"""K02 offline Qwen integration: frozen prompts, correctness, then paired timing.

This runner never connects to Factorio. Forced-token GPU timings are diagnostics,
not executed actions. Fresh timestamped evidence preserves prior experiments.
"""
import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
import traceback

from cuda_review import assert_review_current
from runtime_paths import runtime_home


def write_json(path, value):
    """Persist progress after every bounded stage so failures remain inspectable."""
    path.write_text(json.dumps(value, indent=2, default=str)+'\n', encoding='utf-8')


def freeze_prompts(root):
    """Select five predeclared saved decisions before observing backend outputs."""
    trace = root/'evidence/runs/A04-maintenance-model-20261006T044058Z/steps.jsonl'
    rows = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    selected = [(0,'early'), (17,'fuel-demand'), (23,'full-carry'), (24,'recent-collection-failure'), (43,'late')]
    cases = []
    for step, label in selected:
        row = next(row for row in rows if row['step'] == step)
        messages = row['prompt_messages']
        serialized = json.dumps(messages, sort_keys=True, separators=(',', ':'))
        cases.append({'step': step, 'label': label, 'messages': messages,
                      'messages_sha256': hashlib.sha256(serialized.encode()).hexdigest(),
                      'historical_response': row['response'], 'historical_input_tokens': row['input_tokens']})
    return trace, cases


