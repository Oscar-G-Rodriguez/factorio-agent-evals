"""A06 matched model episode; native restore barrier precedes scored actions."""
import argparse
import fcntl
import hashlib
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path


def write(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temp.replace(path)


def relative_windows(windows, origin):
    return [dict(w, start_tick=w['start_tick']-origin, end_tick=w['end_tick']-origin) for w in windows]


def maintenance_opportunity(observation):
    """Predeclared visible heuristic, not a causal verdict that waiting caused failure."""
    equipment = observation['equipment']
    return (any(e.get('burner', {}).get('coal_in_fuel_inventory', 99) <= 1 for e in equipment)
        or observation['carrying']['carried_plates'] > 0
        or any(e['name']=='stone-furnace' and e['output_storage']['iron_plates'] >= 60 for e in equipment))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-home', type=Path, required=True)
    parser.add_argument('--fixture-run', type=Path, required=True)
    parser.add_argument('--condition', choices=('unchanged_bf16','unchanged_4bit','round1_4bit','round2_4bit','round3_4bit'), required=True)
    parser.add_argument('--adapter', type=Path)
    parser.add_argument('--purpose', choices=('validation','train-diagnostic','final-test'), required=True)
    parser.add_argument('--lock', type=Path)
    args = parser.parse_args()
    from cuda_review import assert_review_current
    review = assert_review_current()
    from a06_context import project, render, canonical, validate_action
    from a06_workflow import partition_gate, pause_requested, protocol as workflow_protocol
    from a06_fixture_controls import await_restore, physical_snapshot, scripted_action
    from observation_policy import ObservationPolicy
    from maintenance_tools import MaintenanceBridge, ProductionMonitor
    from fle.env import FactorioInstance
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, StoppingCriteria, StoppingCriteriaList
    runtime = args.runtime_home.resolve()
    lock_handle = (runtime/'a06-gpu-worker.lock').open('a')
    fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    root = Path(__file__).resolve().parents[2]
    protocol_path = root/'factorio-pilot/protocols/a06-qwen-sft-v1.json'
    protocol = json.loads(protocol_path.read_text())
    controls = args.fixture_run.resolve()
    if controls.parent != runtime/'runs':
        raise ValueError('Fixture must reference an external control run')
    fixture = json.loads((controls/'config.json').read_text())['fixture']
    if fixture not in protocol['fixtures']: raise ValueError('Unknown fixture')
    partition_gate(fixture,args.purpose)
    if not json.loads((controls/'control_manifest.json').read_text())['scripted_reachability_passed']:
        raise ValueError('Unverified fixture')
    if args.condition.startswith('round') != bool(args.adapter):
        raise ValueError('Adapter condition mismatch')
    adapter_hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.adapter.iterdir()
                      if p.name in ('adapter_config.json','adapter_model.safetensors')} if args.adapter else {}
    if args.adapter and set(adapter_hashes) != {'adapter_config.json','adapter_model.safetensors'}:
        raise ValueError('Missing adapter files')
    if args.purpose == 'final-test':
        if not args.lock:
            raise ValueError('Final tests require both-adapter lock')
        frozen = json.loads(args.lock.read_text())
        if set(frozen['adapters']) != {'round1_4bit','round2_4bit','round3_4bit'}:
            raise ValueError('All three rounds must be locked')
        if args.adapter and frozen['adapters'][args.condition]['sha256'] != adapter_hashes:
            raise ValueError('Adapter changed after final lock')
        if frozen['three_round_protocol_sha256'] != workflow_protocol(root)[1]:
            raise ValueError('Final experiment configuration changed')
        for name,expected_hash in frozen['source_hashes'].items():
            if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=expected_hash:
                raise ValueError('Final experiment source changed')
    run = runtime/'runs'/('A06-episode-'+fixture['id']+'-'+args.condition+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir()
    source = run/'source'
    source.mkdir()
    names = ('a06_episode.py','a06_context.py','a06_fixture_controls.py','observation_policy.py',
             'maintenance_tools.py','logistics_tools.py','factory_agent_tools.py','game_bridge.py','cuda_review.py','a06_workflow.py')
    hashes = {}
    for name in names:
        data = Path(__file__).with_name(name).read_bytes()
        (source/name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    config = {'condition':args.condition,'purpose':args.purpose,'fixture':fixture,'fixture_control_run':str(controls),
              'adapter':str(args.adapter) if args.adapter else None,'adapter_sha256':adapter_hashes,
              'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
              'source_hashes':hashes,'native_source_hashes':review['source_hashes'],
              'task':protocol['task'],'custom_cuda_used':False,'attention':'sdpa','do_sample':False,
              'three_round_protocol_sha256':workflow_protocol(root)[1],
              'wait_opportunity_definition':'fuel stored <=1 OR carried plates >0 OR furnace output >=60; heuristic only'}
    write(run/'config.json', config)
    status = {'phase':'loading','pid':os.getpid(),'process_start_ticks':Path('/proc/self/stat').read_text().split()[21], 'run':str(run)}
    write(run/'status.json',status)
    print('RUN '+str(run),flush=True)
    try:
        metadata = json.loads((runtime/'artifacts/model-revision.json').read_text())
        snapshot = Path(metadata['snapshot_path'])
        if snapshot.name != protocol['model']['revision']:
            raise ValueError('Incorrect base model revision')
        torch.manual_seed(42)
        tokenizer = AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
        kwargs = dict(dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa',local_files_only=True,
                      trust_remote_code=False,use_safetensors=True)
        if args.condition != 'unchanged_bf16':
            kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16)
        model = AutoModelForCausalLM.from_pretrained(snapshot,**kwargs)
        if args.adapter:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model,args.adapter,is_trainable=False)
        model.eval().requires_grad_(False)
        model.config.use_cache = True
        guide = (root/protocol['context']['guide_path']).read_bytes().decode('utf-8')
        instance = FactorioInstance(address='127.0.0.1',tcp_port=27000,fast=True,reset_speed=10,reset_paused=True)
        bridge = MaintenanceBridge(instance,game_speed=10,carry_limit=100)
        expected = json.loads((controls/'fixture_snapshot.json').read_text())
        # Instance construction can initialize the world; restore AFTER construction.
        await_restore(instance,bridge,expected,'model',run/'native_restore.json')
        origin = bridge.tick()
        start_plates = instance.namespace._get_production_stats()['output'].get('iron-plate',0)
        total = start_plates
        monitor = ProductionMonitor(origin,start_plates)
        visibility = ObservationPolicy('automatic',bridge.observation(),0)
        history = []
        events = []
        started = time.monotonic()
        torch.cuda.reset_peak_memory_stats()
        status.update(phase='episode',steps=0)
        write(run/'status.json',status)
        stop = 'survived_simulation_limit'
        class StopAfterObject(StoppingCriteria):
            def __init__(self,start): self.start = start; self.first_token_time = None
            def __call__(self,input_ids,scores,**kwargs):
                text = tokenizer.decode(input_ids[0,self.start:],skip_special_tokens=True).strip()
                if self.first_token_time is None: self.first_token_time = time.perf_counter()
                if not text.startswith('{'): return False
                try: json.JSONDecoder().raw_decode(text); return True
                except json.JSONDecodeError: return False
        with (run/'steps.jsonl').open('x',buffering=1) as log:
            for step in range(protocol['task']['max_decisions']):
                if pause_requested(runtime): stop='user_pause_incomplete'; break
                if time.monotonic()-started >= protocol['task']['wall_time_limit_seconds']:
                    stop = 'wall_time_limit_incomplete'; break
                before = bridge.tick()
                physical_before = physical_snapshot(bridge) if args.purpose=='train-diagnostic' else None
                payload = project(visibility.visible(before-origin))
                render_start = time.perf_counter()
                messages, prompt_tokens, trimmed = render(guide,payload,history,tokenizer)
                inputs = tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True).to('cuda')
                render_seconds = time.perf_counter()-render_start
                torch.cuda.synchronize()
                inference_start = time.perf_counter()
                stopper = StopAfterObject(prompt_tokens)
                with torch.inference_mode():
                    output = model.generate(**inputs,max_new_tokens=256,do_sample=False,pad_token_id=tokenizer.eos_token_id,
                        stopping_criteria=StoppingCriteriaList([stopper]))
                torch.cuda.synchronize()
                generation_end = time.perf_counter()
                response_seconds = generation_end-inference_start
                tokens = output[0,prompt_tokens:]
                response = tokenizer.decode(tokens,skip_special_tokens=True).strip()
                action = None
                error = None
                result = None
                tool_start = time.perf_counter()
                try:
                    action = json.loads(response)
                    validate_action(action,payload)
                    result = bridge.action(action)
                except (ValueError,TypeError,KeyError) as exc:
                    error = type(exc).__name__+': '+str(exc)
                tool_seconds = time.perf_counter()-tool_start
                if bridge.tick() != before:
                    raise RuntimeError('Game advanced during inference/action')
                game_start = time.perf_counter()
                if bridge.advance(15) != 900:
                    raise RuntimeError('Cadence mismatch')
                game_seconds = time.perf_counter()-game_start
                observation = bridge.observation()
                total = instance.namespace._get_production_stats()['output'].get('iron-plate',0)
                window = monitor.sample(bridge.tick(),total)
                row = {'step':step,'tick_before':before,'tick_after':bridge.tick(),'elapsed_ticks':bridge.tick()-origin,
                    'agent_visible_input':payload,'prompt_messages':messages,'response':response,'action':action,
                    'result':result,'error':error,'failed_action':error is not None,'input_tokens':prompt_tokens,
                    'output_tokens':len(tokens),'response_seconds':response_seconds,'render_seconds':render_seconds,
                    'time_to_first_token_seconds':stopper.first_token_time-inference_start if stopper.first_token_time is not None else None,
                    'remaining_generation_seconds':generation_end-stopper.first_token_time if stopper.first_token_time is not None else None,
                    'tool_seconds':tool_seconds,'game_seconds':game_seconds,'history_pairs_trimmed':trimmed,
                    'wait_during_maintenance_opportunity':bool(isinstance(action,dict) and action.get('tool')=='wait' and maintenance_opportunity(payload['observation'])),
                    'observation_after':observation,'measurement_window':window,
                    'teacher_proposal':scripted_action(payload['observation']) if args.purpose=='train-diagnostic' else None}
                row['physical_before']=physical_before
                events.append(row)
                log.write(json.dumps(row,allow_nan=False,default=str)+'\n')
                # Malformed text has no representable JSON action. Disclose the omission rather than inventing an executed action.
                if isinstance(action,dict) and set(action)=={'tool','args'}:
                    history.append((payload,action)); history = history[-2:]
                visibility.update(observation,bridge.tick()-origin,action,result,error,relative_windows(monitor.windows,origin))
                status.update(phase='episode',steps=step+1,simulated_seconds=(bridge.tick()-origin)/60)
                write(run/'status.json',status)
                print('STEP '+str(step)+' '+response+' error='+str(error),flush=True)
                if monitor.failed:
                    stop = 'sustained_production_failure'; break
        summary = {'condition':args.condition,'purpose':args.purpose,'fixture_id':fixture['id'],'stop_reason':stop,
            'steps':len(events),'simulated_seconds':(bridge.tick()-origin)/60,'wall_seconds':time.monotonic()-started,
            'new_iron_plates':total-start_plates,'failed_actions':sum(e['failed_action'] for e in events),
            'failed_action_rate':sum(e['failed_action'] for e in events)/len(events) if events else None,
            'waits_during_maintenance_opportunity':sum(e['wait_during_maintenance_opportunity'] for e in events),
            'input_tokens':sum(e['input_tokens'] for e in events),'output_tokens':sum(e['output_tokens'] for e in events),
            'median_response_seconds':statistics.median(e['response_seconds'] for e in events) if events else None,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
            'measurement_windows':monitor.windows,'final_physical_snapshot':physical_snapshot(bridge),
            'custom_cuda_used':False,'inference_paused_game_time':True,'no_manual_ore_insertion':True}
        write(run/'summary.json',summary)
        status.update(phase='complete',passed=True,summary=summary)
        write(run/'status.json',status)
        print('EPISODE_COMPLETE '+json.dumps(summary),flush=True)
    except Exception as exc:
        status.update(phase='failed',passed=False,error_type=type(exc).__name__,error=str(exc)[-2000:])
        write(run/'status.json',status)
        raise


if __name__ == '__main__':
    main()
