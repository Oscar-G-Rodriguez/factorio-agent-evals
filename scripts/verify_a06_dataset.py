"""CPU-only A06 release verification and pinned-tokenizer training ingress check."""
import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path


def verify(root, release, snapshot):
    sys.path.insert(0, str(root / 'factorio-pilot/tools'))
    from a06_context import canonical, digest, pad_encoding, validate_payload
    from a06_dataset import load_optimizer_dataset, optimizer_rows, read, sha, stats
    from transformers import AutoTokenizer
    protocol = read(root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    manifest = read(release / 'manifest.json')
    if snapshot.name != protocol['model']['revision'] or manifest['model'] != protocol['model'] or manifest['protocol_id'] != protocol['protocol_id'] or manifest['release_id'] != release.name:
        raise ValueError('Release or model/tokenizer identity differs from frozen protocol')
    import transformers
    if manifest['transformers_version'] != transformers.__version__:
        raise ValueError('Tokenizer runtime differs from recorded version')
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    encodings, receipt = load_optimizer_dataset(root, release, tokenizer, snapshot)
    rows = [json.loads(line) for line in (release / 'train.jsonl').read_text().splitlines()]
    from collections import Counter
    behaviors = Counter()
    history_targets_masked = 0
    for row, encoding in zip(rows, encodings):
        tool = row['target_action']['tool']
        payload = json.loads(row['messages'][-1]['content'])
        if tool == 'fuel':
            tool += ':' + next(e['name'] for e in payload['observation']['equipment'] if e['handle'] == row['target_action']['args']['building_handle'])
        behaviors[tool] += 1
        n = encoding['prompt_tokens']
        decoded = tokenizer.decode(encoding['input_ids'][n:-1], skip_special_tokens=False)
        if decoded != canonical(row['target_action']) or encoding['input_ids'][-1] != tokenizer.eos_token_id:
            raise ValueError('Loss target is not exactly JSON action and assistant end token')
        if any(label != -100 for label in encoding['labels'][:n]):
            raise ValueError('Prompt/history leaks into loss')
        history_targets_masked += sum(m['role'] == 'assistant' for m in row['messages'])
        padded = pad_encoding(encoding, len(encoding['input_ids']) + 7, tokenizer.pad_token_id)
        if padded['labels'][-7:] != [-100]*7 or padded['attention_mask'][-7:] != [0]*7:
            raise ValueError('Padding contributes to loss')
    if manifest['behavior_counts'] != dict(behaviors):
        raise ValueError('Behavior counts differ from labels')
    lengths = read(release / 'token-lengths.json')
    if manifest['history_pairs_trimmed'] != sum(row['history_pairs_trimmed'] for row in lengths):
        raise ValueError('Trimming count differs from rendered prompts')
    # Deliberately spoof the row's assertion of train membership; registry must win.
    rejected = []
    for fixture in protocol['fixtures']:
        if fixture['partition'] == 'train':
            continue
        row = deepcopy(rows[0])
        row['fixture_id'] = fixture['id']
        try:
            optimizer_rows([row], protocol)
        except ValueError:
            rejected.append(fixture['id'])
        else:
            raise ValueError('Reserved fixture accepted with spoofed train label')
    for field in ('fixture_id', 'partition', 'correct_action', 'final_outcome'):
        payload = json.loads(rows[0]['messages'][-1]['content'])
        payload[field] = 'injected'
        try:
            validate_payload(payload)
        except ValueError:
            pass
        else:
            raise ValueError('Forbidden model-visible field accepted')
    return {**receipt, 'target_json_roundtrip_verified': True, 'historical_assistant_targets_masked': history_targets_masked,
            'padding_mask_verified_for_rows': len(rows), 'reserved_fixture_spoof_cases_rejected': rejected,
            'forbidden_visible_field_cases_rejected': 4, 'behavior_counts_verified': dict(behaviors),
            'verifier_sha256': sha(Path(__file__)), 'model_loaded': False, 'gpu_run': False,
            'scope': 'Training dataset and CPU input/loss contract; no Qwen policy evaluation or trained adapter'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', default='A06-scripted-train-v1-20261007-r3')
    parser.add_argument('--tokenizer-snapshot', required=True, type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    release = root / 'factorio-pilot/evidence/datasets' / args.release
    if release.parent.resolve() != (root / 'factorio-pilot/evidence/datasets').resolve():
        raise ValueError('Release must be in the dataset directory')
    result = verify(root, release, args.tokenizer_snapshot)
    text = json.dumps(result, indent=2) + '\n'
    if args.receipt:
        with args.receipt.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
    print(text)
