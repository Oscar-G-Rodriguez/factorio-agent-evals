# CUDA and C++ Source Review

The active project contains three native source files: the C++ RMSNorm binding, its CUDA reduction kernel, and a bounded CUDA addition smoke test. Two archived RMSNorm files preserve the earlier experiment. All five were inspected. This review covers project-authored source and its launch/test harness; third-party PyTorch, CUDA libraries, the driver and Factorio internals are outside this source review.

Static review is complete for the revised active sources. Numerical validation defects were fixed. No out-of-bounds access, shared-memory race or divergent barrier was identified in the inspected active kernels. This finding does not replace runtime correctness or sanitizer validation. Hashes in `factorio-pilot/evidence/artifacts/cuda-source-review.json` identify the exact reviewed files; new or changed native files invalidate the launch gate.

## Findings and changes

| Finding | Effect | Resolution |
| --- | --- | --- |
| Positive double epsilon could underflow when converted to float | The previous check accepted values such as 1e-300; an all-zero row could then normalize with zero epsilon and produce NaNs | Validate the converted epsilon as a normal FP32 value before allocation or launch. Add underflow and subnormal rejection cases. |
| Contiguity alone did not explicitly rule out lazy negative views | Direct data-pointer access could read underlying unnegated values | Reject unresolved negative views; add a boundary test. |
| Kernel work was bounded only by the CUDA grid limit | The API permitted workloads far beyond this pilot's needs | Bound total rows to 8192 before output allocation, limiting output to 40 MiB; add a rejection test. |
| Layout assumptions were implicit | The pointer interface requires ordinary strided tensors | Explicitly reject other layouts; add a sparse-layout rejection case. |
| Existing numerical evidence belongs to older source hashes | Earlier successful checks cannot validate revised code | Benchmarks require a fresh matching correctness artifact. Historical evidence remains preserved. |

The archived binding retains the earlier epsilon and view validation gaps. It was reviewed as historical evidence and is not approved for new execution. The active source contains the fixes; the old measured speedups are not silently attributed to the revised source.

## C++ binding review

`rmsnorm.cpp` accepts CUDA BF16 tensors on the same device, input last dimension 2560, a weight vector of length 2560, and contiguous strided layouts. It rejects gradient-bearing tensors, unresolved negative views, invalid epsilon and excessive rows. Argument validation precedes output allocation. Empty input returns an empty tensor without launching a zero-sized grid. PyTorch owns the output allocation; there is no manual device allocation or free in this binding.

The device guard selects the tensor's device before allocation and launch. The launcher uses PyTorch's current CUDA stream for that device. This follows tensor stream ordering; it does not synchronize unrelated streams automatically. The harness tests an explicitly ordered nondefault stream.

FP32 squared sums can overflow for extreme BF16 values, and nonfinite input can propagate nonfinite output as in the reference arithmetic. The operator is not a general-purpose finite-value sanitizer. Captured model inputs and full-model logits must be checked for numerical validity during integration. Positive normal FP32 epsilon prevents the discovered zero-epsilon conversion problem for zero rows.

## RMSNorm kernel review

For row r and feature i, the kernel accesses input/output at `r*2560+i`. Exactly one block is launched per nonempty row. The 256 threads use feature indices `lane + 256*k` while the index is less than 2560, covering every feature once. Each block's output region is disjoint. Weight reads are limited to the validated 2560-element vector. The row offset uses 64-bit arithmetic and the pilot row bound keeps it far below overflow.

Every lane initializes one element of the 256-float shared array. In reduction phase stride s, only lanes below s write, and their read partners are in the non-writing upper half. Every phase ends with an unconditional block barrier, so all 256 threads participate. The final barrier precedes reading the total. There are no atomics, inter-block dependencies, dynamic allocations, recursive launches or unbounded loops. Shared memory is 1024 bytes per block.

