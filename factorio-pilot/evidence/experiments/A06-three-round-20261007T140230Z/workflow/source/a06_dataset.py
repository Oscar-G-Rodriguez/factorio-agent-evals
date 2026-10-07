"""Build and re-audit executed A06 train examples; never extracts reserved actions."""
import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from a06_context import canonical, digest, project, render, semantic_messages, training_encoding, validate_action
from observation_policy import ObservationPolicy

TRAIN_RUNS = {
    'train_drill': 'A06-train_drill-controls-20261006T211921Z',
    'train_furnace': 'A06-train_furnace-controls-20261006T223803Z',
    'train_output': 'A06-train_output-controls-20261007T022345Z',
    'train_carry': 'A06-train_carry-controls-20261007T022727Z',
}
ROW_FIELDS = {'schema_version', 'protocol_id', 'fixture_id', 'partition', 'episode_id', 'decision_index',
              'messages', 'target_action', 'label_source', 'evidence', 'input_sha256'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def optimizer_rows(rows, protocol):
    """Fail closed before any optimizer receives rows, regardless of asserted partition."""
    registry = {f['id']: f['partition'] for f in protocol['fixtures']}
    episodes = {}
    for row in rows:
        if set(row) != ROW_FIELDS or row['schema_version'] != 1 or row['protocol_id'] != protocol['protocol_id']:
            raise ValueError('Invalid dataset row schema or protocol')
        if registry.get(row['fixture_id']) != 'train' or row['partition'] != 'train':
            raise ValueError('Reserved or unknown fixture at optimizer boundary')
        expected = TRAIN_RUNS[row['fixture_id']] + '/scripted'
        if row['episode_id'] != expected or row['label_source'] != 'executed_scripted':
            raise ValueError('Unverified episode lineage or label source')
        if row['episode_id'] in episodes and episodes[row['episode_id']] != row['fixture_id']:
            raise ValueError('Episode lineage spans fixtures')
        episodes[row['episode_id']] = row['fixture_id']
    return rows


def collect(root, tokenizer):
    sys.path.insert(0, str(root / 'scripts'))
    from verify_a06_controls import verify_run
    protocol_path = root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json'
    protocol = read(protocol_path)
    guide_path = root / protocol['context']['guide_path']
    if sha(guide_path) != protocol['context']['guide_sha256']:
        raise ValueError('Frozen guide changed')
    # Preserve exact CRLF guide bytes as content, not platform-normalized text.
    guide = guide_path.read_bytes().decode('utf-8')
    rows, exclusions, audits, lengths = [], [], {}, []
    sources = {str(protocol_path.relative_to(root)): sha(protocol_path),
               str(guide_path.relative_to(root)): sha(guide_path)}
    for fixture, run_id in TRAIN_RUNS.items():
        if next(f for f in protocol['fixtures'] if f['id'] == fixture)['partition'] != 'train':
            raise ValueError('Fixture registry changed')
        run = root / 'factorio-pilot/evidence/runs' / run_id
        audit = verify_run(run, root)
        if not audit['reference_reachability_passed'] or audit['controls']['scripted']['failed_actions']:
            raise ValueError('Teacher lacks verified successful full-horizon continuation')
        config = read(run / 'config.json')
        if config.get('reference_policy', 'a05') != 'a05':
            raise ValueError('Only unchanged training teacher is eligible')
        audits[run_id] = audit
        trace_path = run / 'scripted/steps.jsonl'
        trace_bytes = trace_path.read_bytes()
        lines = trace_bytes.splitlines(keepends=True)
        steps = [json.loads(line) for line in lines]
        origin = steps[0]['tick_before']
        visibility = ObservationPolicy('automatic', steps[0]['observation_before'], 0)
        history, windows = [], []
        summary = read(run / 'scripted/summary.json')
        for file in (trace_path, run / 'scripted/summary.json', run / 'fixture_snapshot.json', run / 'config.json', run / 'control_manifest.json'):
            sources[file.relative_to(root).as_posix()] = sha(file)
        for i, step in enumerate(steps):
            payload = project(visibility.visible(step['tick_before'] - origin))
            if step['observation_before'] != visibility.snapshot or step['step'] != i:
                raise ValueError('Visible state does not match actual pre-action state')
            validate_action(step['action'], payload)
            if step['failed_action'] or step['error'] is not None or not isinstance(step['result'], dict):
                raise ValueError('Label action was not successfully executed')
            try:
                messages, count, trimmed = render(guide, payload, history, tokenizer)
                encoding = training_encoding(tokenizer, messages, step['action'])
            except ValueError as error:
                exclusions.append({'fixture_id': fixture, 'episode_id': run_id + '/scripted', 'decision_index': i, 'reason': str(error)})
            else:
                row = {'schema_version': 1, 'protocol_id': protocol['protocol_id'], 'fixture_id': fixture,
                       'partition': 'train', 'episode_id': run_id + '/scripted', 'decision_index': i,
                       'messages': messages, 'target_action': step['action'], 'label_source': 'executed_scripted',
                       'evidence': {'trace_path': trace_path.relative_to(root).as_posix(), 'trace_sha256': sha(trace_path),
                                    'decision_sha256': digest(step), 'decision_line_sha256': hashlib.sha256(lines[i]).hexdigest(),
                                    'snapshot_sha256': sha(run / 'fixture_snapshot.json'),
                                    'execution_receipt_sha256': digest(step['result']), 'successful_execution': True,
                                    'continuation_run_id': run_id + '/scripted', 'continuation_endpoint': summary['stop_reason'],
                                    'continuation_summary_sha256': sha(run / 'scripted/summary.json')},
                       'input_sha256': digest(messages)}
                rows.append(row)
                lengths.append({'fixture_id': fixture, 'decision_index': i, 'prompt_tokens': count,
                                'target_tokens': encoding['target_tokens'], 'total_tokens': len(encoding['input_ids']),
                                'history_pairs_trimmed': trimmed})
            history.append((payload, step['action']))
            history = history[-2:]
            if step['window']:
                window = dict(step['window'])
                window['start_tick'] -= origin
                window['end_tick'] -= origin
                windows.append(window)
            visibility.update(step['observation_after'], step['tick_after'] - origin,
                              step['action'], step['result'], step['error'], windows)
    optimizer_rows(rows, protocol)
    return rows, lengths, exclusions, audits, sources


def duplicate_audit(rows):
    exact, semantic, decisions = {}, {}, set()
    exact_groups, semantic_groups = [], []
    for row in rows:
        identity = (row['episode_id'], row['decision_index'])
        if identity in decisions:
            raise ValueError('Repeated source decision')
        decisions.add(identity)
        for index, key, groups in ((exact, digest(row['messages']), exact_groups),
                                   (semantic, digest(semantic_messages(row['messages'])), semantic_groups)):
            if key in index:
                old = index[key]
                if old['partition'] != row['partition']:
                    raise ValueError('Duplicate input crosses partitions')
                groups.append([list((old['episode_id'], old['decision_index'])), list(identity)])
                if old['target_action'] != row['target_action'] and key == digest(row['messages']):
                    raise ValueError('Conflicting labels for same exact input')
            else:
                index[key] = row
    # Deliberately broader screen: ignore history/timing/feedback and retain current physical facts.
    states = {}
    for row in rows:
        p = json.loads(semantic_messages(row['messages'])[-1]['content'])['observation']
        key = digest(p)
        states.setdefault(key, []).append([row['fixture_id'], row['decision_index']])
    near = [group for group in states.values() if len(group) > 1]
    # Numerical near-state screen across distinct train fixtures, independent of action labels.
    # Max normalized coordinate distance <= .05; statuses and geometry must match exactly.
    vectors = []
    for row in rows:
        p = json.loads(row['messages'][-1]['content'])['observation']
        vector = [p['inventory']['coal']/400, p['inventory']['iron-plate']/100]
        shape = []
        for e in p['equipment']:
            shape.append([e['name'], e['position'], e['status']])
            if 'burner' in e:
                vector += [e['burner']['coal_in_fuel_inventory']/6,
                           e['burner']['remaining_burning_fuel_joules']/4000000]
            if 'output_storage' in e:
                capacity = 100 if e['name'] == 'stone-furnace' else 1600
                vector.append(e['output_storage']['iron_plates']/capacity)
        vectors.append((vector, shape))
    approximate = []
    screened = 0
    for i, row in enumerate(rows):
        for j in range(i):
            if row['fixture_id'] == rows[j]['fixture_id']:
                continue
            screened += 1
            vector, shape = vectors[i]
            other, other_shape = vectors[j]
            if shape != other_shape:
                continue
            distance = max(abs(x-y) for x, y in zip(vector, other))
            if distance <= .05:
                approximate.append({'left': [rows[j]['fixture_id'], rows[j]['decision_index']],
                                    'right': [row['fixture_id'], row['decision_index']],
                                    'max_normalized_distance': distance,
                                    'same_action_kind': row['target_action']['tool'] == rows[j]['target_action']['tool']})
    return {'exact_duplicate_pairs': exact_groups, 'semantic_duplicate_pairs': semantic_groups,
            'near_duplicate_screen': 'Identical current physical whitelist after removing handles, history, timing, windows and feedback',
            'near_duplicate_groups': near,
            'approximate_cross_fixture_pairs_screened': screened,
            'approximate_cross_fixture_pairs': approximate,
            'approximate_method': 'Same geometry/status; maximum absolute normalized physical coordinate difference <=0.05. Coal/400, carried and furnace plates/100, chest plates/1600, stored fuel/6, burning joules/4000000. Timing/history/feedback excluded for screening only.',
            'near_duplicate_review': 'Repeated teacher trajectories share one geometry and deterministic policy; rows are correlated demonstrations, not independent task evidence. Keep episode split and report repeated states.',
            'cross_partition_check': 'Only registered train lineages extracted. Reserved actions never read by builder; validation/test optimizer rows rejected. Semantic cross-partition checks must also run when evaluation prompts are collected.'}


def stats(values):
    ordered = sorted(values)
    return {'count': len(values), 'min': min(values), 'median': statistics.median(values),
            'p95': ordered[max(0, (95 * len(values) + 99)//100 - 1)], 'max': max(values)}


def tokenizer_receipt(snapshot):
    return {file.name: sha(file) for file in sorted(snapshot.iterdir())
            if file.is_file() and (file.name.startswith('tokenizer') or file.name in ('vocab.json', 'merges.txt', 'special_tokens_map.json', 'chat_template.jinja', 'config.json'))}


def build(root, output, tokenizer, snapshot):
    if output.exists():
        raise ValueError('Dataset releases are immutable; choose a new output')
    rows, lengths, exclusions, audits, sources = collect(root, tokenizer)
    if not rows:
        raise ValueError('No eligible rows')
    duplicates = duplicate_audit(rows)
    if duplicates['exact_duplicate_pairs'] or duplicates['semantic_duplicate_pairs']:
        raise ValueError('Duplicate inputs need an explicit reviewed weighting/deduplication decision before release')
    output.mkdir(parents=True)
    (output / 'train.jsonl').write_text(''.join(canonical(row) + '\n' for row in rows), encoding='utf-8', newline='\n')
    for name, value in (('token-lengths.json', lengths), ('exclusions.json', exclusions), ('duplicate-audit.json', duplicates), ('control-audits.json', audits)):
        (output / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')
    code_names = ('a06_context.py', 'a06_dataset.py', 'observation_policy.py')
    source = output / 'source'
    source.mkdir()
    code_hashes = {}
    for name in code_names:
        path = Path(__file__).with_name(name)
        (source / name).write_bytes(path.read_bytes())
        code_hashes[name] = sha(path)
    # These verifiers are part of the evidence qualification, not merely incidental imports.
    for name in ('verify_a06_controls.py',):
        path = root / 'scripts' / name
        (source / name).write_bytes(path.read_bytes())
        sources['scripts/' + name] = sha(path)
    import transformers
    protocol = read(root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    behaviors = Counter()
    for row in rows:
        action = row['target_action']
        behavior = action['tool']
        if behavior == 'fuel':
            current = json.loads(row['messages'][-1]['content'])
            behavior += ':' + next(e['name'] for e in current['observation']['equipment'] if e['handle'] == action['args']['building_handle'])
        behaviors[behavior] += 1
    manifest = {'schema_version': 1, 'protocol_id': protocol['protocol_id'], 'release_id': output.name,
                'created_at_utc': datetime.now(timezone.utc).isoformat(), 'model': protocol['model'],
                'tokenizer_files': tokenizer_receipt(snapshot), 'transformers_version': transformers.__version__,
                'row_counts': {'train': len(rows), 'validation': 0, 'test': 0},
                'fixture_counts': dict(Counter(r['fixture_id'] for r in rows)), 'behavior_counts': dict(behaviors),
                'episodes': sorted(set(r['episode_id'] for r in rows)), 'excluded_rows': len(exclusions),
                'token_lengths': {k: stats([x[k] for x in lengths]) for k in ('prompt_tokens', 'target_tokens', 'total_tokens')},
                'history_pairs_trimmed': sum(x['history_pairs_trimmed'] for x in lengths),
                'source_inputs_sha256': sources, 'renderer_builder_source_sha256': code_hashes,
                'files_sha256': {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob('*')) if p.is_file()},
                'scope': 'Executed scripted demonstrations from four train fixtures; no model improvement or training claim'}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    return manifest


def audit(root, output, tokenizer, snapshot):
    manifest = read(output / 'manifest.json')
    actual_files = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()} - {'manifest.json'}
    if actual_files != set(manifest['files_sha256']):
        raise ValueError('Dataset file set changed')
    for name, expected in manifest['files_sha256'].items():
        if sha(output / name) != expected:
            raise ValueError('Dataset checksum mismatch: ' + name)
    if tokenizer_receipt(snapshot) != manifest['tokenizer_files']:
        raise ValueError('Pinned tokenizer files changed')
    for name, expected in manifest['source_inputs_sha256'].items():
        if sha(root / name) != expected:
            raise ValueError('Source evidence changed: ' + name)
    for name, expected in manifest['renderer_builder_source_sha256'].items():
        if sha(Path(__file__).with_name(name)) != expected:
            raise ValueError('Current builder differs from release snapshot')
    expected, lengths, exclusions, controls, sources = collect(root, tokenizer)
    sources['scripts/verify_a06_controls.py'] = sha(root / 'scripts/verify_a06_controls.py')
    rows = [json.loads(line) for line in (output / 'train.jsonl').read_text(encoding='utf-8').splitlines()]
    if rows != expected or read(output / 'token-lengths.json') != lengths or read(output / 'exclusions.json') != exclusions or read(output / 'control-audits.json') != controls or manifest['source_inputs_sha256'] != sources:
        raise ValueError('Release does not reproduce exactly from executed evidence')
    protocol = read(root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    optimizer_rows(rows, protocol)
    if read(output / 'duplicate-audit.json') != duplicate_audit(rows):
        raise ValueError('Duplicate audit changed')
    if manifest['row_counts'] != {'train': len(rows), 'validation': 0, 'test': 0}:
        raise ValueError('Wrong partition counts')
    if manifest['fixture_counts'] != dict(Counter(r['fixture_id'] for r in rows)) or manifest['episodes'] != sorted(set(r['episode_id'] for r in rows)) or manifest['excluded_rows'] != len(exclusions):
        raise ValueError('Incorrect membership or exclusions')
    for key in ('prompt_tokens', 'target_tokens', 'total_tokens'):
        if manifest['token_lengths'][key] != stats([x[key] for x in lengths]):
            raise ValueError('Token length summary does not reproduce')
    for row in rows:
        if digest(row['messages']) != row['input_sha256']:
            raise ValueError('Input hash mismatch')
        payload = json.loads(row['messages'][-1]['content'])
        validate_action(row['target_action'], payload)
        encoding = training_encoding(tokenizer, row['messages'], row['target_action'])
        n = encoding['prompt_tokens']
        if any(x != -100 for x in encoding['labels'][:n]) or encoding['labels'][n:] != encoding['input_ids'][n:]:
            raise ValueError('Loss mask invalid')
    return {'passed': True, 'release_id': manifest['release_id'], 'rows_verified': len(rows),
            'manifest_sha256': sha(output / 'manifest.json'), 'source_reconstruction_exact': True,
            'executed_actions_and_full_horizon_verified': True, 'reserved_optimizer_rows': 0,
            'prompt_and_target_budget_verified': True, 'loss_mask_verified': True}


def load_optimizer_dataset(root, output, tokenizer, snapshot):
    """Single training ingress: audit before returning any encoded examples."""
    receipt = audit(root, output, tokenizer, snapshot)
    rows = [json.loads(line) for line in (output / 'train.jsonl').read_text(encoding='utf-8').splitlines()]
    protocol = read(root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    optimizer_rows(rows, protocol)
    return [training_encoding(tokenizer, row['messages'], row['target_action']) for row in rows], receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('build', 'audit'))
    parser.add_argument('--tokenizer-snapshot', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    from transformers import AutoTokenizer
    root = Path(__file__).resolve().parents[2]
    protocol = read(root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    if args.tokenizer_snapshot.name != protocol['model']['revision']:
        raise ValueError('Tokenizer snapshot revision does not match frozen Qwen')
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_snapshot, local_files_only=True, trust_remote_code=False)
    result = build(root, args.output, tokenizer, args.tokenizer_snapshot) if args.mode == 'build' else audit(root, args.output, tokenizer, args.tokenizer_snapshot)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
