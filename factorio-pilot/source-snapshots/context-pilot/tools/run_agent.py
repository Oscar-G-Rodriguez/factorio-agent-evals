"""One local-model iron-production pilot with reproducible JSONL logs."""
import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from fle.env import FactorioInstance
from fle.commons.models.game_state import GameState
from game_bridge import GameBridge, PROTOTYPES
from context_memory import ContextMemory

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=('development', 'baseline', 'intervention'), required=True)
parser.add_argument('--steps', type=int, default=64)
parser.add_argument('--seed', type=int, default=42)
parser.add_argument('--context-policy', choices=('history', 'structured-memory'), default='history')
args = parser.parse_args()
if not 1 <= args.steps <= 64:
    raise ValueError('steps must be 1..64')
root = Path('/home/osci2/factorio-pilot')
artifacts = root / 'artifacts'
run = root / 'runs' / f'{args.mode}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-seed{args.seed}'
run.mkdir(parents=True)
log = (run / 'steps.jsonl').open('w', buffering=1)
metadata = json.loads((artifacts / 'model-revision.json').read_text())
torch.manual_seed(args.seed)
model = AutoModelForCausalLM.from_pretrained(
    metadata['snapshot_path'], torch_dtype=torch.bfloat16, device_map='cuda',
    attn_implementation='sdpa', local_files_only=True, trust_remote_code=False,
    use_safetensors=True,
).eval()
tokenizer = AutoTokenizer.from_pretrained(metadata['snapshot_path'], local_files_only=True)
instance = FactorioInstance(address='127.0.0.1', tcp_port=27000,
                            fast=True, reset_speed=10, reset_paused=True)
state_text = (artifacts / 'starting-state.json').read_text()
instance.reset(game_state=GameState.parse_raw(state_text))
instance.game_control.pause()
bridge = GameBridge(instance)
system = '''You control a Factorio factory using one JSON tool action per response.
Goal: automatically produce at least 16 iron plates per game minute in two
consecutive unattended 60-second windows after a 60-second warm-up.
Use the supplied mining drills, furnaces, inserters, chests, belts and coal.
Return exactly {"tool":"tool_name","args":{...}} with no prose or Markdown.
The environment pauses during reasoning. Movement unpauses the world at 10x
while the pathfinder runs; its actual ticks are logged. Each ordinary action
is then followed by one game second. wait advances its requested seconds;
done triggers evaluation.
Positions are {"x":number,"y":number}; directions are UP, RIGHT, DOWN, LEFT.
entity arguments are prototype names without Prototype.; nearest's type is
IronOre, Coal, or Stone. entities can be a list of prototype names.
Returned entity objects have handles such as e1: insert_item target and
rotate_entity/pickup_entity entity arguments use these handles.
Handle positions and drill drop_position are in observations.
move_to supports position only. Do not craft or manually insert ore to inflate output.
Extra tools: wait(seconds: integer 1..60), done(no arguments).
Available prototypes: ''' + ', '.join(PROTOTYPES) + '\n\n' + bridge.prompt()
initial = {'role': 'user', 'content': json.dumps(bridge.observation(), default=str)}
messages = [{'role': 'system', 'content': system}, initial]
memory = ContextMemory()
memory.update(bridge.observation(), valid_handles=bridge.handles)
config = {
    'mode': args.mode, 'seed': args.seed, 'max_decisions': args.steps,
    'wall_time_limit_seconds': 1800, 'sampling': {'do_sample': False},
    'max_total_sequence_tokens': 8192, 'max_new_tokens': 1024,
    'context_policy': args.context_policy,
    'history_trimming': 'keep_system_and_latest_observation; drop_oldest_complete_action_feedback_pairs',
    'memory_token_limit': 512 if args.context_policy == 'structured-memory' else 0,
    'interface': 'one_validated_JSON_call_per_decision', 'system_prompt': system,
    'starting_state_sha256': hashlib.sha256(state_text.encode()).hexdigest(),
    'model': metadata, 'precision': 'bfloat16', 'attention_backend': 'sdpa',
    'tick_policy': 'paused_during_inference; movement_unpaused_at_10x_with_actual_ticks_logged; ordinary_actions_add_60_ticks; wait_exact_requested_ticks',
    'greedy_seed_note': 'Different seeds do not create sampling diversity with do_sample=false.',
    'tool_subset_frozen_before_baseline': True,
    'pathfinder_poll_attempt_limit': os.environ.get('FLE_GETPATH_MAX_ATTEMPTS'),
    'actual_map_seed': int(instance.rcon_client.send_command('/sc rcon.print(game.surfaces[1].map_gen_settings.seed)').strip()),
    'source_hashes': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                      for name in ('run_agent.py', 'game_bridge.py', 'context_memory.py')},
}
if args.mode in ('baseline', 'intervention') and config['actual_map_seed'] != 2859378883:
    raise RuntimeError('Map seed differs from the frozen lab scenario seed 2859378883.')
