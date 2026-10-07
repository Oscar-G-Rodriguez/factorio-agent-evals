"""Sequential native-restore supervisor; model workers run as the ordinary owner."""
import argparse
import fcntl
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-home', type=Path, required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--jobs', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Supervisor needs Docker access; model runs as ordinary owner')
    runtime = args.runtime_home.resolve()
    repo = Path(__file__).resolve().parents[2]
    tools = repo/'factorio-pilot/tools'
    py = runtime/'.venv-a06-train/bin/python'
    env = dict(os.environ,FACTORIO_PILOT_HOME=str(runtime))
    jobs = json.loads(args.jobs.read_text())
    if not isinstance(jobs,list) or not jobs or len(jobs) > 16:
        raise ValueError('Expected 1..16 sequential jobs')
    batch = runtime/'batches'/('A06-episodes-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    batch.mkdir(parents=True)
    (batch/'jobs.json').write_bytes(args.jobs.read_bytes())
    print('BATCH '+str(batch),flush=True)
    from a06_workflow import pause_requested
    server_lock=(runtime/'a06-server-worker.lock').open('a')
    fcntl.flock(server_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def command(argv,user=False):
        argv = list(map(str,argv))
        if user: argv = ['runuser','-u',args.owner,'--']+argv
        result = subprocess.run(argv,env=env,cwd=repo,capture_output=True,text=True,timeout=120)
        with (batch/'orchestration.log').open('a') as log: log.write(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError('Orchestration command failed: '+result.stderr[-2000:])
    def server(mode,controls=None,save=None):
        argv = [py,tools/'a06_native_server.py',mode,'--runtime-home',runtime,'--owner',args.owner]
        if controls: argv += ['--run-name',controls.name]
        if save: argv += ['--save-name',save]
        command(argv)
    def ready():
        import factorio_rcon
        deadline = time.monotonic()+60
        while True:
            client = None
            try:
                client = factorio_rcon.RCONClient('127.0.0.1',27000,os.environ.get('FACTORIO_RCON_PASSWORD','factorio'))
                int(client.send_command('/sc rcon.print(game.tick)').strip()); return
            except Exception:
                if time.monotonic() >= deadline: raise
                time.sleep(1)
            finally:
                if client: client.close()
    records = []
    process = None
    try:
        server('default'); ready()
        for index,job in enumerate(jobs):
            if pause_requested(runtime): print('BATCH_PAUSED',flush=True); break
            kind=job.get('kind','model')
            allowed = {'fixture_run','candidate','kind'} if kind=='correction' else {'fixture_run','condition','purpose','adapter','lock','kind'}
            required={'fixture_run','candidate'} if kind=='correction' else {'fixture_run','condition','purpose'}
            if kind not in ('model','correction') or not isinstance(job,dict) or set(job)-allowed or not required <= set(job):
                raise ValueError('Unknown/missing job fields')
            controls = Path(job['fixture_run']).resolve()
            if controls.parent != runtime/'runs' or not controls.name.startswith('A06-'):
                raise ValueError('Control run escapes external runtime')
            worker='a06_correction_replay.py' if kind=='correction' else 'a06_episode.py'
            argv = ['runuser','-u',args.owner,'--',str(py),'-u',str(tools/worker),'--runtime-home',str(runtime)]
            for key,value in job.items():
                if key!='kind': argv += ['--'+key.replace('_','-'),str(value)]
            process = subprocess.Popen(argv,env=env,cwd=repo,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,text=True,bufsize=1)
            messages = queue.Queue()
            def reader(pipe=process.stdout):
                for line in pipe: messages.put(line)
                messages.put(None)
            threading.Thread(target=reader,daemon=True).start()
            run = None
            save_name=None
            deadline = time.monotonic()+900
            with (batch/('job-'+str(index)+'.log')).open('x',buffering=1) as log:
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError('Episode supervisor deadline; classify incomplete')
                    try: line = messages.get(timeout=3)
                    except queue.Empty:
                        if process.poll() is not None: break
                        continue
                    if line is None: break
                    log.write(line)
                    text = line.strip()
                    if text.startswith('RUN '):
                        run = Path(text[4:]).resolve()
                        if run.parent != runtime/'runs' or not (run.name.startswith('A06-episode-') or kind=='correction' and '-controls-correction-' in run.name):
                            raise RuntimeError('Unexpected episode output')
                    elif text=='SAVE_HELPER_INSPECTION_REQUIRED':
                        command([py,tools/'a06_save_helpers.py','prepare','--run',run],True)
                        process.stdin.write('SAVE\n');process.stdin.flush()
                    elif text.startswith('NATIVE_SAVE '): save_name=text.split(' ',1)[1]
                    elif text.startswith('RESTORE_REQUIRED '):
                        target=run if kind=='correction' and text.endswith('candidate') else controls
                        server('capture-and-restore' if target==run else 'restore',target,save_name if target==run else None); ready()
                        command([py,tools/'a06_save_helpers.py','restore','--run',target],True)
                        process.stdin.write('RESTORED\n'); process.stdin.flush()
                    if text.startswith(('EPISODE_COMPLETE ','RESTORE_VERIFIED ','CORRECTION_COMPLETE ')):
                        print(text,flush=True)
            code = process.wait(timeout=10)
            receipt = {'job':job,'run':str(run) if run else None,'exit_code':code,
                       'supervisor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
            if run:
                (run/'source/a06_episode_batch.py').write_bytes(Path(__file__).read_bytes())
                (run/'supervision.json').write_text(json.dumps(receipt,indent=2)+'\n')
            records.append(receipt)
            (batch/'results.json').write_text(json.dumps(records,indent=2)+'\n')
            if code: raise RuntimeError('Episode worker failed; inspect retained log')
            print('JOB_DONE '+json.dumps(receipt),flush=True)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        server('default')
    print('BATCH_COMPLETE '+str(batch),flush=True)


if __name__ == '__main__':
    main()
