"""CPU-only audit of the exported first A06 fixture controls."""
import argparse
import hashlib
import json
from pathlib import Path


def plate_inventory(observation: dict) -> int:
    return observation['carrying']['carried_plates'] + sum(
        e['output_storage']['iron_plates'] for e in observation['equipment'] if 'output_storage' in e)


def verify_run(run: Path, root: Path) -> dict:
    exported = json.loads((run / 'export-sha256.json').read_text())
    for name, digest in exported.items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Export checksum mismatch: ' + name)
    config = json.loads((run / 'config.json').read_text())
    protocol_path = root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json'
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != config['protocol_sha256']:
        raise RuntimeError('Protocol does not match evaluated configuration')
    protocol = json.loads(protocol_path.read_text())
    expected_fixture = next(f for f in protocol['fixtures'] if f['id'] == 'train_drill')
    if config['fixture'] != expected_fixture or config['task'] != protocol['task']:
        raise RuntimeError('Wrong fixture or task')
    for name, digest in config['source_hashes'].items():
        if hashlib.sha256((run / 'source' / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Evaluated source mismatch: ' + name)
    snapshot = json.loads((run / 'fixture_snapshot.json').read_text())
    for controller in ('scripted', 'idle'):
        restore = json.loads((run / (controller + '_restore.json')).read_text())
        if restore['expected'] != snapshot or restore['actual'] != snapshot or restore['exact_match'] is not True:
            raise RuntimeError('Control did not restore the same physical state')
    manifest = json.loads((run / 'control_manifest.json').read_text())
    if manifest['fixture_id'] != 'train_drill' or manifest['partition'] != 'train' or manifest['dataset_ready'] or manifest['other_fixtures_validated']:
        raise RuntimeError('Control scope incorrectly labeled')
    preparation = run / 'preparation'
    if preparation.exists():
        prepared_config = json.loads((preparation / 'config.json').read_text())
        if prepared_config['fixture'] != config['fixture'] or prepared_config['protocol_sha256'] != config['protocol_sha256']:
            raise RuntimeError('Preparation and control configurations disagree')
        for name, digest in prepared_config['source_hashes'].items():
            if hashlib.sha256((preparation / 'source' / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Preparation source mismatch: ' + name)
        if json.loads((preparation / 'fixture_snapshot.json').read_text()) != snapshot:
            raise RuntimeError('Preparation state changed before controls')
    controls = {}
    for controller in ('scripted', 'idle'):
        folder = run / controller
        summary = json.loads((folder / 'summary.json').read_text())
        steps = [json.loads(line) for line in (folder / 'steps.jsonl').read_text().splitlines()]
        windows = []
        for i, row in enumerate(steps):
            if row['step'] != i or row['tick_before'] != snapshot['tick'] + i * 900 or row['tick_after'] - row['tick_before'] != 900:
                raise RuntimeError('Wrong action cadence')
            if i and row['observation_before'] != steps[i - 1]['observation_after']:
                raise RuntimeError('State changed between decisions')
            before, after = row['observation_before'], row['observation_after']
            produced = after['production']['output'].get('iron-plate', 0) - before['production']['output'].get('iron-plate', 0)
            if plate_inventory(after) - plate_inventory(before) != produced:
                raise RuntimeError('Plate inventory conservation failed')
            if row['action']['tool'] in ('collect_output', 'store_plates') and not row['failed_action']:
                receipt = row['result']
                moved = receipt['transferred']
                if receipt['source_before'] - receipt['source_after'] != moved or receipt['destination_after'] - receipt['destination_before'] != moved or receipt['conserved'] is not True:
                    raise RuntimeError('Transfer receipt failed conservation')
            if row['window']:
                windows.append(row['window'])
                w = windows[-1]
                group = steps[i-3:i+1]
                actual = sum(e['observation_after']['production']['output'].get('iron-plate', 0) - e['observation_before']['production']['output'].get('iron-plate', 0) for e in group)
                if len(group) != 4 or w['actual_ticks'] != 3600 or w['iron_plates'] != actual:
                    raise RuntimeError('Window does not match observed production deltas')
        if len(steps) != summary['steps'] or windows != summary['measurement_windows']:
            raise RuntimeError('Summary differs from trace')
        if summary['failed_actions'] != sum(s['failed_action'] for s in steps):
            raise RuntimeError('Incorrect failed action count')
        if summary['simulated_seconds'] != len(steps) * 15 or summary['new_iron_plates'] != sum(w['iron_plates'] for w in windows):
            raise RuntimeError('Incorrect survival or production summary')
        if summary['model_loaded'] or summary['custom_cuda_used']:
            raise RuntimeError('These must be CPU environment controls')
        if controller == 'scripted' and (len(windows) != 20 or any(w['iron_plates'] < 16 for w in windows) or summary['stop_reason'] != 'survived_simulation_limit'):
            raise RuntimeError('Reachability control failed')
        if controller == 'idle' and (summary['stop_reason'] != 'sustained_production_failure' or len(windows) < 2 or any(w['iron_plates'] >= 16 for w in windows[-2:])):
            raise RuntimeError('Idle failure was not demonstrated')
        controls[controller] = {'steps': len(steps), 'seconds': summary['simulated_seconds'],
            'plate_windows': [w['iron_plates'] for w in windows], 'failed_actions': summary['failed_actions'],
            'new_ore_mined': summary['new_ore_mined'], 'new_ore_consumed': summary['new_ore_consumed']}
    return {'run': run.name, 'export_files_verified': len(exported), 'snapshot_exact_for_both_controls': True,
            'step_plate_conservation_verified': True, 'controls': controls,
            'scope': 'One training fixture; no Qwen, training data or adapter evaluation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(verify_run(root / 'factorio-pilot/evidence/runs' / args.run_id, root), indent=2))
