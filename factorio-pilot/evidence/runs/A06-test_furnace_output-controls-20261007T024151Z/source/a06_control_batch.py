"""Sequential supervisor for existing A06 native-save control barriers (Linux root)."""
import argparse, hashlib, json, os, queue, subprocess, threading, time
from datetime import datetime, timezone
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-home',type=Path,required=True)
    parser.add_argument('--owner',required=True)
    parser.add_argument('--fixtures',nargs='+',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Docker orchestration requires root; controller runs as owner')
    repo=Path(__file__).resolve().parents[2];tools=repo/'factorio-pilot/tools';runtime=args.runtime_home.resolve();py=runtime/'.venv/bin/python'
    registry=json.loads((repo/'factorio-pilot/protocols/a06-qwen-sft-v1.json').read_text())
    if len(set(args.fixtures))!=len(args.fixtures) or any(f not in {r['id'] for r in registry['fixtures']} for f in args.fixtures):raise ValueError('Unknown/duplicate fixture')
    env=dict(os.environ,FACTORIO_PILOT_HOME=str(runtime))
    batch=runtime/'batches'/('A06-controls-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));batch.mkdir(parents=True)
    def command(argv,user=False):
        if user:argv=['runuser','-u',args.owner,'--']+list(map(str,argv))
        result=subprocess.run(list(map(str,argv)),env=env,cwd=repo,capture_output=True,text=True,timeout=120)
        with (batch/'orchestration.log').open('a') as stream:stream.write(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Command failed: '+str(argv)+'\n'+result.stderr[-2000:])
        return result.stdout
    def server(mode,run=None,save=None):
        argv=[py,tools/'a06_native_server.py',mode,'--runtime-home',runtime,'--owner',args.owner]
        if run:argv+=['--run-name',run.name]
        if save:argv+=['--save-name',save]
        command(argv)
    def ready():
        import factorio_rcon
        deadline=time.monotonic()+60
        while True:
            client=None
            try:
                client=factorio_rcon.RCONClient('127.0.0.1',27000,os.environ.get('FACTORIO_RCON_PASSWORD','factorio'))
                result=client.send_command('/sc rcon.print(game.tick)')
                int(result.strip());return
            except Exception:
                if time.monotonic()>=deadline:raise
                time.sleep(1)
            finally:
                if client:client.close()
    results=[]
    try:
        server('default');ready()
        command(['docker','exec','-u','root','cluster-factorio_0-1','install','-d','-o','845','-g','845','-m','755','/factorio/saves'])
        for fixture in args.fixtures:
            print('FIXTURE_START '+fixture,flush=True)
            process=subprocess.Popen(['runuser','-u',args.owner,'--',str(py),'-u',str(tools/'a06_fixture_controls.py'),'--fixture',fixture],env=env,cwd=repo,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            messages=queue.Queue()
            def reader():
                for line in process.stdout:messages.put(line)
                messages.put(None)
            threading.Thread(target=reader,daemon=True).start()
            run=None;save=None;captured=False;deadline=time.monotonic()+1200
            try:
                with (batch/(fixture+'.log')).open('w') as log:
                    while True:
                        if time.monotonic()>deadline:raise TimeoutError('Control supervisor budget; do not relabel as game failure')
                        try:line=messages.get(timeout=5)
                        except queue.Empty:
                            if process.poll() is not None:break
                            continue
                        if line is None:break
                        log.write(line);log.flush();text=line.strip()
                        if text.startswith('RUN '):
                            candidate=Path(text[4:]).resolve()
                            if candidate.parent!=(runtime/'runs') or not candidate.name.startswith('A06-'+fixture+'-controls-'):raise RuntimeError('Unexpected controller run')
                            run=candidate
                            (run/'source/a06_control_batch.py').write_bytes(Path(__file__).read_bytes())
                        if text.startswith('NATIVE_SAVE '):save=text.split(' ',1)[1]
                        if text=='SAVE_HELPER_INSPECTION_REQUIRED':
                            command([py,tools/'a06_save_helpers.py','prepare','--run',run],True)
                            process.stdin.write('SAVE\n');process.stdin.flush()
                        elif text.startswith('RESTORE_REQUIRED '):
                            server('restore' if captured else 'capture-and-restore',run,None if captured else save);captured=True
                            ready();command([py,tools/'a06_save_helpers.py','restore','--run',run],True)
                            process.stdin.write('RESTORED\n');process.stdin.flush()
                        if '_WINDOW ' in text or '_SUMMARY ' in text or text.startswith('RESTORE_VERIFIED '):print(fixture+' '+text,flush=True)
                code=process.wait(timeout=10)
                record={'fixture':fixture,'run':str(run) if run else None,'exit_code':code,'supervisor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
                results.append(record)
                (batch/'results.json').write_text(json.dumps(results,indent=2)+'\n')
                if run:
                    (run/'supervision.json').write_text(json.dumps(record,indent=2)+'\n')
                    if code==0:command([py,repo/'scripts/package_a06_controls.py','--run',run,'--repo',repo],True)
                print('FIXTURE_DONE '+json.dumps(record),flush=True)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
    finally:
        server('default')
    print('BATCH_DONE '+str(batch),flush=True)
if __name__=='__main__':main()
