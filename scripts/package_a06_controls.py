"""Export completed A06 CPU controls without copying native game archives."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--include-rejected-control', action='store_true')
args = parser.parse_args()
run, repo = args.run.resolve(), args.repo.resolve()
manifest = json.loads((run / 'control_manifest.json').read_text())
if (manifest['scripted_reachability_passed'] is not True and not args.include_rejected_control) or manifest['restores_exactly_matched'] is not True:
    raise RuntimeError('Do not export incomplete controls as passed')
destination = repo / 'factorio-pilot/evidence/runs' / run.name
destination.mkdir(exist_ok=False)
hashes = {}
for source in sorted(run.rglob('*')):
    if not source.is_file() or source.suffix not in ('.json', '.jsonl', '.py'):
        continue
    relative = source.relative_to(run)
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != hashlib.sha256(target.read_bytes()).hexdigest():
        raise RuntimeError('Export bytes changed')
    hashes[relative.as_posix()] = digest
provenance_path = run / 'fixture_provenance.json'
source_run = run
if provenance_path.exists():
    provenance = json.loads(provenance_path.read_text())
    prepared_name = provenance['prepared_in_run']
    if Path(prepared_name).name != prepared_name:
        raise RuntimeError('Invalid preparation run basename')
    source_run = run.parent / prepared_name
if source_run != run:
    for source in sorted(source_run.rglob('*')):
        if source.is_file() and source.suffix in ('.json', '.jsonl', '.py'):
            target = destination / 'preparation' / source.relative_to(source_run)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            if target.read_bytes() != source.read_bytes():
                raise RuntimeError('Preparation export bytes changed')
source = run / 'source/a06_native_server.py'
if not source.exists():
    source = source_run / 'source/a06_native_server.py'
if source.read_bytes() != (repo / 'factorio-pilot/tools/a06_native_server.py').read_bytes():
    raise RuntimeError('Orchestration source changed since capture')
(destination / 'source/a06_native_server.py').write_bytes(source.read_bytes())
if manifest['scripted_reachability_passed'] is not True:
    (destination / 'export_scope.json').write_text(json.dumps({'scope': 'rejected reference control; not a validated fixture or optimizer data', 'explicit_rejected_export': True}, indent=2) + '\n')
hashes = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(destination.rglob('*')) if p.is_file() and p != destination / 'export-sha256.json'}
(destination / 'export-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
scripted = json.loads((destination / 'scripted/summary.json').read_text())
idle = json.loads((destination / 'idle/summary.json').read_text())
print(json.dumps({'export': str(destination), 'verified_files': len(hashes),
    'scripted': {k: scripted[k] for k in ('simulated_seconds', 'wall_seconds', 'new_iron_plates', 'new_ore_mined', 'new_ore_consumed')},
    'idle': {k: idle[k] for k in ('simulated_seconds', 'wall_seconds', 'new_iron_plates', 'new_ore_mined', 'new_ore_consumed')},
    'idle_final': idle['final_physical_snapshot']}, indent=2))
