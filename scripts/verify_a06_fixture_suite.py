"""Portable completeness audit for all nine frozen A06 fixture controls."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from verify_a06_controls import verify_run


def audit_suite(root, runtime=None):
    prefix=chr(92)*2+'?'+chr(92)
    if sys.platform=='win32' and not str(root).startswith(prefix):root=Path(prefix+str(root.resolve()))
    protocol_path=root/'factorio-pilot/protocols/a06-qwen-sft-v1.json'
    protocol=json.loads(protocol_path.read_text())
    sys.path.insert(0,str(root/'factorio-pilot/tools'))
    from a06_fixture_controls import verify_presets
    starting=protocol['fixture_preparation']
    if hashlib.sha256((root/starting['starting_state_path']).read_bytes()).hexdigest()!=starting['starting_state_file_sha256']:raise RuntimeError('Starting state template changed')
    records=[];missing=[];geometry=None
    for fixture in protocol['fixtures']:
        candidates=[]
        for run in (root/'factorio-pilot/evidence/runs').glob('A06-'+fixture['id']+'-controls-*'):
            manifest=run/'control_manifest.json'
            if manifest.exists() and json.loads(manifest.read_text()).get('scripted_reachability_passed') is True:candidates.append(run)
        if not candidates:
            missing.append(fixture['id']);continue
        run=sorted(candidates)[-1]
        checked=verify_run(run,root)
        snapshot=json.loads((run/'fixture_snapshot.json').read_text())
        verify_presets(fixture,snapshot)
        setup=json.loads((run/'setup.json').read_text())
        if setup['warmup']['ticks']!=protocol['task']['window_ticks'] or setup['warmup']['iron_plates']<protocol['task']['min_warmup_new_plates']:raise RuntimeError('Warm-up did not demonstrate production')
        entities={e['name']:e for e in snapshot['entities']}
        if entities['stone-furnace']['plates']+entities['stone-furnace']['free_plates']!=protocol['task']['furnace_capacity'] or entities['wooden-chest']['plates']+entities['wooden-chest']['free_plates']!=protocol['task']['chest_capacity']:raise RuntimeError('Wrong storage capacities')
        layout={'actor_position':snapshot['actor_position'],'equipment':[
            {k:e[k] for k in ('name','position','direction')} | ({'drop_position':e['drop_position']} if 'drop_position' in e else {}) for e in snapshot['entities']]}
        if geometry is None:geometry=layout
        elif layout!=geometry:raise RuntimeError('Fixture geometry differs: '+fixture['id'])
        native=json.loads((run/'native_save.json').read_text())
        if native['zip_integrity_passed'] is not True or native['bytes']<=0:raise RuntimeError('Invalid native save receipt')
        native_verified=False
        if runtime:
            saved=(runtime/native['archive_relative_to_runtime']).resolve()
            if not saved.is_relative_to(runtime.resolve()/'native-fixtures'):raise RuntimeError('Save path escapes fixture storage')
            if saved.stat().st_size!=native['bytes'] or hashlib.sha256(saved.read_bytes()).hexdigest()!=native['sha256']:raise RuntimeError('Native archive changed')
            with zipfile.ZipFile(saved) as archive:
                if archive.testzip() is not None:raise RuntimeError('Native archive corruption')
            native_verified=True
        scripted=json.loads((run/'scripted/summary.json').read_text());idle=json.loads((run/'idle/summary.json').read_text())
        if scripted['no_manual_ore_insertion'] is not True or scripted['new_ore_mined']<=0:raise RuntimeError('Automatic ore supply not demonstrated')
        for receipt_path in run.glob('helpers_*.json'):
            receipt=json.loads(receipt_path.read_text())
            if 'source_sha256' in receipt and not any(hashlib.sha256(p.read_bytes()).hexdigest()==receipt['source_sha256'] for p in (run/'source').glob('*.py')):raise RuntimeError('Missing helper source provenance')
        supervision=run/'supervision.json'
        if supervision.exists():
            receipt=json.loads(supervision.read_text())
            if hashlib.sha256((run/'source/a06_control_batch.py').read_bytes()).hexdigest()!=receipt['supervisor_sha256']:raise RuntimeError('Supervisor source mismatch')
        records.append({'fixture':fixture['id'],'partition':fixture['partition'],'run':run.name,
            'scripted_seconds':scripted['simulated_seconds'],'new_plates':scripted['new_iron_plates'],
            'scripted_windows':[w['iron_plates'] for w in scripted['measurement_windows']],
            'scripted_failed_actions':scripted['failed_actions'],'idle_seconds':idle['simulated_seconds'],
            'idle_windows':[w['iron_plates'] for w in idle['measurement_windows']],
            'idle_failed_actions':idle['failed_actions'],'source_snapshot_sha256':hashlib.sha256((run/'fixture_snapshot.json').read_bytes()).hexdigest(),
            'native_sha256':native['sha256'],'native_archive_verified_now':native_verified,
            'export_files_verified':checked['export_files_verified']})
    return {'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),'required_fixtures':len(protocol['fixtures']),
        'validated_fixtures':len(records),'missing':missing,'complete':not missing,'common_geometry':geometry,
        'records':records,'scope':'Environment controls only; no optimizer data or Qwen evaluation'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-home',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=audit_suite(Path(__file__).resolve().parents[1],args.runtime_home)
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['complete']:raise SystemExit(1)
