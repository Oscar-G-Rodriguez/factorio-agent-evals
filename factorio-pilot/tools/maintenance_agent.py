"""Failure-oriented maintenance development evaluation, separate from construction."""
from runtime_paths import runtime_home

from cuda_review import assert_review_current
assert_review_current()
import argparse
import hashlib
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from fle.env import FactorioInstance
from maintenance_tools import build_maintenance_fixture, ProductionMonitor

parser = argparse.ArgumentParser()
parser.add_argument('--controller', choices=('model', 'scripted', 'idle'), default='model')
parser.add_argument('--inference-backend', choices=('pytorch', 'custom-rmsnorm'), default='pytorch')
parser.add_argument('--minutes', type=int, default=20)
parser.add_argument('--wall-seconds', type=int, default=600)
args = parser.parse_args()
if args.inference_backend != 'pytorch' and args.controller != 'model':
    raise ValueError('A custom inference backend requires the model controller')
if not 2 <= args.minutes <= 20 or not 30 <= args.wall_seconds <= 1200:
    raise ValueError('Maintenance budget out of bounds')
root = runtime_home()
run = root/'runs'/f'A04-maintenance-{args.controller}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}'
run.mkdir()
print('RUN '+str(run), flush=True)
model = tokenizer = metadata = norm_dispatch = None
if args.controller == 'model':
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList
    metadata = json.loads((root/'artifacts/model-revision.json').read_text())
    torch.manual_seed(42)
    model = AutoModelForCausalLM.from_pretrained(metadata['snapshot_path'], torch_dtype=torch.bfloat16,
        device_map='cuda', attn_implementation='sdpa', local_files_only=True, trust_remote_code=False, use_safetensors=True).eval().requires_grad_(False)
    tokenizer = AutoTokenizer.from_pretrained(metadata['snapshot_path'], local_files_only=True)
    if args.inference_backend == 'custom-rmsnorm':
        # Retain instance-local forwards; standalone process cleanup restores them.
        import atexit
        from qwen_rmsnorm_backend import RMSNormDispatch, load_reviewed_extension
        norm_dispatch = RMSNormDispatch(model, load_reviewed_extension().rmsnorm_forward)
        atexit.register(norm_dispatch.restore)

    class StopAfterObject(StoppingCriteria):
        def __init__(self, start): self.start = start
        def __call__(self, input_ids, scores, **kwargs):
            text = tokenizer.decode(input_ids[0, self.start:], skip_special_tokens=True).strip()
            if not text.startswith('{'): return False
            try:
                _, end = json.JSONDecoder().raw_decode(text)
                return end > 0
            except json.JSONDecodeError:
                return False

