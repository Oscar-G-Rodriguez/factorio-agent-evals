"""Compact read-only check for both historical probes and three-round workflow."""
import argparse,json
from pathlib import Path
from a06_workflow import read,alive


def inspect(runtime):
    state=read(runtime/'artifacts/a06-autonomous-state.json')
    if state['schema_version']==1:
        identity={k:state[k] for k in ('pid','process_start_ticks','argv')}
        status=read(Path(state['run'])/'status.json')
        return {'stage':state['stage'],'alive':alive(identity),'phase':status['phase'],'latest':status.get('latest'),'run':state['run']}
    result={'stage':state['stage'],'phase':state['phase'],'supervisor_alive':alive(state['supervisor']),
        'worker_alive':alive(state.get('worker')),'completed_jobs':len(state['completed_jobs']),
        'completed_training_rounds':len(state['training']),'selected':{c:r['selected_step'] for c,r in state['selected'].items()},
        'error':state.get('error'),'workflow':state['workflow'],'final_tests_opened':state['final_tests_opened']}
    if state.get('current_run'):
        path=Path(state['current_run'])/'status.json'
        if path.exists():
            current=read(path)
            result['current_worker']={k:current.get(k) for k in ('phase','optimizer_steps','latest','error')}
    if state.get('log') and Path(state['log']).exists():
        lines=Path(state['log']).read_text(errors='replace').splitlines()
        result['log_tail']=lines[-2:]
        batch=next((Path(line[6:]) for line in lines if line.startswith('BATCH ')),None)
        if batch and (batch/'results.json').exists():result['current_batch_completed_jobs']=len(read(batch/'results.json'))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-home',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(inspect(args.runtime_home.resolve()),allow_nan=False))
