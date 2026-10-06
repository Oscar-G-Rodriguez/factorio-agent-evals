"""Verify exported A05 pilot bytes and replay controller-visible observations without inference."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('run_ids',nargs='+')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
root=repo/'factorio-pilot/evidence/runs'
audit=[]
for name in args.run_ids:
    assert re.fullmatch(r'A05-observation-(automatic|requested)-(model|scripted)-\d{8}T\d{6}Z',name)
    src=root/name
    config=json.loads((src/'config.json').read_text())
    summary=json.loads((src/'summary.json').read_text())
    rows=[json.loads(line) for line in (src/'steps.jsonl').read_text().splitlines()]
    assert summary['steps']==len(rows)
    initial=rows[0]['agent_visible_input']['observation']
    observation=initial
    observed_tick=0
    windows=[]
    inspections=0
    for index,row in enumerate(rows):
        visible=row['agent_visible_input']
        assert visible['observation']==observation
        assert visible['observation_tick']==observed_tick
        assert visible['observation_age_ticks']==index*900-observed_tick
        assert visible['recent_production_windows']==windows[-2:]
        assert row['elapsed_ticks']==(index+1)*900
        if config['controller']=='model':
            assert json.loads(row['prompt_messages'][-1]['content'])==visible
        if row['measurement_window']:
            windows_next=windows+[row['measurement_window']]
        else:
            windows_next=windows
        checked=isinstance(row['action'],dict) and row['action'].get('tool')=='check' and not row['failed_action']
        inspections+=int(checked)
        if config['observation_policy']=='automatic' or checked:
            observation=row['observation']
            observed_tick=row['elapsed_ticks']
        # Production windows are privately accumulated even when not disclosed.
        if config['observation_policy']=='requested':
            # Recover visible windows only when a check returns the private history.
            if checked:
                windows=[r['measurement_window'] for r in rows[:index+1] if r['measurement_window']]
        else:
            windows=windows_next
        if config['controller']=='model':
            for message in row['prompt_messages'][1:]:
                if message['role']=='user':
                    feedback=json.loads(message['content'])['result']
                    if feedback:
                        assert set(feedback)<= {'ok','tool','error','transferred_iron_plates'}
    assert inspections==summary['inspection_count']
    dst=src
    hashes=json.loads((dst/'export-sha256.json').read_text())
    for rel,digest in hashes.items():
        assert hashlib.sha256((dst/rel).read_bytes()).hexdigest()==digest
    for rel,digest in config['source_hashes'].items():
        assert hashlib.sha256((dst/'source'/rel).read_bytes()).hexdigest()==digest
    audit.append({'run':name,'steps':len(rows),'inspections':inspections,'visible_state_replay_passed':True,
                  'initial_observation':initial,'source_hashes':config['source_hashes']})
# Verification is read-only; retained audit was produced at export.
print(json.dumps([{k:v for k,v in a.items() if k not in ('initial_observation','source_hashes')} for a in audit]))
