"""Bounded sequential three-round workflow. Root orchestrates; GPU jobs run as owner."""
import argparse
import fcntl
import json
import os
import pwd
import signal
import subprocess
import time
from datetime import datetime,timezone
from pathlib import Path
from a06_workflow import read,write,sha,protocol,process_identity,pause_requested,selection,adapter_hashes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-home',type=Path,required=True)
    parser.add_argument('--owner',required=True)
    parser.add_argument('--resume-workflow',type=Path)
    parser.add_argument('--preflight-run',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0: raise RuntimeError('Docker orchestration needs root; GPU workers run as owner')
    root=Path(__file__).resolve().parents[2];tools=root/'factorio-pilot/tools';runtime=args.runtime_home.resolve()
    plan,plan_hash=protocol(root)
    ownership=pwd.getpwnam(args.owner)
    pipeline_lock=(runtime/'a06-pipeline.lock').open('a')
    fcntl.flock(pipeline_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if pause_requested(runtime): raise RuntimeError('Pause request pending; explicitly resume before launching')
    py=runtime/'.venv-a06-train/bin/python'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    workflow=args.resume_workflow.resolve() if args.resume_workflow else runtime/'workflows'/('A06-three-round-'+stamp)
    if args.resume_workflow and workflow.parent!=runtime/'workflows': raise ValueError('Resume workflow escapes runtime')
    workflow.mkdir(parents=True,exist_ok=bool(args.resume_workflow));os.chown(workflow,ownership.pw_uid,ownership.pw_gid)
    pointer=runtime/'artifacts/a06-autonomous-state.json'
    if pointer.exists() and not args.resume_workflow: (workflow/'previous-workflow-pointer.json').write_bytes(pointer.read_bytes())
    sources={p.name:sha(p) for p in tools.glob('a06*.py')}
    sources['cuda_review.py']=sha(tools/'cuda_review.py')
    state={'schema_version':2,'stage':'preflight','phase':'running','workflow':str(workflow),'repo':str(root),
        'protocol_sha256':plan_hash,'source_hashes':sources,'started_utc':datetime.now(timezone.utc).isoformat(),
        'supervisor':process_identity(os.getpid()),'worker':None,'completed_jobs':[], 'training':{},'selected':{},
        'corrections':{},'training_attempts':[],'final_tests_opened':False,'rounds_required':3,'deadline_unix':time.time()+plan['limits']['total_wall_seconds']}
    if args.resume_workflow:
        previous=read(workflow/'state.json')
        if previous['protocol_sha256']!=plan_hash or previous['source_hashes']!=sources:
            raise ValueError('Resume protocol or sources changed')
        state=previous;state.update(supervisor=process_identity(os.getpid()),worker=None,phase='running')
        stamp=workflow.name.removeprefix('A06-three-round-')
    else:
        write(workflow/'protocol.json',plan)
        (workflow/'source').mkdir()
        for name in sources: (workflow/'source'/name).write_bytes((tools/name).read_bytes())
    current=[None]
    def persist():
        write(workflow/'state.json',state);write(pointer,state)
    def stop_signal(signum,frame):
        (runtime/'artifacts/a06-pause.request').touch()
        # Workers observe this request at their own safe boundary; do not kill
        # runuser, whose forced child cleanup can interrupt a checkpoint save.
    signal.signal(signal.SIGTERM,stop_signal);signal.signal(signal.SIGINT,stop_signal)
    persist();print('WORKFLOW '+str(workflow),flush=True)
    env=dict(os.environ,FACTORIO_PILOT_HOME=str(runtime))
    counter=[len(list(workflow.glob('*.log')))]
    def run(argv,label,user=False,timeout=900):
        if pause_requested(runtime): raise InterruptedError('User pause request')
        if time.time()>=state['deadline_unix']: raise TimeoutError('Total execution cap reached')
        if protocol(root)[1]!=plan_hash or any(sha(tools/name)!=expected for name,expected in sources.items()):
            raise RuntimeError('Frozen workflow sources/protocol changed')
        argv=list(map(str,argv))
        if user: argv=['runuser','-u',args.owner,'--']+argv
        counter[0]+=1;log_path=workflow/(f'{counter[0]:03d}-'+label+'.log')
        with log_path.open('x') as log:
            process=subprocess.Popen(argv,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            current[0]=process
            identity=None
            for _ in range(20):
                identity=process_identity(process.pid)
                if identity or process.poll() is not None: break
                time.sleep(.05)
            state.update(worker=identity,log=str(log_path),current_run=argv[argv.index('--run')+1] if '--run' in argv else None);persist()
            deadline=min(state['deadline_unix'],time.time()+timeout)
            while process.poll() is None:
                if time.time()>deadline:
                    process.terminate()
                    try: process.wait(timeout=60)
                    except subprocess.TimeoutExpired: process.kill();process.wait()
                    raise TimeoutError('Stage deadline; retained incomplete evidence')
                time.sleep(1)
            code=process.returncode
            current[0]=None;state['worker']=None;persist()
        return code,log_path
    def episode_jobs(jobs,label):
        results=[];pending=[]
        for job in jobs:
            existing=next((r for r in state['completed_jobs'] if r['job']==job and r['exit_code']==0),None)
            if existing and Path(existing['run']).exists():
                summary=Path(existing['run'])/'summary.json'
                if summary.exists() and read(summary)['stop_reason']=='user_pause_incomplete': existing=None
            if existing: results.append(existing)
            else: pending.append(job)
        if not pending:return results
        for attempt in range(2):
            job_path=workflow/(label+'-jobs-'+str(attempt)+'.json');write(job_path,pending)
            code,log=run([py,tools/'a06_episode_batch.py','--runtime-home',runtime,'--owner',args.owner,'--jobs',job_path],label+'-'+str(attempt),timeout=len(pending)*900+120)
            batch=None
            for line in log.read_text().splitlines():
                if line.startswith('BATCH '): batch=Path(line[6:])
            completed=read(batch/'results.json') if batch and (batch/'results.json').exists() else []
            successful=[r for r in completed if r['exit_code']==0]
            results+=successful;state['completed_jobs']+=successful;persist()
            pending=pending[len(successful):]
            if not pending:
                if code and not pause_requested(runtime): raise RuntimeError('Worker finished but server cleanup failed')
                break
            if pause_requested(runtime): raise InterruptedError('User pause request')
            if attempt==1: raise RuntimeError('Infrastructure stage failed after one retry')
        return results
    def model_jobs(fixtures,condition,purpose,adapter=None,lock=None):
        jobs=[]
        for fixture in fixtures:
            job={'fixture_run':str(runtime/'runs'/plan['fixtures'][fixture]),'condition':condition,'purpose':purpose}
            if adapter:job['adapter']=str(adapter)
            if lock:job['lock']=str(lock)
            jobs.append(job)
        return jobs
    train_fixtures=[name for name in plan['fixtures'] if name.startswith('train_')]
    val_fixtures=plan['selection']['fixtures']
    try:
        # GPU preflight is a separate two-update probe, never a production training round.
        probe=args.preflight_run.resolve() if args.preflight_run else runtime/'runs'/('A06-training-three-round-preflight-'+stamp)
        if probe.parent!=runtime/'runs':raise ValueError('Preflight run escapes runtime')
        if args.preflight_run:
            preflight_config=read(probe/'config.json')
            if preflight_config['config_sha256']!=plan_hash or any(sha(tools/name)!=expected for name,expected in preflight_config['source_hashes'].items()):
                raise ValueError('Preflight evidence belongs to different training sources/settings')
        if not (probe/'reload-verification.json').exists():
            code,log=run([py,'-u',tools/'a06_train.py','--runtime-home',runtime,'--run',probe,'--round','1',
                '--probe-optimizer-steps','2','--verify-reload'],'gpu-preflight',user=True,timeout=600)
            if code: raise RuntimeError('GPU preflight failed; no full baseline/training launched')
        if not read(probe/'reload-verification.json')['passed']: raise RuntimeError('GPU preflight missing')
        state['preflight_run']=str(probe);state.update(stage='baseline');persist()
        baseline=episode_jobs(model_jobs(train_fixtures,'unchanged_4bit','train-diagnostic')+
                              model_jobs(val_fixtures,'unchanged_4bit','validation'),'baseline')
        state['baseline']=baseline
        for round_number in range(1,4):
            condition=f'round{round_number}_4bit';state.update(stage=f'round{round_number}_training');persist()
            training=None
            if str(round_number) in state['training']:
                training=Path(state['training'][str(round_number)])
            for attempt in range(2):
                if training and (training/'status.json').exists() and read(training/'status.json')['phase']=='complete': break
                training=runtime/'runs'/(f'A06-training-round{round_number}-'+stamp+f'-attempt{attempt}')
                if str(training) not in state['training_attempts']:state['training_attempts'].append(str(training));persist()
                argv=[py,'-u',tools/'a06_train.py','--runtime-home',runtime,'--run',training,'--round',str(round_number)]
                if round_number>1:
                    argv+=['--initial-adapter',state['selected'][f'round{round_number-1}_4bit']['adapter'],
                           '--corrections',state['corrections'][str(round_number-1)]]
                if training.exists():
                    if any((p/'receipt.json').exists() for p in training.glob('checkpoint-*')): argv+=['--resume']
                    else: continue
                code,log=run(argv,f'train-round{round_number}-attempt{attempt}',user=True,timeout=plan['limits']['worker_wall_seconds']+120)
                if pause_requested(runtime): raise InterruptedError('User pause request; checkpoint saved')
                if code==0 and read(training/'status.json')['phase']=='complete': break
                if attempt==1: raise RuntimeError('Training failed after one infrastructure retry')
            state['training'][str(round_number)]=str(training)
            state.update(stage=f'round{round_number}_validation');persist()
            validation=[]
            for step in (20,40):
                checkpoint=training/f'checkpoint-{step}'
                records=episode_jobs(model_jobs(val_fixtures,condition,'validation',checkpoint),f'validation-r{round_number}-step{step}')
                for record in records:
                    episode=Path(record['run']);validation.append({'config':read(episode/'config.json'),
                        'summary':read(episode/'summary.json'),'checkpoint_step':step,'run':str(episode)})
            choice=selection(validation);adapter=training/('checkpoint-'+str(choice['selected_step']))
            state['selected'][condition]=choice|{'adapter':str(adapter),'sha256':adapter_hashes(adapter),'validation':validation}
            def selected_score(condition):
                selected=state['selected'][condition];step=selected['selected_step']
                score=selected['scores'].get(step) or selected['scores'][str(step)]
                return score['mean_survival'],score['new_plates'],-int(condition[5])
            state['best_validation_condition']=max(state['selected'],key=selected_score)
            persist()
            if round_number==3: break
            state.update(stage=f'round{round_number}_train_diagnostics');persist()
            diagnostics=episode_jobs(model_jobs(train_fixtures,condition,'train-diagnostic',adapter),f'diagnostic-r{round_number}')
            from a06_corrections import candidates
            correction_jobs=[]
            for record in diagnostics:
                episode=Path(record['run'])
                for candidate in candidates(episode,root):
                    path=workflow/(f'candidate-r{round_number}-'+candidate['fixture_id']+'-'+str(candidate['step'])+'.json')
                    write(path,candidate)
                    correction_jobs.append({'kind':'correction','candidate':str(path),'fixture_run':str(runtime/'runs'/plan['fixtures'][candidate['fixture_id']])})
            state.update(stage=f'round{round_number}_correction_verification');persist()
            if not correction_jobs: raise ValueError('No verified corrective opportunities; stop incomplete rather than manufacture another round')
            verified=episode_jobs(correction_jobs,f'corrections-r{round_number}')
            verification_paths=workflow/f'verifications-r{round_number}.json';write(verification_paths,[r['run'] for r in verified])
            release=runtime/'runs'/(f'A06-corrections-round{round_number}-'+stamp)
            if not release.exists():
                code,log=run([py,tools/'a06_corrections.py','--runtime-home',runtime,'--verifications',verification_paths,'--output',release],f'correction-release-r{round_number}',user=True,timeout=180)
                if code: raise ValueError('Corrective release did not meet verified-data gate; stop incomplete')
            # A resumed release is re-audited by the next training ingress.
            state['corrections'][str(round_number)]=str(release);persist()
        state.update(stage='final_lock');persist()
        final_lock=workflow/'final-lock.json'
        lock={'three_round_protocol_sha256':plan_hash,'adapters':state['selected'],
              'source_hashes':{name:sha(tools/name) for name in read(Path(state['selected']['round1_4bit']['validation'][0]['run'])/'config.json')['source_hashes']}}
        write(final_lock,lock);state['final_lock']=str(final_lock)
        state.update(stage='final_evaluation',final_tests_opened=True);persist()
        jobs=[]
        for condition in plan['final_evaluation']['conditions']:
            jobs+=model_jobs(plan['final_evaluation']['fixtures'],condition,'final-test',
                             Path(state['selected'][condition]['adapter']) if condition in state['selected'] else None,final_lock)
        state['final_results']=episode_jobs(jobs,'final-evaluation')
        state.update(stage='packaging',phase='running');persist()
        code,log=run([py,tools/'a06_package.py','--runtime-home',runtime,'--workflow',workflow],'packaging',user=True,timeout=180)
        if code: raise RuntimeError('Packaging failed; preserve all measurements')
        state.update(stage='measurements_complete',phase='complete',next_action='Audit report and tests; commit/push intended checkout and update Second Brain');persist()
    except Exception as error:
        state.update(phase='paused' if isinstance(error,InterruptedError) else 'incomplete',error_type=type(error).__name__,error=str(error)[-2000:],
            next_action='Inspect retained evidence; package partial results without claiming three-round completion')
        persist()
        print('WORKFLOW_STOP '+json.dumps({'stage':state['stage'],'phase':state['phase'],'error':state['error']}),flush=True)
        if not isinstance(error,InterruptedError): raise
    print('WORKFLOW_STATUS '+str(workflow),flush=True)


if __name__=='__main__': main()
