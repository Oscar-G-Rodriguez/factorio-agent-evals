#include <torch/extension.h>
#include <c10/cuda/CUDAStream.h>
#include <c10/cuda/CUDAException.h>
#include <cuda_bf16.h>

// One independent row per block. All threads participate in every barrier.
__global__ void rmsnorm_kernel(const __nv_bfloat16* input, const __nv_bfloat16* weight,
                              __nv_bfloat16* output, float epsilon) {
    constexpr int features = 2560;
    constexpr int threads = 256;
    const int64_t row = static_cast<int64_t>(blockIdx.x) * features;
    const int lane = threadIdx.x;
    __shared__ float sums[threads];
    float sum = 0.0f;
    for (int i = lane; i < features; i += threads) {
        float x = __bfloat162float(input[row+i]);
        sum += x*x;
    }
    sums[lane] = sum;
    __syncthreads();
    for (int stride = threads/2; stride > 0; stride /= 2) {
        if (lane < stride) sums[lane] += sums[lane+stride];
        __syncthreads();
    }
    float scale = rsqrtf(sums[0] / features + epsilon);
    for (int i = lane; i < features; i += threads) {
        float normalized = __bfloat162float(input[row+i]) * scale;
        // Match Qwen: round normalization to BF16 BEFORE multiplying weight.
        float rounded = __bfloat162float(__float2bfloat16_rn(normalized));
        output[row+i] = __float2bfloat16_rn(rounded * __bfloat162float(weight[i]));
    }
}

void launch_rmsnorm(const at::Tensor& input, const at::Tensor& weight,
                    at::Tensor& output, float epsilon) {
    int64_t rows = input.numel() / 2560;
    TORCH_CHECK(rows <= 2147483647, "too many rows for CUDA grid");
    rmsnorm_kernel<<<static_cast<unsigned>(rows), 256, 0, c10::cuda::getCurrentCUDAStream()>>>(
        reinterpret_cast<const __nv_bfloat16*>(input.data_ptr<at::BFloat16>()),
        reinterpret_cast<const __nv_bfloat16*>(weight.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(output.data_ptr<at::BFloat16>()), epsilon);
    C10_CUDA_KERNEL_LAUNCH_CHECK();
}
