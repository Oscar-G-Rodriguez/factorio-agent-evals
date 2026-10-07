"""Host orchestration: archive or reload the observed A06 native save only."""
import argparse
import hashlib
import json
import os
import pwd
import subprocess
import zipfile
import shutil
from datetime import datetime, timezone
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
if run.parent != runtime / 'runs' or not run.name.startswith('A06-'):
    raise ValueError('Run must be an observed A06 control directory')
config = json.loads((run / 'config.json').read_text())
registry = json.loads((Path(__file__).resolve().parents[1] / 'protocols/a06-qwen-sft-v1.json').read_text())
fixture = config['fixture']
if fixture not in registry['fixtures'] or not run.name.startswith('A06-' + fixture['id'] + '-controls-'):
    raise ValueError('Unexpected fixture')
native = runtime / 'native-fixtures' / run.name
override = run / 'native-server.override.yaml'
if args.mode == 'capture-and-restore':
    if not args.save_name or '/' in args.save_name or not args.save_name.startswith('a06_' + fixture['id'] + '_') or not args.save_name.endswith('.zip'):
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
    receipt = {'native_save_filename': args.save_name, 'archive_relative_to_runtime': str(target.relative_to(runtime)),
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size,
        'zip_integrity_passed': True, 'original_compose_sha256': hashlib.sha256(compose.read_bytes()).hexdigest()}
    (run / 'native_save.json').write_text(json.dumps(receipt, indent=2) + '\n')
else:
    receipt = json.loads((run / 'native_save.json').read_text())
    target = runtime / receipt['archive_relative_to_runtime']
    if hashlib.sha256(target.read_bytes()).hexdigest() != receipt['sha256']:
        raise RuntimeError('Native save changed since capture')
# The recorded archive is a master, never a writable game mount. FLE setup
# can save 'initial' again; each load therefore gets a fresh working copy.
if not target.resolve().is_relative_to(runtime / 'native-fixtures'):
    raise RuntimeError('Master archive escapes fixture storage')
if hashlib.sha256(target.read_bytes()).hexdigest() != receipt['sha256']:
    raise RuntimeError('Master archive changed before working-copy creation')
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
working = runtime / 'native-work' / run.name / stamp
working.mkdir(parents=True, exist_ok=False)
uid = pwd.getpwnam(args.owner).pw_uid
os.chown(working, uid, 845)
os.chmod(working, 0o2775)
loaded = working / 'initial.zip'
shutil.copyfile(target, loaded)
os.chown(loaded, uid, 845)
os.chmod(loaded, 0o664)
if hashlib.sha256(loaded.read_bytes()).hexdigest() != receipt['sha256']:
    raise RuntimeError('Working copy differs from master')
original = yaml.safe_load(compose.read_text())['services']['factorio_0']['command']
needle = '--start-server-load-scenario default_lab_scenario'
if original.count(needle) != 1:
    raise RuntimeError('Unexpected original server command')
saved_command = original.replace(needle, '--start-server /factorio/saves/initial.zip')
backup = run / 'native-server.override.previous.yaml'
if override.exists() and not backup.exists():
    backup.write_bytes(override.read_bytes())
override.write_text(yaml.safe_dump({'services': {'factorio_0': {'command': saved_command,
    'volumes': [{'type': 'bind', 'source': str(working), 'target': '/factorio/saves'}]}}}))
source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(run / 'source' / 'a06_native_server.py').write_bytes(Path(__file__).read_bytes())
(run / ('native_mount_' + stamp + '.json')).write_text(json.dumps({
    'master_archive': receipt['archive_relative_to_runtime'], 'master_sha256': receipt['sha256'],
    'working_directory': str(working.relative_to(runtime)), 'working_copy_sha256': hashlib.sha256(loaded.read_bytes()).hexdigest(),
    'master_is_game_mount': False, 'source_sha256': source_hash}, indent=2) + '\n')
subprocess.run(['docker', 'compose', '-f', str(compose), '-f', str(override),
                'up', '-d', '--force-recreate', 'factorio_0'], check=True)
print('NATIVE_SAVE_LOADED ' + json.dumps(receipt))
