# Engineering conventions

This is a research pilot with a frozen historical experiment and newer assisted development runs. Preserve those boundaries when changing prompts, tools, budgets or memory. A run configuration and its source hashes determine what was evaluated; the latest source file does not retroactively describe older results.

Python implements inference orchestration and validated game tools. C++ validates tensors and dispatches the forward-only CUDA RMSNorm kernel. The CUDA kernel uses one 256-thread block per 2560-feature row, FP32 reduction and the reference's BF16 rounding behavior. Factorio simulation and RCON requests execute outside the GPU model.

## Validation

Follow [the native source review](outputs/CUDA%20and%20C%2B%2B%20Source%20Review.md) and `factorio-pilot/AGENTS.md` before GPU entry points. Added or changed native sources invalidate the review; do not regenerate its manifest as automatic approval. Numerical evidence must match the reviewed source hashes before benchmarking. Empty, invalid and bounded small cases precede larger captured inputs. Whole-model integration requires separate numerical and behavioral checks.

For CPU tool/evaluation checks, use the existing Linux environment:

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- bash -lc 'cd /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools && /home/osci2/factorio-pilot/.venv/bin/python -m unittest test_maintenance test_logistics_tools test_cuda_review'
```

Exact agent and kernel commands are in the linked runtime README and result reports. Run only one controller against the current Factorio server: each resets that world. Parallel evaluation needs isolated servers and a shared-model scheduler before it can be interpreted. Preserve the same simulation cadence and input contract across scored conditions.

## Evidence and Git

Commit project-authored source, report methods, run metadata, relevant traces and source snapshots. Preserve old artifacts before replacing fixed-name benchmark outputs. Store model weights and downloaded binaries outside Git. Use `.gitattributes` to preserve exact file bytes rather than normalizing line endings; reproducibility checks use SHA-256, including historical source snapshots. Never execute superseded native snapshots with known validation defects.

The large raw profiler JSON remains on the host, with a compressed copy in Git. Captured operator tensors are small experiment inputs rather than model weights and are retained. Do not include resumes, unrelated project material, vault exports, credentials or scratch downloads in this project history.

Current scripts include fixed host paths and some executable modules with top-level orchestration. Those are recorded pilot exceptions to the general preference for portable configuration and independently importable functions. Moving the checkout or adding parallel workers requires explicit configuration work and fresh checks, rather than rewriting historical evidence.

## GPU settings

Keep clock, voltage, power, firmware and Windows timeout settings unchanged. The user authorized only the temporary NVIDIA debugging interface required for sanitizer validation; its previous state was restored. Reuse the preserve/restore workflow for an authorized sanitizer session and record the actual result. An operator speedup is distinct from response latency or complete evaluation throughput.

