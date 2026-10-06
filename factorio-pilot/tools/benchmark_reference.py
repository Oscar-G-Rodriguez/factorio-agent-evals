"""Time the unchanged installed RMSNorm on captured model tensors."""
from runtime_paths import runtime_home

from cuda_review import assert_review_current
assert_review_current()
import json
import math
import statistics
from pathlib import Path
import torch
from transformers.models.qwen3.modeling_qwen3 import Qwen3RMSNorm

root = runtime_home() / 'artifacts'
samples = torch.load(root / 'rmsnorm-real-inputs.pt', weights_only=True)
results = []
outputs = {}
with torch.inference_mode():
    for label, sample in samples.items():
        x = sample['input'].to('cuda').contiguous()
        norm = Qwen3RMSNorm(x.shape[-1], eps=sample['epsilon']).to(device='cuda', dtype=x.dtype).eval()
        norm.weight.copy_(sample['weight'].to('cuda'))
        actual = norm(x)
        # Match the original operator's BF16 intermediate and output rounding.
        precise = x.to(torch.float64)
        precise *= torch.rsqrt(precise.square().mean(-1, keepdim=True) + sample['epsilon'])
        ideal = precise.to(x.dtype) * norm.weight
        torch.testing.assert_close(actual, ideal, rtol=0.02, atol=1e-5)
        outputs[label] = actual.cpu()
        for _ in range(10):
            norm(x)
        torch.cuda.synchronize()
        pairs = []
        for _ in range(100):
            start = torch.cuda.Event(enable_timing=True)
            end = torch.cuda.Event(enable_timing=True)
            start.record()
            norm(x)
            end.record()
            pairs.append((start, end))
        torch.cuda.synchronize()
        times = sorted(start.elapsed_time(end) for start, end in pairs)
        results.append({'phase': label, 'shape': list(x.shape), 'dtype': str(x.dtype),
            'reference': 'installed_Qwen3RMSNorm_Transformers_4.57.6',
            'accuracy_against_float64_reference': 'passed_rtol_0.02_atol_1e-5_with_BF16_rounding',
            'timing_method': 'CUDA events around unchanged forward, 10 warmups and 100 samples',
            'median_gpu_ms': statistics.median(times),
            'p95_gpu_ms_nearest_rank': times[math.ceil(len(times)*0.95)-1],
            'mean_gpu_ms': statistics.mean(times)})
torch.save(outputs, root / 'rmsnorm-reference-output.pt')
report = {'custom_kernel_used': False, 'reference_results': results,
          'full_response_speedup_measured': False}
(root / 'rmsnorm-reference-benchmark.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