instance = FactorioInstance(address='127.0.0.1', tcp_port=27000, fast=True, reset_speed=10, reset_paused=True)
state_text = (root/'artifacts/starting-state.json').read_text()
bridge, fixture = build_maintenance_fixture(instance, state_text)
(run/'fixture.json').write_text(json.dumps(fixture, indent=2, default=str)+'\n')
origin = bridge.tick()
monitor = ProductionMonitor(origin, instance.namespace._get_production_stats()['output'].get('iron-plate', 0))
system = '''You maintain an ALREADY BUILT Factorio iron factory. Return exactly ONE JSON object with tool and args, no prose.
Keep producing at least 16 iron plates per simulated minute for as long as possible. There is NO finish action. Meeting the target once does not end the run.
The drill automatically feeds ore into the adjacent furnace. BOTH machines burn coal independently. You have ample reserve coal, but each refill is limited to 1..3 coal by this benchmark. Initial fuel is low. Observe coal_in_fuel_inventory AND remaining_burning_fuel_joules: zero stored coal alone does not mean the currently burning piece has expired.
Finished plates stay in the furnace output. Its 100-plate limit stops production when full. collect_output moves plates into your carried inventory (benchmark limit 100); store_plates moves carried plates into the supplied wooden chest (1600 capacity). A chest alone does not transfer anything automatically. No plates disappear when collected or stored.
You are already within transfer range of all three machines; construction and movement are outside this maintenance task. Use only current observed handles.
After EACH decision, including checking, waiting or an invalid action, the game advances exactly 15 simulated seconds. Inference is paused game time. Two consecutive 60-second windows below 16 plates end the run as sustained failure. A time limit is recorded as survival through the limit, not failure.
Examples of syntax only (use actual observed handles):
{"tool":"fuel","args":{"building_handle":"e1","coal_count":3}}
{"tool":"collect_output","args":{"furnace_handle":"e2","plate_count":100}}
{"tool":"store_plates","args":{"chest_handle":"e3","plate_count":100}}
{"tool":"wait","args":{}}
Tools:
'''+bridge.prompt()
config = {'controller': args.controller, 'mode': 'maintenance_development', 'not_comparable_to_construction': True,
          'model': metadata, 'backend': 'custom_rmsnorm' if norm_dispatch else 'pytorch_reference_no_custom_kernel',
          'custom_norm_modules': norm_dispatch.module_names if norm_dispatch else [], 'context_policy': 'history',
          'max_total_tokens': 8192, 'max_new_tokens': 256, 'do_sample': False, 'decision_interval_ticks': 900,
          'max_simulated_seconds': args.minutes*60, 'max_decisions': args.minutes*4, 'wall_time_limit_seconds': args.wall_seconds,
          'warmup_seconds': 60, 'target_plates_per_minute': 16, 'failure_rule': 'two_consecutive_exact_60_second_windows_below_16',
          'finish_tool': False, 'game_speed': 10, 'initial_fuel_per_machine': 3, 'refill_max_coal': 3,
          'carrying_limit': 100, 'system_prompt': system, 'fixture_origin_tick': origin,
          'starting_state_sha256': hashlib.sha256(state_text.encode()).hexdigest(),
          'source_hashes': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ('maintenance_agent.py', 'maintenance_tools.py', 'logistics_tools.py', 'factory_agent_tools.py', 'game_bridge.py', 'cuda_review.py', 'qwen_rmsnorm_backend.py')}}
(run/'config.json').write_text(json.dumps(config, indent=2)+'\n')
messages = [{'role': 'system', 'content': system}]
latest = {'observation': bridge.observation(), 'elapsed_ticks': 0}
events = []
failed = 0
history_pairs_trimmed = 0
stop = 'survived_simulation_limit'
started = time.monotonic()


def scripted_action(obs):
    equipment = obs['equipment']
    burners = [e for e in equipment if 'burner' in e and e['burner']['coal_in_fuel_inventory'] <= 1]
    if burners:
        # Current observations only. Prioritize the least stored fuel; ties
        # prioritize the drill, whose fuel consumption is higher.
        entity = min(burners, key=lambda e: (e['burner']['coal_in_fuel_inventory'], e['name'] != 'burner-mining-drill'))
        return {'tool': 'fuel', 'args': {'building_handle': entity['handle'], 'coal_count': 3}}
    if obs['carrying']['carried_plates']:
        chest = next(e for e in equipment if e['name'] == 'wooden-chest')
        return {'tool': 'store_plates', 'args': {'chest_handle': chest['handle'], 'plate_count': 100}}
    for entity in equipment:
        if entity['name'] == 'stone-furnace' and entity['output_storage']['iron_plates'] >= 60:
            return {'tool': 'collect_output', 'args': {'furnace_handle': entity['handle'], 'plate_count': 100}}
    return {'tool': 'wait', 'args': {}}


