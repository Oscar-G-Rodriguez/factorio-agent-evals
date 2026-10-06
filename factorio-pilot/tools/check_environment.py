"""Read-only toolchain checks; writes a report only when --output is supplied.

Run in the intended project environment, not the Codex bundled runtime.
This never installs packages, downloads models, or changes hardware settings.
"""

import argparse
from cuda_review import assert_review_current
assert_review_current()
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def command_check(args):
    executable = shutil.which(args[0])
    if executable is None:
        return {"status": "missing", "command": args}
    try:
        result = subprocess.run(
            [executable, *args[1:]], capture_output=True, text=True, timeout=15
        )
        return {
            "status": "ok" if result.returncode == 0 else "failed",
            "path": executable,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "failed", "path": executable, "error": str(error)}


def package_check(distribution):
    try:
        return {"status": "installed", "version": importlib.metadata.version(distribution)}
    except importlib.metadata.PackageNotFoundError:
        return {"status": "missing"}


def torch_check():
    if importlib.util.find_spec("torch") is None:
        return {"status": "missing"}
    try:
        import torch

        if not torch.cuda.is_available():
            return {"status": "cuda_unavailable", "version": torch.__version__}
        # Tiny framework calculation only. This is not a custom CUDA test.
        torch.cuda.reset_peak_memory_stats()
        tensor = torch.tensor([1.0, 2.0, 3.0], device="cuda")
        actual = tensor.square().sum().item()
        torch.cuda.synchronize()
        return {
            "status": "ok" if actual == 14.0 else "incorrect_result",
            "version": torch.__version__,
            "build_cuda_version": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "device_capability": list(torch.cuda.get_device_capability(0)),
            "bf16_supported": torch.cuda.is_bf16_supported(),
            "tiny_calculation_expected": 14.0,
            "tiny_calculation_actual": actual,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        }
    except Exception as error:
        return {"status": "failed", "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "disk_free_gib_at_working_directory": round(
            shutil.disk_usage(Path.cwd()).free / (1024**3), 2
        ),
        "commands": {
            "gpu": command_check([
                "nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ]),
            "docker": command_check([
                "docker", "version", "--format", "{{json .}}",
            ]),
            "cuda_compiler": command_check(["nvcc", "--version"]),
            "cpp_compiler": command_check(["g++", "--version"]),
            "sanitizer": command_check(["compute-sanitizer", "--version"]),
            "git": command_check(["git", "--version"]),
        },
        "packages": {
            name: package_check(name) for name in (
                "torch", "transformers", "factorio-learning-environment",
            )
        },
        "torch_gpu_smoke_check": torch_check(),
        "not_verified_by_this_check": [
            "custom_cpp_cuda_compilation", "factorio_connection", "model_loading",
        ],
    }
    encoded = json.dumps(report, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