def main():
    """Run validated inference backends sequentially with explicit timing scope."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('validate','benchmark'), default='validate')
    parser.add_argument('--include-compiled', action='store_true')
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--blocks', type=int, default=3)
    parser.add_argument('--warmups', type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.samples <= 30 or not 1 <= args.blocks <= 3 or not 1 <= args.warmups <= 10:
        parser.error('Timing bounds: 1..30 samples, 1..3 blocks, 1..10 warmups')
    stage = Path(__file__).resolve().parents[1]
    review = assert_review_current('benchmark')
    runtime = runtime_home()
    run = runtime/'runs'/f'K02-integrated-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}'
    run.mkdir(parents=True)
    print('RUN '+str(run), flush=True)
    result = {'run_id': run.name, 'phase': args.phase, 'status': 'started', 'args': vars(args),
              'gpu_exclusive_requested': True, 'game_actions_executed': False,
              'native_source_hashes': review['source_hashes'],
              'fresh_native_inspection': 'All five files manually inspected before this run; archived binding is not executed.',
              'source_hashes': {}, 'validation': [], 'timing': [], 'errors': []}
    for name in ('check_integrated_rmsnorm.py','qwen_rmsnorm_backend.py','cuda_review.py','runtime_paths.py'):
        source = stage/'tools'/name
        result['source_hashes'][name] = hashlib.sha256(source.read_bytes()).hexdigest()
        destination = run/'source'/name
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(source.read_bytes())
    write_json(run/'results.json', result)

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList
        from qwen_rmsnorm_backend import load_reviewed_extension, custom_rmsnorm
        torch.manual_seed(42)
        os.environ.setdefault('TORCHINDUCTOR_COMPILE_THREADS', '1')
        os.environ.setdefault('MAX_JOBS', '2')
        trace, cases = freeze_prompts(stage)
        write_json(run/'prompt-manifest.json', {'trace': trace.relative_to(stage).as_posix(),
            'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(), 'cases': cases})
        metadata = json.loads((runtime/'artifacts/model-revision.json').read_text())
        result['model_revision'] = metadata.get('revision', metadata.get('commit_hash'))
        result['model_metadata'] = metadata
        result['torch'] = torch.__version__
        result['device'] = torch.cuda.get_device_name()
        result['context_limit'] = 8192
        result['output_limit'] = 256
        free, total = torch.cuda.mem_get_info()
        result['memory_before_load'] = {'free_bytes':free,'total_bytes':total}
        if free < 10 * 1024**3:
            raise RuntimeError('Need at least 10 GiB free for this bounded BF16 model test; no other experiment may overlap.')
        started = time.perf_counter()
        extension = load_reviewed_extension()
        result['extension_load_build_seconds'] = time.perf_counter()-started
        # First execute one bounded row before the large model is resident.
        with torch.inference_mode():
            x = torch.zeros(1,2560,device='cuda',dtype=torch.bfloat16)
            weight = torch.ones(2560,device='cuda',dtype=torch.bfloat16)
            output = extension.rmsnorm_forward(x,weight,1e-6)
            torch.cuda.synchronize()
            if not torch.isfinite(output).all() or not (output == 0).all():
                raise RuntimeError('Bounded native smoke failed')
            del x, weight, output
        started = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(metadata['snapshot_path'], dtype=torch.bfloat16,
            device_map='cuda', attn_implementation='sdpa', local_files_only=True,
            trust_remote_code=False, use_safetensors=True).eval().requires_grad_(False)
        tokenizer = AutoTokenizer.from_pretrained(metadata['snapshot_path'], local_files_only=True)
        result['model_load_seconds'] = time.perf_counter()-started
        original_forward = model.forward
        compiled_forward = None
        backends = ['eager','custom'] + (['compiled'] if args.include_compiled else [])
        print('MODEL_LOADED backends='+str(backends), flush=True)

        class StopJSON(StoppingCriteria):
            """Preserve the maintenance runner's one-complete-JSON stopping rule."""
            def __init__(self, start): self.start = start
            def __call__(self, input_ids, scores, **kwargs):
                text = tokenizer.decode(input_ids[0,self.start:],skip_special_tokens=True).strip()
                if not text.startswith('{'): return False
                try:
                    _, end = json.JSONDecoder().raw_decode(text)
                    return end > 0
                except json.JSONDecodeError:
                    return False

        @contextmanager
        def backend(name, diagnostics=False):
            """Switch only this model; always restore reference dispatch on exit."""
            nonlocal compiled_forward
            if name == 'custom':
                with custom_rmsnorm(model, extension.rmsnorm_forward, diagnostics) as dispatch:
                    yield dispatch
            elif name == 'compiled':
                if compiled_forward is None:
                    compiled_forward = torch.compile(original_forward, backend='inductor', mode='default', dynamic=True)
                model.forward = compiled_forward
                try: yield None
                finally: model.forward = original_forward
            else:
                yield None

        def response(case):
            """Time assembly/tokenization through completed decode and JSON parse."""
            torch.cuda.synchronize()
            started = time.perf_counter()
            inputs = tokenizer.apply_chat_template(case['messages'],tokenize=True,add_generation_prompt=True,
                return_tensors='pt',return_dict=True).to('cuda')
            length = inputs['input_ids'].shape[-1]
            if length > 8192-256: raise RuntimeError('Frozen prompt exceeds maintenance budget')
            ids = model.generate(**inputs,max_new_tokens=256,do_sample=False,pad_token_id=tokenizer.eos_token_id,
                stopping_criteria=StoppingCriteriaList([StopJSON(length)]))
            tokens = ids[0,length:]
            text = tokenizer.decode(tokens,skip_special_tokens=True).strip()
            action = json.loads(text)
            if not isinstance(action,dict) or set(action) != {'tool','args'} or not isinstance(action['args'],dict):
                raise RuntimeError('Generated action failed JSON envelope validation')
            torch.cuda.synchronize()
            return {'seconds':time.perf_counter()-started,'input_tokens':length,
                    'tokens':tokens.tolist(),'text':text,'action':action}

        def fixed_work(case, continuation):
            """Separate prefill and forced decode GPU work; keep normal timing uninstrumented."""
            inputs = tokenizer.apply_chat_template(case['messages'],tokenize=True,add_generation_prompt=True,
                return_tensors='pt',return_dict=True).to('cuda')
            start, end = torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
            start.record()
            output = model(**inputs,use_cache=True,logits_to_keep=1)
            end.record()
            torch.cuda.synchronize()
            logits = output.logits[0,-1].detach().float().cpu()
            cache = output.past_key_values
            del output
            decode_times = []
            decode_finite = True
            mask = inputs['attention_mask']
            for token in continuation[:8]:
                mask = torch.cat([mask,torch.ones((1,1),device=mask.device,dtype=mask.dtype)],dim=-1)
                token_input = torch.tensor([[token]],device='cuda')
                a,b = torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
                a.record()
                output = model(input_ids=token_input,attention_mask=mask,past_key_values=cache,
                               use_cache=True,logits_to_keep=1)
                b.record()
                torch.cuda.synchronize()
                decode_times.append(a.elapsed_time(b))
                decode_finite &= bool(torch.isfinite(output.logits).all())
                cache = output.past_key_values
                del output
            del cache
            return logits, {'prefill_gpu_ms':start.elapsed_time(end),
                            'forced_decode_gpu_ms':decode_times, 'forced_decode_tokens':len(decode_times),
                            'forced_decode_logits_finite':decode_finite}

        reference = {}
        all_passed = True
        with torch.inference_mode():
            for case in cases:
                step = case['step']
                for name in backends:
                    print(f'VALIDATE step={step} backend={name}', flush=True)
                    torch.cuda.reset_peak_memory_stats()
                    with backend(name, diagnostics=True) as dispatch:
                        natural = response(case)
                        forced = natural['tokens'] if name == 'eager' else reference[step]['response']['tokens']
                        logits, gpu = fixed_work(case,forced)
                        coverage = dispatch.coverage() if dispatch else None
                    finite = bool(torch.isfinite(logits).all()) and gpu['forced_decode_logits_finite']
                    if name == 'eager':
                        reference[step] = {'response':natural,'logits':logits}
                        agreement = True
                        differences = {'max_absolute':0.0,'mean_absolute':0.0}
                    else:
                        agreement = natural['tokens'] == reference[step]['response']['tokens']
                        difference = (logits-reference[step]['logits']).abs()
                        differences = {'max_absolute':difference.max().item(),'mean_absolute':difference.mean().item()}
                    if name == 'custom' and not coverage['counts'].get('custom',0):
                        raise RuntimeError('Custom backend did not execute any custom calls')
                    passed = finite and agreement
                    all_passed &= passed
                    entry = {'step':step,'label':case['label'],'backend':name,'response':natural,
                             'finite_prefill_logits':finite,'exact_greedy_tokens':agreement,
                             'same_parsed_action':name == 'eager' or natural['action'] == reference[step]['response']['action'],
                             'logit_difference':differences,'fixed_work_diagnostic':gpu,'coverage':coverage,
                             'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                             'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'passed':passed}
                    result['validation'].append(entry)
                    result['status'] = 'validation_in_progress'
                    write_json(run/'results.json',result)
                    print(f'CHECK step={step} backend={name} passed={passed} max_error={differences["max_absolute"]}', flush=True)
            result['all_validation_passed'] = all_passed
            if not all_passed:
                result['status'] = 'validation_failed_no_benchmark_or_live_actions'
            elif args.phase == 'validate':
                result['status'] = 'offline_validation_passed'
            else:
                for case in cases:
                    for name in backends:
                        with backend(name):
                            for _ in range(args.warmups): response(case)
                    samples = {name:[] for name in backends}
                    for block in range(args.blocks):
                        for index in range(args.samples):
                            order = backends if (block+index)%2 == 0 else list(reversed(backends))
                            for name in order:
                                with backend(name): sample = response(case)
                                if sample['tokens'] != reference[case['step']]['response']['tokens']:
                                    raise RuntimeError('Token agreement changed during timing')
                                samples[name].append({'block':block,'index':index,**sample})
                            print(f'TIMING step={case["step"]} block={block} pair={index}',flush=True)
                        result['timing'] = [item for item in result['timing'] if item['step'] != case['step']]
                        result['timing'].append({'step':case['step'],'samples':samples})
                        write_json(run/'results.json',result)
                result['status'] = 'offline_benchmark_complete'
        if args.include_compiled:
            from torch._dynamo.utils import counters
            result['compiler_counters'] = {name:dict(counts) for name,counts in counters.items()}
        write_json(run/'results.json',result)
        print('K02_RESULT '+json.dumps({'run':str(run),'status':result['status']}),flush=True)
        return 0 if all_passed else 2
    except Exception:
        result['status'] = 'runtime_failure'
        result['errors'].append(traceback.format_exc())
        write_json(run/'results.json',result)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