with (run/'steps.jsonl').open('w', buffering=1) as log:
    for step in range(args.minutes*4):
        if time.monotonic()-started >= args.wall_seconds:
            stop = 'wall_time_limit_incomplete'; break
        input_tokens = output_tokens = 0
        latency = 0
        before = bridge.tick()
        if args.controller == 'model':
            prompt_messages = messages+[{'role': 'user', 'content': json.dumps(latest, default=str)}]
            while True:
                inputs = tokenizer.apply_chat_template(prompt_messages, tokenize=True, add_generation_prompt=True, return_tensors='pt', return_dict=True)
                if inputs['input_ids'].shape[-1] <= 8192-256: break
                if len(messages) <= 1: raise RuntimeError('Essential context exceeds budget')
                del messages[1:3]
                history_pairs_trimmed += 1
                prompt_messages = messages+[{'role': 'user', 'content': json.dumps(latest, default=str)}]
            inputs = inputs.to('cuda')
            input_tokens = inputs['input_ids'].shape[-1]
            torch.cuda.synchronize(); inference_start = time.perf_counter()
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=256, do_sample=False, pad_token_id=tokenizer.eos_token_id,
                    stopping_criteria=StoppingCriteriaList([StopAfterObject(input_tokens)]))
            torch.cuda.synchronize()
            latency = time.perf_counter()-inference_start
            tokens = output[0, input_tokens:]
            output_tokens = len(tokens)
            response = tokenizer.decode(tokens, skip_special_tokens=True).strip()
        else:
            response = json.dumps(scripted_action(latest['observation']) if args.controller == 'scripted' else {'tool': 'wait', 'args': {}})
        if bridge.tick() != before:
            raise RuntimeError('World advanced during reasoning')
        action = None; error = None
        try:
            action = json.loads(response)
            result = bridge.action(action)
        except Exception as exc:
            failed += 1; error = f'{type(exc).__name__}: {exc}'
            result = {'error': error}
        # All permitted maintenance operations must be instantaneous while
        # paused. Advance even after invalid actions, preventing time-free stalls.
        if bridge.tick() != before:
            raise RuntimeError('Action violated the fixed simulation cadence')
        if bridge.advance(15) != 900:
            raise RuntimeError('Wrong decision interval')
        observation = bridge.observation()
        total_plates = instance.namespace._get_production_stats()['output'].get('iron-plate', 0)
        window = monitor.sample(bridge.tick(), total_plates)
        if window:
            print('WINDOW '+json.dumps(window), flush=True)
        event = {'step': step, 'response': response, 'action': action, 'result': result, 'error': error,
                 'failed_action': error is not None, 'input_tokens': input_tokens, 'output_tokens': output_tokens,
                 'response_seconds': latency, 'elapsed_ticks': bridge.tick()-origin, 'observation': observation,
                 'measurement_window': window, 'history_pairs_trimmed_total': history_pairs_trimmed,
                 'prompt_messages': prompt_messages if args.controller == 'model' else None}
        events.append(event); log.write(json.dumps(event, default=str)+'\n')
        print(f'STEP {step}: {response} | error={error}', flush=True)
        if args.controller == 'model':
            messages.extend([{'role': 'user', 'content': json.dumps(latest, default=str)}, {'role': 'assistant', 'content': response}])
        latest = {'result': result, 'observation': observation, 'elapsed_ticks': bridge.tick()-origin,
                  'recent_production_windows': monitor.windows[-2:]}
        if monitor.failed:
            stop = 'sustained_production_failure'; break
final = bridge.observation()
evidence = {'empty_and_expired_burners': [e['handle'] for e in final['equipment'] if 'burner' in e and e['burner']['coal_in_fuel_inventory'] == 0 and e['burner']['remaining_burning_fuel_joules'] <= 0],
            'full_furnace_outputs': [e['handle'] for e in final['equipment'] if e['name'] == 'stone-furnace' and e['output_storage']['free_plate_capacity'] == 0],
            'reserve_coal': final['inventory'].get('coal', 0),
            'note': 'Observed bottleneck indicators, not a causal proof; fuel reserve exhaustion is distinct from missed refueling.'}
latencies = [e['response_seconds'] for e in events]
summary = {'mode': config['mode'], 'controller': args.controller, 'stop_reason': stop, 'failed_actions': failed,
           'steps': len(events), 'simulated_seconds': (bridge.tick()-origin)/60, 'wall_seconds': time.monotonic()-started,
           'time_to_sustained_failure_seconds': (bridge.tick()-origin)/60 if monitor.failed else None,
           'first_low_window_end_seconds': (next((w['end_tick'] for w in monitor.windows if w['below_target']), origin)-origin)/60 if any(w['below_target'] for w in monitor.windows) else None,
           'survived_at_least_seconds': (bridge.tick()-origin)/60 if not monitor.failed else None,
           'measurement_windows': monitor.windows, 'failure_indicators': evidence, 'final_observation': final,
           'tokens': {'input_total': sum(e['input_tokens'] for e in events), 'output_total': sum(e['output_tokens'] for e in events)},
           'median_response_seconds': statistics.median(latencies) if latencies else None,
           'gpu_peak_allocated_bytes': torch.cuda.max_memory_allocated() if model is not None else None,
           'custom_cuda_used': False, 'backend': config['backend']}
summary['history_pairs_trimmed_total'] = history_pairs_trimmed
(run/'summary.json').write_text(json.dumps(summary, indent=2, default=str)+'\n')
print('SUMMARY '+json.dumps(summary, default=str), flush=True)
