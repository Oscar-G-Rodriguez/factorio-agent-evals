"""Scaffolded development agent; never pooled with the frozen pilot."""
import argparse
import hashlib
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer,StoppingCriteria,StoppingCriteriaList
from factorio_rcon import RCONClient
from fle.env import FactorioInstance
from fle.commons.models.game_state import GameState
from game_bridge import GameBridge
from factory_agent_tools import FactoryBridge

parser=argparse.ArgumentParser()
parser.add_argument('--steps',type=int,default=32)
parser.add_argument('--visual',action='store_true')
parser.add_argument('--require-viewer',action='store_true')
parser.add_argument('--keep-visible-seconds',type=int,default=120)
args=parser.parse_args()
if not 1<=args.steps<=64 or not 0<=args.keep_visible_seconds<=600:
    raise ValueError('Invalid bounded development budget')
root=Path('/home/osci2/factorio-pilot')
artifacts=root/'artifacts'
run=root/'runs'/f'working-development-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}'
run.mkdir()
log=(run/'steps.jsonl').open('w',buffering=1)
print('RUN '+str(run),flush=True)
if args.require_viewer:
    client=RCONClient('127.0.0.1',27000,'factorio')
    deadline=time.monotonic()+120
    print('Waiting up to two minutes for a connected graphical viewer BEFORE loading FLE tools.',flush=True)
    while True:
        count=int(client.send_command('/sc local n=0; for _,p in pairs(game.players) do if p.connected then n=n+1 end end; rcon.print(n)').strip())
        if count>0:
            print(f'VIEWER_CONNECTED count={count}',flush=True)
            break
        if time.monotonic()>deadline:
            raise TimeoutError('No viewer connected; no FLE tools loaded. Reconnect and rerun.')
        time.sleep(1)
    client.close()

metadata=json.loads((artifacts/'model-revision.json').read_text())
torch.manual_seed(42)
model=AutoModelForCausalLM.from_pretrained(metadata['snapshot_path'],torch_dtype=torch.bfloat16,
    device_map='cuda',attn_implementation='sdpa',local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
tokenizer=AutoTokenizer.from_pretrained(metadata['snapshot_path'],local_files_only=True)
instance=FactorioInstance(address='127.0.0.1',tcp_port=27000,fast=True,reset_speed=1 if args.visual else 10,reset_paused=True)
state_text=(artifacts/'starting-state.json').read_text()
instance.reset(game_state=GameState.parse_raw(state_text))
instance.game_control.pause()
bridge=FactoryBridge(instance,visual=args.visual)
tick_origin=bridge.tick()
system='''You operate a Factorio factory. Return exactly ONE JSON object containing tool and args. No prose, no code fences, no second action.
Goal: automatically produce at least 16 iron plates per simulated minute.
The player ALREADY HAS 500 coal, drills and furnaces. There is no need to visit a coal deposit.
Basic factory knowledge: a burner mining drill on iron feeds ore from its output into an adjacent stone furnace. BOTH machines require coal. Supplied coal may be inserted; ore may NOT be inserted by hand.
Use find_iron, move to its returned position, place a RIGHT-facing drill over iron, place_furnace_at_output with that drill handle, then fuel each machine separately with 50 coal. Choose coordinates based on observations; do not invent handles. Building requires standing nearby. Once fueled, wait 60 seconds to test production. If insufficient, inspect and repair or build an additional chain. finish is accepted only after a successful test.
Examples of JSON SYNTAX (coordinates and handles are examples; use your actual observations):
{"tool":"find_iron","args":{}}
{"tool":"move","args":{"position":{"x":10,"y":20}}}
{"tool":"place_drill","args":{"position":{"x":10,"y":20},"direction":"RIGHT"}}
{"tool":"place_furnace_at_output","args":{"drill_handle":"e1"}}
{"tool":"fuel","args":{"building_handle":"e1","coal_count":50}}
{"tool":"fuel","args":{"building_handle":"e2","coal_count":50}}
{"tool":"wait","args":{"seconds":60}}
{"tool":"finish","args":{}}
Tool definitions:
'''+bridge.prompt()

class StopAfterObject(StoppingCriteria):
    def __init__(self,start): self.start=start
    def __call__(self,input_ids,scores,**kwargs):
        text=tokenizer.decode(input_ids[0,self.start:],skip_special_tokens=True).strip()
        if not text.startswith('{'): return False
        try:
            _,end=json.JSONDecoder().raw_decode(text)
            return end>0
        except json.JSONDecodeError: return False

config={'mode':'working-development','scaffold':'simplified_tools_plus_explicit_task_procedure_and_examples',
    'is_unassisted_planning':False,'not_comparable_to_frozen_pilot':True,'model':metadata,
    'max_decisions':args.steps,'max_new_tokens':256,'max_total_tokens':8192,'do_sample':False,
    'visual':args.visual,'keep_visible_seconds':args.keep_visible_seconds,
    'system_prompt':system,'starting_state_sha256':hashlib.sha256(state_text.encode()).hexdigest(),
    'actual_map_seed':int(instance.rcon_client.send_command('/sc rcon.print(game.surfaces[1].map_gen_settings.seed)').strip()),
    'source_hashes':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('working_agent.py','factory_agent_tools.py','game_bridge.py')},
    'world_observation_clock':'elapsed_ticks_from_reset','wall_time_limit_seconds':1800}
