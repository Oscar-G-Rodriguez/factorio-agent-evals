"""Host orchestration: archive or reload the observed A06 native save only."""
import argparse
import hashlib
import json
import os
import pwd
import subprocess
import zipfile
from pathlib import Path
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['capture-and-restore', 'restore', 'default'])
parser.add_argument('--run-name')
parser.add_argument('--save-name')
parser.add_argument('--runtime-home', type=Path, required=True)
parser.add_argument('--owner', required=True)
parser.add_argument('--container', default='cluster-factorio_0-1')
args = parser.parse_args()
runtime = args.runtime_home.resolve()
compose = runtime / 'cluster/compose.yaml'
if args.mode == 'default':
    subprocess.run(['docker', 'compose', '-f', str(compose), 'up', '-d', '--force-recreate', 'factorio_0'], check=True)
    raise SystemExit()
run = (runtime / 'runs' / args.run_name).resolve()
if run.parent != runtime / 'runs' or not run.name.startswith('A06-train_drill-controls-'):
    raise ValueError('Run must be an observed A06 train_drill control directory')
config = json.loads((run / 'config.json').read_text())
if config['fixture']['id'] != 'train_drill':
    raise ValueError('Unexpected fixture')
native = runtime / 'native-fixtures' / run.name
override = run / 'native-server.override.yaml'
if args.mode == 'capture-and-restore':
    if not args.save_name or '/' in args.save_name or not args.save_name.startswith('a06_train_drill_') or not args.save_name.endswith('.zip'):
        raise ValueError('Unsafe or unexpected save basename')
    native.mkdir(parents=True, exist_ok=False)
    uid = pwd.getpwnam(args.owner).pw_uid
    os.chown(native, uid, 845)
    os.chmod(native, 0o2775)
    target = native / 'initial.zip'
    subprocess.run(['docker', 'cp', args.container + ':/factorio/saves/' + args.save_name, str(target)], check=True)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Corrupt native save')
    os.chown(target, uid, 845)
    os.chmod(target, 0o664)
    original = yaml.safe_load(compose.read_text())['services']['factorio_0']['command']
    needle = '--start-server-load-scenario default_lab_scenario'
    if original.count(needle) != 1:
        raise RuntimeError('Unexpected original server command')
    saved_command = original.replace(needle, '--start-server /factorio/saves/initial.zip')
    override.write_text(yaml.safe_dump({'services': {'factorio_0': {'command': saved_command,
        'volumes': [{'type': 'bind', 'source': str(native), 'target': '/factorio/saves'}]}}}))
    receipt = {'native_save_filename': args.save_name, 'archive_relative_to_runtime': str(target.relative_to(runtime)),
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size,
        'zip_integrity_passed': True, 'original_compose_sha256': hashlib.sha256(compose.read_bytes()).hexdigest()}
    (run / 'native_save.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (run / 'source' / 'a06_native_server.py').write_bytes(Path(__file__).read_bytes())
else:
    receipt = json.loads((run / 'native_save.json').read_text())
    target = runtime / receipt['archive_relative_to_runtime']
    if hashlib.sha256(target.read_bytes()).hexdigest() != receipt['sha256']:
        raise RuntimeError('Native save changed since capture')
subprocess.run(['docker', 'compose', '-f', str(compose), '-f', str(override),
                'up', '-d', '--force-recreate', 'factorio_0'], check=True)
print('NATIVE_SAVE_LOADED ' + json.dumps(receipt))