Normalization reduces in FP32, rounds to BF16 before multiplying weights, and rounds the final output to BF16. The launch configuration fixes block size at 256, matching the kernel's shared-array/reduction assumptions. The grid check prevents truncation when converting row count to the launch dimension. `C10_CUDA_KERNEL_LAUNCH_CHECK` catches launch errors; asynchronous execution errors need synchronization in the validation harness. NVIDIA describes these distinctions in its [error-handling guidance](https://developer.nvidia.com/blog/how-query-device-properties-and-handle-errors-cuda-cc/) and [CUDA programming guide](https://docs.nvidia.com/cuda/archive/12.8.1/cuda-c-programming-guide/index.html).

## Smoke kernel review

`smoke.cu` allocates three arrays of 1025 floats, initializes both inputs on the CPU and copies their full contents. Its nine blocks of 128 threads cover indices 0 through 1151; the `i < 1025` guard prevents tail reads/writes. Each valid thread writes one unique output element. There are no shared arrays or barriers. Allocation, transfer, launch, synchronization, copy-back and successful-path free calls check CUDA errors. The host verifies every result is finite and equal to the CPU result.

Error paths exit the small standalone process, whose CUDA context releases remaining allocations; they do not retain a leak across a continuing application. Process cleanup is not a proposed ownership pattern for the integrated extension, which uses PyTorch-managed tensors.

## Runtime validation order

1. Validate the reviewed source hashes using the CPU-only gate.
2. Run the bounded correctness suite, starting with one zero row, then small near-zero/random rows, captured decode and captured prefill tensors. Synchronize after custom operations so device errors surface at the offending case.
3. Reject invalid dtype, shape, layout, contiguity, gradients, row count and epsilon; check empty input and nondefault-stream behavior.
4. Permit benchmarks only when every required case passed for the same C++/CUDA hashes. Preserve the old result files before generating replacements.
5. Review and validate any new warp kernel or integration wrapper before executing it. Full-model checks include finite logits, numerical differences, token agreement and actual agent behavior.

The guard is a project workflow control, not an operating-system restriction on arbitrary manually launched programs. Direct execution of historical or unreviewed binaries is prohibited by the project instructions. The existing GPU/model entry points and native smoke launcher check the gate; future entry points must do the same.

## Other safety controls and remaining limits

The revised binding compiled successfully. All 25 numerical, invalid-argument, empty-input and stream cases passed, including the new epsilon conversion, negative-view and row-limit cases. The benchmark eligibility gate confirmed that this evidence matches the reviewed hashes. Twenty CPU unit checks covering the review gate and current tool adapters passed. These results authorize bounded development testing under the project workflow; they do not establish sanitizer validation or measure revised operator speed.

Use small bounded workloads, one GPU experiment at a time, ordinary user execution, and standard driver-managed settings. Preserve launch error checks, allocation ownership and current-stream ordering. After an illegal-access or CUDA-context error, stop that process and diagnose it in a fresh process; do not keep retrying in the damaged context. Do not run stress tests or change clocks, power, voltage, firmware or Windows TDR timeouts as part of this project.

On October 6 the user explicitly authorized the temporary Windows debugging-interface setting. Its previous absent state was recorded, `EnableInterface` alone was enabled, and the reviewed 25-case RMSNorm suite ran under memcheck, racecheck, initcheck and synccheck. Each reported zero errors; the setting was restored afterward and the registry key is absent again. Logs and matching source hashes are in `factorio-pilot/evidence/artifacts/approved-sanitizer-validation.json`. This closes the earlier permission blocker for this check. It covers the bounded RMSNorm operator suite, not third-party libraries generally, whole-model integration, or the separate native smoke binary. See [NVIDIA's sanitizer documentation](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html#windows-specific-behavior).

Further Factorio logistics work remains authorized, but it must honor this review gate before runtime tests. The existing factory stores plates in the furnace output and needs collection/storage tools for long maintenance runs; production expansion will be evaluated as a separate explicit goal after maintenance is reachable.