(run/'config.json').write_text(json.dumps(config,indent=2)+'\n')
messages=[{'role':'system','content':system}]
latest={'observation':bridge.observation(),'elapsed_ticks':0}
failed=0
stop='decision_limit'
started=time.monotonic()
for step in range(args.steps):
    if time.monotonic()-started>1800:
        stop='wall_time_limit'; break
    prompt_messages=messages+[{'role':'user','content':json.dumps(latest,default=str)}]
    while True:
        inputs=tokenizer.apply_chat_template(prompt_messages,tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True)
        if inputs['input_ids'].shape[-1]<=8192-256: break
        if len(messages)<=1: raise RuntimeError('Essential prompt exceeds token budget')
        del messages[1:3]
        prompt_messages=messages+[{'role':'user','content':json.dumps(latest,default=str)}]
    inputs=inputs.to('cuda')
    before=bridge.tick()
    torch.cuda.synchronize(); generation_start=time.perf_counter()
    with torch.inference_mode():
        output=model.generate(**inputs,max_new_tokens=256,do_sample=False,pad_token_id=tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([StopAfterObject(inputs['input_ids'].shape[-1])]))
    torch.cuda.synchronize()
    latency=time.perf_counter()-generation_start
    assert bridge.tick()==before,'World advanced during reasoning'
    tokens=output[0,inputs['input_ids'].shape[-1]:]
    response=tokenizer.decode(tokens,skip_special_tokens=True).strip()
    action=None; error=None
    try:
        action=json.loads(response)
        result=bridge.action(action)
        if action['tool'] not in ('wait','finish','check'):
            bridge.advance(1)
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        result={'error':error,'format_example':{'tool':'fuel','args':{'building_handle':'RETURNED_HANDLE','coal_count':50}}}
        failed+=1
    observation=bridge.observation()
    event={'step':step,'response':response,'action':action,'result':result,'error':error,
        'failed_action':error is not None,'input_tokens':inputs['input_ids'].shape[-1],
        'output_tokens':len(tokens),'response_seconds':latency,'observation':observation,
        'raw_observation':GameBridge.observation(bridge),'elapsed_ticks':bridge.tick()-tick_origin}
    log.write(json.dumps(event,default=str)+'\n')
    print(f'STEP {step}: {response} | error={error}',flush=True)
    messages.extend([{'role':'user','content':json.dumps(latest,default=str)}, {'role':'assistant','content':response}])
    latest={'result':result,'observation':observation,'elapsed_ticks':bridge.tick()-tick_origin}
    if error is None and action['tool']=='finish':
        stop='verified_finish_request';break
before_eval=GameBridge.observation(bridge)
bridge.advance(60)
windows=[]
for _ in range(2):
    stats=instance.namespace._get_production_stats(); tick=bridge.tick()
    bridge.advance(60)
    after=instance.namespace._get_production_stats()
    windows.append({'actual_ticks':bridge.tick()-tick,'iron_plates':after['output'].get('iron-plate',0)-stats['output'].get('iron-plate',0)})
met=all(w['actual_ticks']==3600 and w['iron_plates']>=16 for w in windows)
summary={'mode':'working-development','steps':step+1,'failed_actions':failed,'stop_reason':stop,
    'wall_seconds':time.monotonic()-started,'measurement_windows':windows,'throughput_target_met':met,
    'task_success':None if met else False,'automated_supply_chain_check':'audit_pending' if met else 'throughput_failed',
    'pre_evaluation_factory':before_eval,'final_factory':GameBridge.observation(bridge)}
(run/'summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
(run/'final-state.json').write_text(GameState.from_instance(instance).to_raw())
log.close()
print('SUMMARY '+json.dumps(summary,default=str),flush=True)
remaining=args.keep_visible_seconds if args.visual else 0
if remaining:
    print(f'MODEL_FINISHED: keeping the resulting factory visible for {remaining} seconds. No new model decisions occur during this viewing period.',flush=True)
    while remaining>0:
        seconds=min(60,remaining); bridge.advance(seconds);remaining-=seconds
    print('Viewing period complete; game paused.',flush=True)
