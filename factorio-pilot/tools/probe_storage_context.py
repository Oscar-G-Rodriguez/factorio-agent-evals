"""Offline matched-context diagnostic; never executes actions or resets Factorio."""
from cuda_review import assert_review_current
review = assert_review_current()
import hashlib
import json
import time
import argparse
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList

project = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--storage-subgoal-only', action='store_true')
args = parser.parse_args()
source = project/'evidence/runs/A04-maintenance-model-20261006T044058Z'
events = [json.loads(line) for line in (source/'steps.jsonl').read_text().splitlines()]
event = events[23]
config = json.loads((source/'config.json').read_text())
messages = event['prompt_messages']
assert messages[0]['role'] == 'system' and messages[-1]['role'] == 'user'
latest = json.loads(messages[-1]['content'])
assert latest['observation']['carrying']['available_carry_space'] == 0
assert any(e['name'] == 'wooden-chest' and e['handle'] == 'e1' and e['output_storage']['free_plate_capacity'] == 1600 for e in latest['observation']['equipment'])
assert 'store_plates: args=' in messages[0]['content']
torch.manual_seed(42)
model = AutoModelForCausalLM.from_pretrained(config['model']['snapshot_path'], torch_dtype=torch.bfloat16,
    device_map='cuda', attn_implementation='sdpa', local_files_only=True, trust_remote_code=False, use_safetensors=True).eval()
tokenizer = AutoTokenizer.from_pretrained(config['model']['snapshot_path'], local_files_only=True)


class StopAfterObject(StoppingCriteria):
    def __init__(self, start): self.start = start
    def __call__(self, input_ids, scores, **kwargs):
        text = tokenizer.decode(input_ids[0, self.start:], skip_special_tokens=True).strip()
        if not text.startswith('{'): return False
        try:
            json.JSONDecoder().raw_decode(text)
            return True
        except json.JSONDecodeError:
            return False


results = []
conditions = [('recorded_history', messages), ('fresh_context', [messages[0], messages[-1]])]
if args.storage_subgoal_only:
    conditions = [('explicit_storage_subgoal', [messages[0], messages[-1],
        {'role': 'user', 'content': 'For this diagnostic only, choose one available action that frees carrying space by storing carried iron plates in the observed chest. Return the action JSON.'}])]
for condition, prompt in conditions:
    inputs = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True, return_tensors='pt', return_dict=True).to('cuda')
    length = inputs['input_ids'].shape[-1]
    assert length <= 8192-256
    if condition == 'recorded_history': assert length == event['input_tokens']
    torch.cuda.synchronize(); started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=256, do_sample=False, pad_token_id=tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([StopAfterObject(length)]))
    torch.cuda.synchronize()
    elapsed = time.perf_counter()-started
    response = tokenizer.decode(output[0, length:], skip_special_tokens=True).strip()
    try: action = json.loads(response)
    except json.JSONDecodeError: action = None
    results.append({'condition': condition, 'input_tokens': length, 'response': response, 'action': action,
        'same_as_recorded_action': action == event['action'],
        'stores_into_observed_chest': bool(action and action.get('tool') == 'store_plates' and action.get('args', {}).get('chest_handle') == 'e1' and isinstance(action.get('args', {}).get('plate_count'), int) and not isinstance(action['args']['plate_count'], bool) and 1 <= action['args']['plate_count'] <= 100),
        'response_seconds_single_unwarmed_sample_not_benchmark': elapsed})
    print(json.dumps(results[-1]), flush=True)
report = {'kind': 'offline_matched_context_development_probe', 'source_run': source.name, 'step': 23,
    'source_event_sha256': hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest(),
    'model': config['model'], 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'native_review_hashes': review['source_hashes'], 'actual_game_actions_executed': 0,
    'intervention': 'explicit storage subgoal appended to fresh prompt' if args.storage_subgoal_only else 'remove older user/assistant messages; keep identical system instructions and latest observed state/feedback',
    'results': results, 'limits': 'One observed state. History probe changes content and length together; cannot isolate token count from historical action bias. Explicit subgoal is assisted capability diagnosis, not autonomous maintenance success. Proposed actions are not executed or full-episode outcomes.'}
name = 'storage-subgoal-probe.json' if args.storage_subgoal_only else 'storage-context-probe.json'
(project/'evidence/artifacts'/name).write_text(json.dumps(report, indent=2)+'\n')
