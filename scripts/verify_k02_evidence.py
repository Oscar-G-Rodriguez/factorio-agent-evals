"""Audit retained K02 bytes and comparisons without loading a model or GPU."""
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(repo):
    """Reject mismatched exports, incomplete samples or unsupported result claims."""
    root = repo / 'factorio-pilot'
    records = []
    for run in sorted((root/'evidence/runs').glob('K02-integrated-*')):
        data = json.loads((run/'results.json').read_text())
        if data['status'] not in ('offline_validation_passed', 'offline_benchmark_complete'):
            raise AssertionError(f'{run.name}: incomplete record')
        assert not data['game_actions_executed'] and not data['errors']
        for name, expected in json.loads((run/'export-sha256.json').read_text()).items():
            assert digest(run/name) == expected, (run.name, name, 'export hash')
        for name, expected in data['source_hashes'].items():
            assert digest(run/'source'/name) == expected, (run.name, name, 'source hash')
        for name, expected in data['native_source_hashes'].items():
            assert digest(root/name) == expected, (run.name, name, 'native hash')
        manifest = json.loads((run/'prompt-manifest.json').read_text())
        assert digest(root/manifest['trace']) == manifest['trace_sha256']
        steps = {case['step'] for case in manifest['cases']}
        assert len(steps) == 5
        for case in manifest['cases']:
            serialized = json.dumps(case['messages'],sort_keys=True,separators=(',',':'))
            assert hashlib.sha256(serialized.encode()).hexdigest() == case['messages_sha256']
        refs = {entry['step']: entry['response'] for entry in data['validation'] if entry['backend']=='eager'}
        backends = {'eager','custom'} | ({'compiled'} if data['args']['include_compiled'] else set())
        assert {(entry['step'],entry['backend']) for entry in data['validation']} == {(step,backend) for step in steps for backend in backends}
        for entry in data['validation']:
            assert entry['passed'] and entry['finite_prefill_logits']
            assert entry['response']['tokens'] == refs[entry['step']]['tokens']
            assert entry['response']['action'] == refs[entry['step']]['action']
            if entry['backend']=='custom':
                assert entry['coverage']['counts']['custom'] > 0
                assert len(entry['coverage']['replaced_modules']) == 73
                assert len(entry['coverage']['untouched_norms']) == 72
        samples = 0
        if data['status']=='offline_benchmark_complete':
            assert {item['step'] for item in data['timing']} == steps
            for item in data['timing']:
                assert set(item['samples']) == backends
                for backend, rows in item['samples'].items():
                    assert len(rows) == data['args']['samples'] * data['args']['blocks']
                    assert {(row['block'],row['index']) for row in rows} == {
                        (block,index) for block in range(data['args']['blocks']) for index in range(data['args']['samples'])}
                    for row in rows:
                        assert row['seconds'] > 0
                        assert row['tokens'] == refs[item['step']]['tokens']
                        assert row['action'] == refs[item['step']]['action']
                    samples += len(rows)
        records.append({'run':run.name,'validation_responses':len(data['validation']),'warm_samples':samples})
    assert len(records) == 2, 'Expected both retained K02 records'
    print(json.dumps({'verified_records':records,'scope':'Saved evidence only; no inference or game execution.'},indent=2))


if __name__ == '__main__':
    verify(Path(__file__).resolve().parents[1])
