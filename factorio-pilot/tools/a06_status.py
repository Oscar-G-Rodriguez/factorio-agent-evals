"""Compact read-only workflow check. No model, GPU or game connection."""
import argparse
import json
from pathlib import Path


def inspect(runtime):
    pointer = runtime/'artifacts/a06-autonomous-state.json'
    state = json.loads(pointer.read_text())
    pid = state['pid']
    proc = Path('/proc')/str(pid)
    alive = False
    if proc.exists():
        stat = (proc/'stat').read_text().split()
        command = (proc/'cmdline').read_bytes().split(b'\0')
        alive = (stat[2] != 'Z' and stat[21] == str(state['process_start_ticks'])
                 and [s.decode() for s in command if s] == state['argv'])
    status_path = Path(state['run'])/'status.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    return {'stage':state['stage'],'worker_alive_identity_verified':alive,'phase':status.get('phase','not_yet_recorded'),
            'round':status.get('round'),'optimizer_steps':status.get('optimizer_steps'),
            'steps':status.get('steps'),'latest':status.get('latest'),'error':status.get('error'),
            'run':state['run'],'next_stage':state['next_stage'],'final_tests_opened':state['final_tests_opened']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-home',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.runtime_home.resolve()),allow_nan=False))
