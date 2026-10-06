#include <torch/extension.h>
#include <c10/cuda/CUDAGuard.h>
#include <cmath>

void launch_rmsnorm(const at::Tensor& input, const at::Tensor& weight,
                    at::Tensor& output, float epsilon);

at::Tensor rmsnorm_forward(const at::Tensor& input, const at::Tensor& weight, double epsilon) {
    TORCH_CHECK(input.is_cuda() && weight.is_cuda(), "input and weight must be CUDA tensors");
    TORCH_CHECK(input.device() == weight.device(), "input and weight must share a device");
    TORCH_CHECK(input.layout() == at::kStrided && weight.layout() == at::kStrided,
                "input and weight must have strided layout");
    TORCH_CHECK(input.scalar_type() == at::kBFloat16 && weight.scalar_type() == at::kBFloat16,
                "input and weight must be BF16");
    TORCH_CHECK(input.dim() >= 1 && input.size(-1) == 2560, "input last dimension must be 2560");
    TORCH_CHECK(weight.dim() == 1 && weight.numel() == 2560, "weight must have shape [2560]");
    TORCH_CHECK(input.is_contiguous() && weight.is_contiguous(), "tensors must be contiguous");
    TORCH_CHECK(!input.is_neg() && !weight.is_neg(), "negative views must be resolved first");
    TORCH_CHECK(std::isfinite(epsilon) && epsilon > 0 && epsilon <= 1,
                "epsilon must be finite and in (0,1]");
    const float epsilon_fp32 = static_cast<float>(epsilon);
    TORCH_CHECK(std::isnormal(epsilon_fp32),
                "epsilon must remain a positive normal FP32 value after conversion");
    TORCH_CHECK(!input.requires_grad() && !weight.requires_grad(), "forward-only inference operator");
    // Bound this pilot's workload before allocating its output. At BF16,
    // 8192 rows of 2560 values require at most 40 MiB for the output tensor.
    TORCH_CHECK(input.numel() / 2560 <= 8192, "pilot supports at most 8192 rows");
    c10::cuda::CUDAGuard device_guard(input.device());
    auto output = at::empty_like(input);
    if (input.numel() > 0) launch_rmsnorm(input, weight, output, epsilon_fp32);
    return output;
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("rmsnorm_forward", &rmsnorm_forward, "BF16 RMSNorm forward (2560 features)");
}
