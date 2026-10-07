"""CPU-only audit of the retained A06 three-round workflow, including its stop gate."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, name):
    if os.name == 'nt' and not str(root).startswith('\\\\?\\'):
        root = Path('\\\\?\\' + str(root.resolve()))
    package = root / 'factorio-pilot/evidence/experiments' / name
    manifest = read(package / 'manifest.json')
    for relative, expected in manifest['files_sha256'].items():
        path = (package / relative).resolve()
        assert path.is_relative_to(package.resolve()), 'Artifact path escapes package'
        assert sha(path) == expected, f'Artifact changed: {relative}'
    report = root / manifest['report_path']
    assert sha(report) == manifest['report_sha256'], 'Report hash mismatch'
    state = read(package / 'workflow/state.json')
    plan = read(package / 'workflow/protocol.json')
    assert plan == read(root / 'factorio-pilot/protocols/a06-three-round-v1.json'), 'Copied protocol differs semantically'
    assert sha(root / 'factorio-pilot/protocols/a06-three-round-v1.json') == state['protocol_sha256']
    assert plan['rounds'] == 3 and not plan['training']['custom_rmsnorm']
    curves = list(csv.DictReader((package / 'training-curves.csv').open()))
    assert len(curves) == 40 * len(state['training'])
    for number, external in state['training'].items():
        run = package / 'runs' / Path(external).name
        summary = read(run / 'summary.json')
        assert summary['phase'] == 'complete' and summary['passed']
        assert summary['round'] == int(number) and not summary['probe_only']
        assert summary['optimizer_steps'] == 40 and summary['micro_steps'] == 320
        assert not summary['custom_cuda_used'] and summary['dataset_audit']['reserved_optimizer_rows'] == 0
        assert summary['dataset_audit']['loss_mask_verified']
        for relative, expected in summary['native_source_hashes'].items():
            assert sha(root / 'factorio-pilot' / relative) == expected, 'Native source changed'
        if int(number) > 1:
            assert summary['correction_audit']['passed']
            assert summary['correction_audit']['rows'] >= plan['corrections']['minimum_distinct_rows']
    episodes = []
    replays = []
    for item in state['completed_jobs']:
        run = package / 'runs' / Path(item['run']).name
        if item['job'].get('kind') == 'correction':
            proof = read(run / 'correction_verification.json')
            for file, key in (('continuation.jsonl', 'continuation_sha256'), ('corrective_action.json', 'action_receipt_sha256'), ('candidate_restore.json', 'candidate_restore_sha256'), ('native_save.json', 'native_save_sha256')):
                assert sha(run / file) == proof[key]
            if proof['accepted']:
                assert proof['exact_pre_action_restore'] and proof['corrective_action_executed'] and proof['observed_problem_addressed'] and proof['full_horizon_survived']
                assert proof['final_tick'] - proof['origin_tick'] == 72000
                assert len(proof['measurement_windows']) == 20
                assert all(v['consecutive_low_windows'] < 2 for v in proof['measurement_windows'])
            replays.append(proof)
            continue
        config = read(run / 'config.json')
        summary = read(run / 'summary.json')
        events = [json.loads(v) for v in (run / 'steps.jsonl').read_text().splitlines()]
        assert len(events) == summary['steps']
        assert config['condition'] == item['job']['condition'] == summary['condition']
        assert config['purpose'] == item['job']['purpose'] == summary['purpose']
        for event in events:
            for field in ('render_seconds','time_to_first_token_seconds','remaining_generation_seconds','tool_seconds','game_seconds','response_seconds'):
                assert field in event and (event[field] is None or event[field] >= 0)
        episodes.append(summary)
    for condition, selected in state['selected'].items():
        scores = {}
        for step in (20, 40):
            rows = [v['summary'] for v in selected['validation'] if v['checkpoint_step'] == step]
            assert len(rows) == 2
            scores[step] = (sum(v['simulated_seconds'] for v in rows) / 2, sum(v['new_iron_plates'] for v in rows), -step)
        assert selected['selected_step'] == max(scores, key=scores.get), 'Checkpoint selection differs'
        receipt = read(package / 'runs' / Path(selected['adapter']).parent.name / Path(selected['adapter']).name / 'receipt.json')
        assert receipt['round'] == int(condition[5]) and receipt['step'] == selected['selected_step']
        assert receipt['config_sha256'] == state['protocol_sha256']
        for name, expected in selected['sha256'].items():
            assert receipt['files'][name] == expected, 'Selected adapter differs from checkpoint receipt'
    assert len(list(csv.DictReader((package / 'comparison.csv').open()))) == len(episodes)
    final = [v for v in episodes if v['purpose'] == 'final-test']
    assert manifest['completed_rounds'] == len(state['training']) and manifest['final_episodes'] == len(final)
    if state['phase'] == 'incomplete' and state['stage'] == 'round2_correction_verification':
        partial = read(package / 'insufficient-corrections-round2/status.json')
        rows = [json.loads(v) for v in (package / 'insufficient-corrections-round2/train.jsonl').read_text().splitlines()]
        assert len(rows) == partial['verified_rows'] < plan['corrections']['minimum_distinct_rows']
        assert not partial['accepted_for_training'] and '2' not in state['corrections']
        assert len(state['training']) == 2 and not state['final_tests_opened'] and not final
        assert not manifest['all_three_rounds_and_final_tests_complete']
    return {'passed': True, 'artifact_hashes': len(manifest['files_sha256']), 'model_episodes': len(episodes), 'correction_replays': len(replays), 'training_rounds': len(state['training']), 'final_test_episodes': len(final), 'phase': state['phase'], 'goal_complete': manifest['all_three_rounds_and_final_tests_complete']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', default='A06-three-round-20261007T140230Z')
    args = parser.parse_args()
    print(json.dumps(verify(Path(__file__).resolve().parents[1], args.experiment)))
