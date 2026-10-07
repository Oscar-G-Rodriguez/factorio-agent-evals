"""Execute one train-only correction from an exact native pre-action save."""
import argparse
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
from a06_workflow import read,write,sha,pause_requested


def inventory(client):
    return json.loads(client.send_command('''/sc local seen={}; local paths={}; local tables={};
local function inspect(t,path)
 if seen[t] then return end; seen[t]=true;
 local scalar_count=0; local function_count=0; local table_count=0;
 for k,v in pairs(t) do
  local next_path=path..'.'..tostring(k);
  if type(v)=='function' then table.insert(paths,next_path); function_count=function_count+1;
  elseif type(v)=='table' then table_count=table_count+1; inspect(v,next_path);
  else scalar_count=scalar_count+1; end;
 end;
 table.insert(tables,{path=path,scalar_count=scalar_count,function_count=function_count,table_count=table_count});
end;
inspect(storage,'storage'); table.sort(paths); rcon.print(helpers.table_to_json({paths=paths,tables=tables}));'''))


def addressed(label,action,before,after,result):
    if not isinstance(result,dict): return False
    if action['tool']=='fuel':
        previous=next(e for e in before['equipment'] if e['handle']==action['args']['building_handle'])
        current=next(e for e in after['equipment'] if e['handle']==action['args']['building_handle'])
        return current['burner']['coal_in_fuel_inventory']>previous['burner']['coal_in_fuel_inventory']
    if action['tool'] in ('collect_output','store_plates'):
        return result.get('transferred',0)>0
    return False


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-home',type=Path,required=True)
    parser.add_argument('--fixture-run',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    args=parser.parse_args()
    from cuda_review import assert_review_current
    review=assert_review_current()
    from a06_context import project,validate_action
    from observation_policy import ObservationPolicy
    from a06_episode import relative_windows
    from a06_fixture_controls import await_restore,physical_snapshot,scripted_action
    from maintenance_tools import MaintenanceBridge,ProductionMonitor
    from fle.env import FactorioInstance
    root=Path(__file__).resolve().parents[2];runtime=args.runtime_home.resolve()
    parent=read(root/'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    candidate=read(args.candidate)
    episode=Path(candidate['episode']).resolve();controls=args.fixture_run.resolve()
    if episode.parent!=runtime/'runs' or controls.parent!=runtime/'runs': raise ValueError('External source escapes runtime')
    source_config=read(episode/'config.json');fixture=source_config['fixture']
    if fixture['partition']!='train' or source_config['purpose']!='train-diagnostic' or fixture not in parent['fixtures']:
        raise ValueError('Train-only correction lineage required')
    if read(controls/'config.json')['fixture']!=fixture or sha(episode/'steps.jsonl')!=candidate['trace_sha256']:
        raise ValueError('Candidate trace/fixture changed')
    traces=[json.loads(line) for line in (episode/'steps.jsonl').read_text().splitlines()]
    original=traces[candidate['step']]
    if original['teacher_proposal']!=candidate['target_action'] or original['physical_before'] is None:
        raise ValueError('Missing actual pre-action state or mismatched teacher proposal')
    validate_action(candidate['target_action'],original['agent_visible_input'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run=runtime/'runs'/('A06-'+fixture['id']+'-controls-correction-'+stamp)
    run.mkdir();(run/'source').mkdir()
    for name in ('a06_correction_replay.py','a06_corrections.py','a06_context.py','a06_workflow.py',
                 'maintenance_tools.py','logistics_tools.py','factory_agent_tools.py','game_bridge.py','a06_fixture_controls.py'):
        (run/'source'/name).write_bytes(Path(__file__).with_name(name).read_bytes())
    write(run/'config.json',{'fixture':fixture,'protocol_sha256':sha(root/'factorio-pilot/protocols/a06-qwen-sft-v1.json'),
          'candidate':candidate,'task':parent['task'],'model_loaded':False,'native_source_hashes':review['source_hashes'],
          'source_hashes':{p.name:sha(p) for p in (run/'source').iterdir()}})
    print('RUN '+str(run),flush=True)
    instance=FactorioInstance(address='127.0.0.1',tcp_port=27000,fast=True,reset_speed=10,reset_paused=True)
    bridge=MaintenanceBridge(instance,game_speed=10,carry_limit=100)
    await_restore(instance,bridge,read(controls/'fixture_snapshot.json'),'initial',run/'initial_restore.json')
    origin=bridge.tick();start_plates=instance.namespace._get_production_stats()['output'].get('iron-plate',0)
    monitor=ProductionMonitor(origin,start_plates)
    visibility=ObservationPolicy('automatic',bridge.observation(),0)
    # Replay actual model decisions, including failed attempts, with original cadence.
    for row in traces[:candidate['step']]:
        if physical_snapshot(bridge)!=row['physical_before'] or project(visibility.visible(bridge.tick()-origin))!=row['agent_visible_input']:
            raise RuntimeError('Actual prefix did not reproduce exact state and visible input')
        action=row['action'];error=None;result=None
        try:
            validate_action(action,row['agent_visible_input']);result=bridge.action(action)
        except (ValueError,TypeError,KeyError) as exc: error=str(exc)
        if (error is not None)!=row['failed_action']: raise RuntimeError('Replayed failure classification changed')
        if bridge.advance(15)!=900: raise RuntimeError('Replay cadence mismatch')
        observed=bridge.observation();total=instance.namespace._get_production_stats()['output'].get('iron-plate',0)
        monitor.sample(bridge.tick(),total)
        visibility.update(observed,bridge.tick()-origin,action,result,error,relative_windows(monitor.windows,origin))
    expected=physical_snapshot(bridge)
    if expected!=original['physical_before'] or project(visibility.visible(bridge.tick()-origin))!=original['agent_visible_input']:
        raise RuntimeError('Candidate exact pre-action state did not reproduce')
    write(run/'fixture_snapshot.json',expected)
    write(run/'storage_function_inventory.json',inventory(instance.rcon_client))
    print('SAVE_HELPER_INSPECTION_REQUIRED',flush=True)
    if sys.stdin.readline().strip()!='SAVE': raise RuntimeError('Save helper preparation not acknowledged')
    name='a06_'+fixture['id']+'_correction_'+stamp
    instance.rcon_client.send_command('/sc game.server_save('+json.dumps(name)+')')
    print('NATIVE_SAVE '+name+'.zip',flush=True)
    await_restore(instance,bridge,expected,'candidate',run/'candidate_restore.json')
    before=bridge.observation();target=candidate['target_action'];validate_action(target,original['agent_visible_input'])
    result=bridge.action(target);after=bridge.observation()
    repaired=addressed(candidate['problem'],target,before,after,result)
    write(run/'corrective_action.json',{'action':target,'before':before,'after':after,'result':result,'addressed':repaired})
    # Monitor retains the model prefix and its low-window streak; correction cannot erase it.
    started=time.monotonic();stop='survived_simulation_limit';step=candidate['step'];first=True
    with (run/'continuation.jsonl').open('x',buffering=1) as log:
        while step<parent['task']['max_decisions']:
            if pause_requested(runtime): stop='user_pause_incomplete';break
            if time.monotonic()-started>=parent['task']['wall_time_limit_seconds']: stop='wall_time_limit_incomplete';break
            action=target if first else scripted_action(bridge.observation())
            action_result=result if first else bridge.action(action)
            first=False
            if bridge.advance(15)!=900: raise RuntimeError('Correction cadence mismatch')
            total=instance.namespace._get_production_stats()['output'].get('iron-plate',0)
            window=monitor.sample(bridge.tick(),total)
            log.write(json.dumps({'step':step,'action':action,'result':action_result,'tick':bridge.tick(),'new_plates':total-start_plates,'window':window})+'\n')
            step+=1
            if monitor.failed: stop='sustained_production_failure';break
    survived=stop=='survived_simulation_limit' and step==80 and bridge.tick()-origin==72000
    proof={'candidate':candidate,'target_action':target,'exact_pre_action_restore':True,
        'corrective_action_executed':True,'observed_problem_addressed':bool(repaired),
        'full_horizon_survived':survived,'accepted':bool(repaired and survived),'stop_reason':stop,
        'final_tick':bridge.tick(),'origin_tick':origin,'measurement_windows':monitor.windows,
        'continuation_sha256':sha(run/'continuation.jsonl'),'action_receipt_sha256':sha(run/'corrective_action.json'),
        'candidate_restore_sha256':sha(run/'candidate_restore.json'),'native_save_sha256':sha(run/'native_save.json')}
    write(run/'correction_verification.json',proof)
    print('CORRECTION_COMPLETE '+json.dumps({'run':str(run),'accepted':proof['accepted'],'stop_reason':stop}),flush=True)


if __name__=='__main__': main()
