"""Read-only audit: distinguish executed teacher waits and historical model waits."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
release = root / 'factorio-pilot/evidence/datasets/A06-scripted-train-v1-20261007-r3'
manifest = json.loads((release / 'manifest.json').read_text())
train_file = release / 'train.jsonl'
assert hashlib.sha256(train_file.read_bytes()).hexdigest() == manifest['files_sha256']['train.jsonl']
rows = [json.loads(line) for line in train_file.read_text().splitlines()]
traces = {}
waits = []
for row in rows:
    if row['target_action']['tool'] != 'wait':
        continue
    path = row['evidence']['trace_path']
    if path not in traces:
        data = (root / path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['evidence']['trace_sha256']
        traces[path] = [json.loads(line) for line in data.splitlines()]
    step = traces[path][row['decision_index']]
    assert step['action'] == row['target_action'] and not step['failed_action']
    before = step['observation_before']
    furnace = next(e for e in before['equipment'] if e['name'] == 'stone-furnace')
    burners = [e for e in before['equipment'] if 'burner' in e]
    new = step['observation_after']['production']['output']['iron-plate'] - before['production']['output']['iron-plate']
    waits.append({'fixture': row['fixture_id'], 'step': row['decision_index'],
                  'stored_fuel_min': min(e['burner']['coal_in_fuel_inventory'] for e in burners),
                  'carried_plates': before['carrying']['carried_plates'],
                  'furnace_output': furnace['output_storage']['iron_plates'],
                  'new_plates_next_interval': new,
                  'teacher_wait_predicate': all(e['burner']['coal_in_fuel_inventory'] > 1 for e in burners)
                       and before['carrying']['carried_plates'] == 0 and furnace['output_storage']['iron_plates'] < 60})

result = {'dataset': release.name, 'dataset_sha256': manifest['files_sha256']['train.jsonl'],
          'teacher_waits': len(waits), 'teacher_wait_predicate_met': sum(w['teacher_wait_predicate'] for w in waits),
          'waits_with_positive_next_interval_production': sum(w['new_plates_next_interval'] > 0 for w in waits),
          'stored_fuel_min': min(w['stored_fuel_min'] for w in waits),
          'maximum_output_before_wait': max(w['furnace_output'] for w in waits),
          'maximum_carried_before_wait': max(w['carried_plates'] for w in waits),
          'next_interval_plate_range': [min(w['new_plates_next_interval'] for w in waits), max(w['new_plates_next_interval'] for w in waits)],
          'teacher_waits_by_fixture': dict(Counter(w['fixture'] for w in waits)), 'wait_details': waits,
          'interpretation': 'All labels come from the scripted teacher, not Qwen. Predicate agreement and next-interval production support intentional idle scheduling; they do not prove the teacher is optimal.',
          'historical_model_runs': []}
for name in ('A04-maintenance-model-20261006T044058Z', 'A05-observation-automatic-model-20261006T182130Z',
             'A05-observation-requested-model-20261006T182355Z'):
    path = root / 'factorio-pilot/evidence/runs' / name / 'steps.jsonl'
    steps = [json.loads(line) for line in path.read_text().splitlines()]
    counts = Counter(step['action']['tool'] if isinstance(step.get('action'), dict) else 'no_valid_action' for step in steps)
    review = []
    for i, step in enumerate(steps):
        if not isinstance(step.get('action'), dict) or step['action']['tool'] != 'wait':
            continue
        # Prefer the actually supplied model-visible state, explicitly disclosing age.
        messages = step.get('prompt_messages', [])
        if messages:
            visible = json.loads(messages[-1]['content'])
            observation = visible.get('observation', {})
            equipment = observation.get('equipment', [])
            expired = [e['name'] for e in equipment if e.get('burner', {}).get('coal_in_fuel_inventory') == 0
                       and e.get('burner', {}).get('remaining_burning_fuel_joules') == 0]
            full = [e['name'] for e in equipment if e.get('output_storage', {}).get('free_plate_capacity') == 0]
            review.append({'step': step['step'], 'observation_age_ticks': visible.get('observation_age_ticks'),
                           'visible_expired_burners': expired, 'visible_full_storages': full})
        else:
            review.append({'step': step['step'], 'visible_state': 'Not available in this trace; no before-state causal classification'})
    latencies = [s['response_seconds'] for s in steps if s.get('response_seconds', 0) > 0]
    result['historical_model_runs'].append({'run': name, 'trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'action_counts': dict(counts), 'wait_review': review,
                  'recorded_response_seconds_median': statistics.median(latencies) if latencies else None,
                  'scope': 'Historical protocol only; not a matched A06 comparison or GPU bottleneck diagnosis'})
result['diagnostic_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
if args.output:
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(result, indent=2)+'\n')
compact = {k:v for k,v in result.items() if k != 'wait_details'}
print(json.dumps(compact, indent=2))
