"""Forward correctness and alternating GPU benchmark; no model monkeypatch."""
from runtime_paths import runtime_home

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
from cuda_review import assert_review_current
import torch
from torch.utils.cpp_extension import load
from transformers.models.qwen3.modeling_qwen3 import Qwen3RMSNorm

parser = argparse.ArgumentParser()
parser.add_argument('--tests-only', action='store_true')
args = parser.parse_args()
assert_review_current('correctness' if args.tests_only else 'benchmark')
project = runtime_home()
source = Path(__file__).resolve().parent.parent / 'cuda'
build = project/'build'/'rmsnorm'
build.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('MAX_JOBS', '2')
os.environ.setdefault('TORCH_CUDA_ARCH_LIST', '12.0')
extension = load(name='pilot_rmsnorm', sources=[str(source/'rmsnorm.cpp'), str(source/'rmsnorm.cu')],
                 build_directory=str(build), extra_cflags=['-O3'],
                 extra_cuda_cflags=['-O3', '--fmad=false', '-lineinfo'], verbose=True)
custom = extension.rmsnorm_forward
root = project/'artifacts'
captured = torch.load(root/'rmsnorm-real-inputs.pt', weights_only=True)
free_bytes, _ = torch.cuda.mem_get_info()
if free_bytes < 1024**3:
    raise RuntimeError('Leave at least 1 GiB free for the bounded operator checks; stop other GPU experiments first.')
torch.manual_seed(123)
cases = {}
for label, rows, scale in [('zero',1,0), ('near_zero',3,1e-8),('odd_rows',7,1),('random',31,3)]:
    cases[label] = {'input':torch.randn(rows,2560,dtype=torch.bfloat16)*scale,
                    'weight':torch.randn(2560,dtype=torch.bfloat16), 'epsilon':1e-6}
# Start with one row; increase workload only after the smaller cases pass.
cases.update({label:captured[label] for label in ('decode','prefill')})
checks = []
bench = []
with torch.inference_mode():
    for label, sample in cases.items():
        x = sample['input'].to('cuda').contiguous()
        w = sample['weight'].to('cuda').contiguous()
        eps = sample['epsilon']
        norm = Qwen3RMSNorm(2560, eps=eps).to(device='cuda', dtype=x.dtype).eval()
        norm.weight.copy_(w)
        actual = custom(x,w,eps)
        torch.cuda.synchronize()  # Surface asynchronous device errors here.
        expected = norm(x)
        precise = x.double()
        ideal = (precise * torch.rsqrt(precise.square().mean(-1,keepdim=True)+eps)).to(x.dtype) * w
        torch.testing.assert_close(actual, expected, rtol=0.02, atol=1e-5)
        torch.testing.assert_close(actual, ideal, rtol=0.02, atol=1e-5)
        checks.append({'case':label,'shape':list(x.shape),'passed':True,
                       'max_absolute_error':(actual.float()-expected.float()).abs().max().item(),
                       'fraction_exact':(actual==expected).float().mean().item()})
        if label not in captured or args.tests_only:
            continue
        batches = []
        for batch in range(3):
            for _ in range(10):
                norm(x); custom(x,w,eps)
            torch.cuda.synchronize()
            events = {'reference':[], 'custom':[]}
            for index in range(100):
                order = ('reference','custom') if (index+batch)%2 == 0 else ('custom','reference')
                for name in order:
                    start,end = torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
                    start.record()
                    if name == 'reference': norm(x)
                    else: custom(x,w,eps)
                    end.record()
                    events[name].append((start,end))
            torch.cuda.synchronize()
            times = {name:[a.elapsed_time(b) for a,b in pairs] for name,pairs in events.items()}
            metrics = {name:{'median_ms':statistics.median(t), 'p95_ms':sorted(t)[math.ceil(.95*len(t))-1],
                             'samples_ms':t} for name,t in times.items()}
            metrics['speedup'] = metrics['reference']['median_ms']/metrics['custom']['median_ms']
            batches.append(metrics)
        bench.append({'phase':label,'shape':list(x.shape),'batches':batches})
    empty = torch.empty(0,2560,device='cuda',dtype=torch.bfloat16)
    assert custom(empty,w,eps).shape == empty.shape
    checks.append({'case':'empty_batch','passed':True})
    for label, bad_x, bad_w, bad_eps in [
        ('cpu_input',x.cpu(),w,eps), ('wrong_dtype',x.float(),w,eps),
        ('wrong_width',x[...,:128].contiguous(),w,eps),
        ('noncontiguous',torch.ones(2560,3,device='cuda',dtype=torch.bfloat16).t(),w,eps),
        ('wrong_weight',x,w[:128],eps), ('nan_epsilon',x,w,float('nan')),
        ('zero_epsilon',x,w,0), ('negative_epsilon',x,w,-1e-6),
        ('infinite_epsilon',x,w,float('inf')),
        ('epsilon_underflow',x,w,1e-300), ('epsilon_subnormal',x,w,1e-40),
        ('weight_dtype',x,w.float(),eps),
        ('weight_noncontiguous',x,torch.ones(5120,device='cuda',dtype=torch.bfloat16)[::2],eps),
        ('sparse_layout',x.reshape(-1,2560)[:1].to_sparse(),w,eps),
        ('negative_view',torch._neg_view(x),w,eps),
        ('row_limit',torch.empty(8193,2560,device='cuda',dtype=torch.bfloat16),w,eps),
        ('requires_grad',x.clone().requires_grad_(),w,eps)]:
        try: custom(bad_x,bad_w,bad_eps)
        except (RuntimeError,ValueError): checks.append({'case':label,'rejected':True,'passed':True})
        else: raise AssertionError(f'Invalid input accepted: {label}')
    # A nondefault stream validates current-stream dispatch and dependencies.
    stream = torch.cuda.Stream()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        stream_x = x.clone()
        stream_out = custom(stream_x,w,eps)
        stream_expected = norm(stream_x)
    stream.synchronize()
    torch.testing.assert_close(stream_out,stream_expected,rtol=0.02,atol=1e-5)
    checks.append({'case':'nondefault_stream','passed':True})
report = {'correctness_checks':checks,'rtol':0.02,'atol':1e-5,
          'benchmark':bench, 'timing':'GPU events including wrapper launch gaps; allocations included; no transfers; alternating order; 3 batches x 100 pairs; 10 warmups',
          'device':torch.cuda.get_device_name(),'torch':torch.__version__,
          'cuda':torch.version.cuda,'end_to_end_speedup_measured':False,
          'sanitizer_status':'separate_check_required',
          'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'rmsnorm.cpp',source/'rmsnorm.cu')}}
name = 'rmsnorm-correctness.json' if args.tests_only else 'rmsnorm-custom-benchmark.json'
(root/name).write_text(json.dumps(report,indent=2)+'\n')
print('RMSNORM_RESULT '+json.dumps({**report,'benchmark':[{'phase':b['phase'],'speedups':[t['speedup'] for t in b['batches']]} for b in bench]}),flush=True)
