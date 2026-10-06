"""Conservative audit for this development tool set's direct drill/furnace chain."""
import json
import argparse
from pathlib import Path

root=Path('/home/osci2/factorio-pilot')
parser=argparse.ArgumentParser()
parser.add_argument('--include-logistics',action='store_true')
args=parser.parse_args()
reports=[]
paths=list((root/'runs').glob('A02-working-development-*/summary.json'))
paths.extend((root/'runs').glob('working-development-*/summary.json'))  # Original host records.
if args.include_logistics:
    paths.extend((root/'runs').glob('A03-logistics-development-*/summary.json'))
    paths.extend((root/'runs').glob('logistics-development-*/summary.json'))
for path in sorted(paths):
    summary=json.loads(path.read_text())
    config=json.loads((path.parent/'config.json').read_text())
    target=config.get('target_plates_per_minute',16)
    events=[json.loads(line) for line in (path.parent/'steps.jsonl').read_text().splitlines()]
    final=summary['final_factory']
    drills=[e for e in final['entities'] if e['name']=='burner-mining-drill']
    furnaces=[e for e in final['entities'] if e['name']=='stone-furnace']
    connections=[]
    for drill in drills:
        drop=drill['drop_position']
        sinks=[f['handle'] for f in furnaces if abs(drop['x']-f['position']['x'])<1 and abs(drop['y']-f['position']['y'])<1]
        connections.append({'drill':drill['handle'],'drop_position':drop,'receiving_furnaces':sinks})
    allowed={'find_iron','move','place_drill','place_furnace_at_output','fuel','check','wait','finish'}
    if config['mode']=='logistics-development': allowed.update(('collect_output','place_storage','store_plates'))
    checks={
        'two_exact_3600_tick_windows_meet_configured_target':len(summary['measurement_windows'])==2 and all(w['actual_ticks']==3600 and w['iron_plates']>=target for w in summary['measurement_windows']),
        'only_audited_tools_successfully_executed':all(e['failed_action'] or (isinstance(e['action'],dict) and e['action'].get('tool') in allowed) for e in events),
        'drill_output_inside_furnace_bounds':bool(connections) and all(c['receiving_furnaces'] for c in connections),
        'furnaces_contain_mined_iron_and_produced_plates':bool(furnaces) and all('iron-ore=' in f.get('furnace_source','') and 'iron-plate=' in f.get('furnace_result','') for f in furnaces),
        'no_handcrafting_or_harvesting':not final['production'].get('crafted') and not final['production'].get('harvested'),
        'restricted_fuel_actions_only':all(set(e['action']['args'])=={'building_handle','coal_count'} for e in events if isinstance(e['action'],dict) and e['action'].get('tool')=='fuel'),
        'successful_coal_fuel_actions_for_drill_and_furnace':bool(drills and furnaces) and all(any(not e['failed_action'] and isinstance(e['action'],dict) and e['action'].get('tool')=='fuel' and e['action']['args'].get('building_handle')==machine['handle'] for e in events) for machine in drills+furnaces),
    }
    passed=all(checks.values())
    audit={'run':path.parent.name,'passed':passed,'target_plates_per_minute':target,'checks':checks,'connections':connections,
           'scope':'restricted-tool direct drill-to-furnace chain; not a general belt-network validator',
           'method':'recorded actions, final inventories/geometry, crafting/harvesting counters and unattended throughput'}
    (path.parent/'supply-chain-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    summary['task_success']=passed
    summary['automated_supply_chain_check']='direct_chain_audit_passed' if passed else 'direct_chain_audit_failed'
    path.write_text(json.dumps(summary,indent=2)+'\n')
    reports.append({'run':path.parent.name,'mode':config['mode'],'target_plates_per_minute':target,'passed':passed,'steps':summary['steps'],
        'failures':summary['failed_actions'],'plates':[w['iron_plates'] for w in summary['measurement_windows']],
        'wall_seconds':summary['wall_seconds']})
(root/'artifacts'/'working-agent-results.json').write_text(json.dumps([r for r in reports if r['mode']=='working-development'],indent=2)+'\n')
if args.include_logistics:
    (root/'artifacts'/'logistics-agent-results.json').write_text(json.dumps([r for r in reports if r['mode']=='logistics-development'],indent=2)+'\n')
print(json.dumps(reports,indent=2))
