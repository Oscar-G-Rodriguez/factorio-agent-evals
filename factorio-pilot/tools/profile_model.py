"""Separate diagnostic inference profile and real first-layer RMSNorm inputs."""
from runtime_paths import runtime_home

from cuda_review import assert_review_current
assert_review_current()
import json
import re
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

root = runtime_home()
artifacts = root / 'artifacts'
meta = json.loads((artifacts / 'model-revision.json').read_text())
configs = list(root.glob('runs/A01-baseline-*/config.json'))
configs.extend(root.glob('runs/baseline-*/config.json'))  # Original host records.
configs.sort(key=lambda path: re.search(r'\d{8}T\d{6}Z', path.parent.name).group(0))
if not configs:
    raise RuntimeError('Complete a baseline prompt configuration first')
config = json.loads(configs[-1].read_text())
tokenizer = AutoTokenizer.from_pretrained(meta['snapshot_path'], local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(meta['snapshot_path'], torch_dtype=torch.bfloat16,
    device_map='cuda', attn_implementation='sdpa', local_files_only=True,
    trust_remote_code=False, use_safetensors=True).eval()
first_event = json.loads((configs[-1].parent / 'steps.jsonl').read_text().splitlines()[0])
inputs = tokenizer.apply_chat_template([
    {'role': 'system', 'content': config['system_prompt']},
    {'role': 'user', 'content': json.dumps(first_event['observation'])},
], tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt').to('cuda')
norm = model.model.layers[0].input_layernorm
captured = {}
def capture(module, arguments):
    x = arguments[0]
    label = 'decode' if x.shape[-2] == 1 else 'prefill'
    if label not in captured:
        captured[label] = {'input': x.detach().cpu(),
                           'weight': module.weight.detach().cpu(), 'epsilon': module.variance_epsilon}
hook = norm.register_forward_pre_hook(capture)
with torch.inference_mode():
    model.generate(**inputs, max_new_tokens=4, do_sample=False, pad_token_id=tokenizer.eos_token_id)
hook.remove()
torch.save(captured, artifacts / 'rmsnorm-real-inputs.pt')
torch.cuda.synchronize()
with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,
                                      torch.profiler.ProfilerActivity.CUDA],
                            record_shapes=True) as profile:
    with torch.inference_mode():
        with torch.profiler.record_function('pilot_prefill_and_decode_16_tokens'):
            model.generate(**inputs, max_new_tokens=16, do_sample=False,
                           pad_token_id=tokenizer.eos_token_id)
    torch.cuda.synchronize()
profile.export_chrome_trace(str(artifacts / 'inference-profile.json'))
(artifacts / 'inference-profile.txt').write_text(profile.key_averages().table(
    sort_by='self_cuda_time_total', row_limit=30))
summary = {'kind': 'separate_diagnostic_profile_not_baseline_timing',
    'prompt_source': 'frozen baseline tool prompt and observation after first action',
    'input_tokens': inputs['input_ids'].shape[-1], 'model': meta,
    'rmsnorm_inputs': {label: {'shape': list(values['input'].shape),
                              'dtype': str(values['input'].dtype), 'epsilon': values['epsilon']}
                      for label, values in captured.items()},
    'capture_overhead_excluded_from_profile': True,
    'cuda_event_count': sum(event.device_type == torch.autograd.DeviceType.CUDA for event in profile.events()),
    'custom_operator_integration': False}
(artifacts / 'profile-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