if 'Call self as a function.' in system:
    raise RuntimeError('Incorrect tool documentation extraction.')
(run / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
failed = 0
stop = 'decision_limit'
start = time.monotonic()
print(f'RUN {run}', flush=True)
for step in range(args.steps):
    if time.monotonic() - start >= 1800:
        stop = 'wall_time_limit'
        break
    dropped = 0
    memory_text, memory_tokens = memory.render(tokenizer) if args.context_policy == 'structured-memory' else ('', 0)
    while True:
        inference_messages = [dict(message) for message in messages]
        if memory_text:
            inference_messages[-1]['content'] += '\nObserved-fact memory: ' + memory_text
        inputs = tokenizer.apply_chat_template(inference_messages, tokenize=True,
            add_generation_prompt=True, return_tensors='pt', return_dict=True)
        if inputs['input_ids'].shape[-1] <= 8192 - 1024:
            break
        if len(messages) <= 2:
            raise RuntimeError('Essential prompt exceeds the frozen token budget')
        del messages[1:3]
        dropped += 2
    inputs = inputs.to('cuda')
    before = bridge.tick()
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    generation_start = time.perf_counter()
    with torch.inference_mode():
        outputs = model.generate(**inputs, max_new_tokens=1024, do_sample=False,
                                 pad_token_id=tokenizer.eos_token_id)
    torch.cuda.synchronize()
    response_seconds = time.perf_counter() - generation_start
    tokens = outputs[0, inputs['input_ids'].shape[-1]:]
    response = tokenizer.decode(tokens, skip_special_tokens=True)
    if bridge.tick() != before:
        raise RuntimeError('World advanced while model was reasoning')
    action_start = time.perf_counter()
    error = None
    action = None
    try:
        action = json.loads(response)
        result = bridge.action(action)
        if action['tool'] not in ('wait', 'done'):
            bridge.advance(1)
    except Exception as exception:
        error = f'{type(exception).__name__}: {exception}'
        failed += 1
        result = {'error': error}
    observation = bridge.observation()
    memory.update(observation, action, error, valid_handles=bridge.handles)
    event = {
        'step': step, 'response': response, 'action': action, 'result': result,
        'failed_action': error is not None, 'error': error,
        'input_tokens': inputs['input_ids'].shape[-1], 'output_tokens': len(tokens),
        'generation_reached_token_limit': len(tokens) == 1024,
        'response_seconds': response_seconds,
        'environment_seconds': time.perf_counter() - action_start,
        'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
        'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
        'actual_game_ticks_before': before, 'actual_game_ticks_after': bridge.tick(),
        'fle_logical_elapsed_ticks': instance.game_control.get_elapsed_ticks(),
        'dropped_history_messages': dropped, 'observation': observation,
        'memory_tokens': memory_tokens, 'memory_text': memory_text,
    }
    log.write(json.dumps(event, default=str) + '\n')
    print(f'STEP {step}: {response.strip()} | error={error}', flush=True)
    messages += [{'role': 'assistant', 'content': response},
                 {'role': 'user', 'content': json.dumps({'result': result, 'observation': observation}, default=str)}]
    if error is None and action['tool'] == 'done':
        stop = 'model_done'
        break
before_eval = bridge.observation()
bridge.advance(60)
windows = []
for _ in range(2):
    before_stats = instance.namespace._get_production_stats()
    tick_start = bridge.tick()
    bridge.advance(60)
    after_stats = instance.namespace._get_production_stats()
    plates = after_stats['output'].get('iron-plate', 0) - before_stats['output'].get('iron-plate', 0)
    windows.append({'actual_ticks': bridge.tick() - tick_start, 'iron_plates': plates,
                    'before_stats': before_stats, 'after_stats': after_stats})
met = all(window['iron_plates'] >= 16 for window in windows)
summary = {'mode': args.mode, 'steps': step + 1, 'failed_actions': failed,
    'stop_reason': stop, 'wall_seconds': time.monotonic() - start,
    'measurement_windows': windows, 'throughput_target_met': met,
    'task_success': None if met else False,
    'automated_supply_chain_check': 'manual_inspection_required' if met else 'throughput_target_not_met',
    'pre_evaluation_factory': before_eval, 'final_factory': bridge.observation()}
(run / 'summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
(run / 'final-state.json').write_text(GameState.from_instance(instance).to_raw())
print('SUMMARY ' + json.dumps(summary, default=str), flush=True)
log.close()
