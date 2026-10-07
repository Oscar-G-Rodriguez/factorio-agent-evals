"""CPU-only contract, selection, atomic state and process identity helpers."""
import fcntl
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


def protocol(root):
    path = root/'factorio-pilot/protocols/a06-three-round-v1.json'
    return read(path), sha(path)


def process_identity(pid):
    proc = Path('/proc')/str(pid)
    try:
        stat = (proc/'stat').read_text().rsplit(')',1)[1].split()
        if stat[0]=='Z': return None
        return {'pid':pid,'process_start_ticks':stat[19],
                'argv':[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s]}
    except (FileNotFoundError,ProcessLookupError):
        return None


def alive(identity):
    return bool(identity and process_identity(identity['pid'])==identity)


def gpu_lock(runtime):
    handle = (runtime/'a06-gpu-worker.lock').open('a')
    try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('Another GPU worker owns the runtime lock')
    return handle


def adapter_hashes(path):
    hashes = {name:sha(Path(path)/name) for name in ('adapter_config.json','adapter_model.safetensors')}
    return hashes


def selection(records):
    """Never rank incomplete episodes as survival or choose from test episodes."""
    grouped = {}
    for record in records:
        config, summary = record['config'],record['summary']
        if config['purpose']!='validation' or config['fixture']['partition']!='validation':
            raise ValueError('Checkpoint selection accepts validation only')
        if summary['stop_reason'] not in ('sustained_production_failure','survived_simulation_limit'):
            raise ValueError('Incomplete validation episode; no checkpoint selection')
        step = record['checkpoint_step']
        if step not in (20,40): raise ValueError('Noncandidate checkpoint')
        fixture = config['fixture']['id']
        group = grouped.setdefault(step,{})
        if fixture in group: raise ValueError('Duplicate validation episode')
        group[fixture]=summary
    expected = {'validation_fuel','validation_storage'}
    if set(grouped)!={20,40} or any(set(g)!=expected for g in grouped.values()):
        raise ValueError('Missing checkpoint/validation condition')
    scores = {step:{'mean_survival':sum(r['simulated_seconds'] for r in group.values())/2,
                   'new_plates':sum(r['new_iron_plates'] for r in group.values())}
              for step,group in grouped.items()}
    winner = max(scores,key=lambda step:(scores[step]['mean_survival'],scores[step]['new_plates'],-step))
    return {'selected_step':winner,'scores':scores,'test_used':False}


def partition_gate(fixture,purpose):
    expected = {'validation':'validation','train-diagnostic':'train','final-test':'test'}
    if purpose not in expected or fixture['partition']!=expected[purpose]:
        raise ValueError('Purpose/partition mismatch')


def pause_requested(runtime):
    return (runtime/'artifacts/a06-pause.request').exists()
