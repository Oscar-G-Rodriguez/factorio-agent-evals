// Bounded toolchain check, not the optimization experiment.
#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

static void check(cudaError_t result, const char* operation) {
  if (result != cudaSuccess) {
    std::fprintf(stderr, "%s: %s\n", operation, cudaGetErrorString(result));
    std::exit(1);
  }
}

__global__ void add(const float* a, const float* b, float* out, int n) {
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) out[i] = a[i] + b[i];
}

int main() {
  constexpr int n = 1025;  // Non-multiple of block size checks the tail guard.
  constexpr size_t bytes = n * sizeof(float);
  std::vector<float> a(n), b(n), out(n);
  for (int i = 0; i < n; ++i) {
    a[i] = static_cast<float>(i) / 4.0f;
    b[i] = static_cast<float>(n - i) / 8.0f;
  }
  float *da = nullptr, *db = nullptr, *dout = nullptr;
  check(cudaMalloc(&da, bytes), "allocate a");
  check(cudaMalloc(&db, bytes), "allocate b");
  check(cudaMalloc(&dout, bytes), "allocate output");
  check(cudaMemcpy(da, a.data(), bytes, cudaMemcpyHostToDevice), "copy a");
  check(cudaMemcpy(db, b.data(), bytes, cudaMemcpyHostToDevice), "copy b");
  add<<<(n + 127) / 128, 128>>>(da, db, dout, n);
  check(cudaGetLastError(), "launch add");
  check(cudaDeviceSynchronize(), "complete add");
  check(cudaMemcpy(out.data(), dout, bytes, cudaMemcpyDeviceToHost), "copy output");
  for (int i = 0; i < n; ++i) {
    if (!std::isfinite(out[i]) || out[i] != a[i] + b[i]) {
      std::fprintf(stderr, "Mismatch at %d\n", i);
      return 1;
    }
  }
  check(cudaFree(da), "free a");
  check(cudaFree(db), "free b");
  check(cudaFree(dout), "free output");
  std::puts("PASS: all 1025 GPU sums match the CPU reference.");
}
