"""One local inference smoke check; not a Factorio baseline run."""
from runtime_paths import runtime_home

from cuda_review import assert_review_current
assert_review_current()
import json
import time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

root = runtime_home() / 'artifacts'
metadata = json.loads((root / 'model-revision.json').read_text())
path = metadata['snapshot_path']
free, total = torch.cuda.mem_get_info()
if free < 10 * 1024**3:
    raise RuntimeError(f'Only {free / 1024**3:.2f} GiB GPU memory free; leave room for model loading.')
tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
started = time.perf_counter()
model = AutoModelForCausalLM.from_pretrained(
    path, torch_dtype=torch.bfloat16, device_map='cuda',
    attn_implementation='sdpa', local_files_only=True,
    trust_remote_code=False, use_safetensors=True,
).eval()
torch.cuda.synchronize()
loading_seconds = time.perf_counter() - started
inputs = tokenizer.apply_chat_template(
    [{'role': 'user', 'content': 'Reply with exactly READY.'}],
    tokenize=True, add_generation_prompt=True, return_tensors='pt', return_dict=True,
).to('cuda')
torch.cuda.reset_peak_memory_stats()
started = time.perf_counter()
with torch.inference_mode():
    outputs = model.generate(**inputs, max_new_tokens=32, do_sample=False,
                             pad_token_id=tokenizer.eos_token_id)
torch.cuda.synchronize()
seconds = time.perf_counter() - started
new = outputs[0, inputs['input_ids'].shape[-1]:]
text = tokenizer.decode(new, skip_special_tokens=True)
assert text.strip(), 'Empty model response.'
report = {
    'kind': 'local_inference_development_smoke', **metadata,
    'torch_version': torch.__version__, 'precision': 'bfloat16',
    'attention_backend': 'sdpa', 'loading_seconds': loading_seconds,
    'input_tokens': inputs['input_ids'].shape[-1], 'output_tokens': len(new),
    'response_seconds': seconds, 'response': text,
    'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
    'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
    'free_gpu_bytes_before_load': free,
    'model_hidden_size': model.config.hidden_size,
    'model_rms_norm_eps': model.config.rms_norm_eps,
}
(root / 'model-smoke.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
