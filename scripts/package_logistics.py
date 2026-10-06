import hashlib
import json
import shutil
from pathlib import Path

project=Path(__file__).resolve().parents[1]
root=project/'factorio-pilot'
evidence=root/'evidence'
run=evidence/'runs/logistics-development-20261006T035914Z'
config=json.loads((run/'config.json').read_text())
summary=json.loads((run/'summary.json').read_text())
control=json.loads((evidence/'artifacts/logistics-control.json').read_text())
checks=json.loads((evidence/'artifacts/rmsnorm-correctness.json').read_text())
manifest_path=evidence/'artifacts/cuda-source-review.json'
manifest=json.loads(manifest_path.read_text())
assert all(check['passed'] for check in checks['correctness_checks'])
assert checks['source_hashes']=={n:manifest['source_hashes'][f'cuda/{n}'] for n in ('rmsnorm.cpp','rmsnorm.cu')}
manifest['dynamic_validation_status']='25_required_correctness_cases_passed_for_reviewed_sources'
manifest['dynamic_validation_artifact']='evidence/artifacts/rmsnorm-correctness.json'
manifest['cpu_unit_tests_passed']=20
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
snapshot=root/'source-snapshots/logistics-development-v3/tools'
snapshot.mkdir(parents=True,exist_ok=True)
for name,expected in config['source_hashes'].items():
    content=(root/'tools'/name).read_bytes()
    assert hashlib.sha256(content).hexdigest()==expected,name
    (snapshot/name).write_bytes(content)
for name in ('test_logistics_tools.py','check_logistics.py','audit_working_agent.py','test_cuda_review.py'):
    shutil.copyfile(root/'tools'/name,snapshot/name)
shutil.copyfile(project/'work/logistics-unit-tests.log',evidence/'artifacts/logistics-unit-tests.txt')
shutil.copyfile(project/'work/reviewed-rmsnorm-correctness.log',evidence/'artifacts/reviewed-rmsnorm-correctness.txt')
notes={'source_snapshot':'logistics-development-v3','source_hashes_verified':True,
       'is_unassisted_planning':False,'storage_tools_used_in_model_run':False,
       'expansion_followed_rejected_premature_finish_with_explicit_expansion_feedback':True,
       'evaluation_scope':'guided expansion only; long-running collection and maintenance not yet evaluated',
       'wall_time_scope':'after model loading, through evaluation; no viewing delay'}
(run/'development-notes.json').write_text(json.dumps(notes,indent=2)+'\n',encoding='utf-8')
protocol_path=project/'outputs/factorio-pilot-protocol.json'
protocol=json.loads(protocol_path.read_text())
protocol['native_source_review']={'status':manifest['status'],'source_files_reviewed':len(manifest['source_hashes']),
     'matching_correctness_checks_passed':len(checks['correctness_checks']),'sanitizer':manifest['sanitizer_status']}
protocol['logistics_development']={'run':run.name,'scripted_control_passed':control['passed'],
    'expansion_task_success':summary['task_success'],'target_plates_per_minute':32,
    'measured_plates':[w['iron_plates'] for w in summary['measurement_windows']],
    'model_storage_behavior_tested':False}
protocol_path.write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
report=f'''# Factorio Storage and Expansion Results

The revised interface can collect finished iron plates from a furnace into the agent inventory and store them in a wooden chest. A scripted control verified that output blockage stops production, collection restores it, and all transfers conserve items. Separately, the guided Qwen agent expanded to two automatic iron production chains and met a 32-plate-per-minute target. Long-running model maintenance remains untested.

## Actual storage and new tools

In the current environment a stone furnace has one output slot holding 100 normal iron plates. The earlier successful factory ended with 74 plates in it. A nearby chest does not remove output automatically. Wooden chests have 16 slots and capacity for 1600 normal iron plates when empty. The agent now observes current output, carried plates and destination capacity.

`collect_output(furnace_handle, plate_count)` transfers from the exact furnace output to the FLE agent character's inventory. `place_storage(position)` places a supplied chest. `store_plates(chest_handle, plate_count)` transfers from the character to that chest. Counts are integers from 1 to 100, transfers are limited by actual source contents and destination space, and interaction requires proximity. The new development mode additionally declares a 100-carried-plate benchmark limit, which creates storage pressure without pretending it is the game's physical inventory limit. Plates are stored, not deleted.

Direct inventory transfers avoid a defect in the installed FLE extraction helper: its item-count helper adds the entity-wide count once per valid inventory, and its player insertion uses the requested extraction stack instead of the actual removed amount. An oversized request could therefore create extra plates. The project has not patched the installed package. Its restricted transfer code uses the exact source inventory, transfers only what exists and fits, restores any uninserted remainder to that same inventory, and checks source loss against destination gain. It never places ore or plates into a furnace input.

## Scripted validation

All eight scripted checks passed, including partial collection, partial storage, a natural full-output stall, production recovery, carrying-limit rejection, full-chest rejection and measured capacity. Clearing the stalled output restored 19 plates in the next 3600-tick window. Before the separate artificial full-chest fixture, all 136 produced plates were accounted for: 117 in the chest, 12 in the furnace and seven carried. The injected full-chest fixture is excluded from production results and every model result.

Twenty CPU unit tests passed across the adapters and source review gate. The scripted storage control is evidence of tool reachability and conservation, not evidence that the model can manage storage over time.

## Guided expansion

| Target | Model decisions | Failed actions | Unattended minute 1 | Unattended minute 2 | Wall time after model loading |
| --- | --- | --- | --- | --- | --- |
| 32 plates per minute | {summary['steps']} | {summary['failed_actions']} | {summary['measurement_windows'][0]['iron_plates']} | {summary['measurement_windows'][1]['iron_plates']} | {summary['wall_seconds']:.2f} s |

The model first built one chain, tested it, and requested completion too early. The adapter rejected completion because production was below 32 and explicitly suggested inspecting bottlenecks or adding another chain. Qwen then placed and fueled another drill/furnace pair. Two unattended 3600-tick windows passed the target, and both direct ore-supply chains passed the audit.

This demonstrates expansion in response to a higher goal and corrective feedback. The prompt still supplies construction rules and procedure, placement remains assisted, and the rejection supplies an expansion hint. It does not demonstrate spontaneous growth or independent diagnosis. The model did not invoke any storage tool in this short episode: its furnace outputs ended at 94 and 74 plates. Longer maintenance trials are necessary to measure whether it notices and clears output blockage.

## Safety review and reproduction

The full project-authored C++/CUDA source review preceded these runs. The revised operator passed 25 matching numerical/boundary/stream checks. The review gate rejects added, removed or changed native sources; the custom benchmark gate additionally requires matching correctness evidence. Sanitizer validation remains blocked by the previously unapproved Windows debugging-interface setting. See [the source review](CUDA%20and%20C%2B%2B%20Source%20Review.md).

With the test server running, use these commands from PowerShell in the project directory:

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/cuda_review.py
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/check_logistics.py
wsl -d Ubuntu-24.04 -u osci2 -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-working-agent.sh --logistics --target-plates-per-minute 32 --steps 32 --visual --game-speed 10 --keep-visible-seconds 0
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/audit_working_agent.py --include-logistics
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/export_evidence.py
```

Run sequentially because these commands reset or control the same server. New run folders preserve earlier evidence. The source snapshot is `factorio-pilot/source-snapshots/logistics-development-v3/tools`; the run config hashes verify its evaluated files. The earlier guided and context-pilot reports remain separate. Evaluation still pauses simulation during inference and uses 10× speed during advancement.

The next implementation checkpoint is a maintenance runner that continues after initial construction, exposes the same storage rules across memory conditions, and measures outages and recovery. Expansion should be its own explicit production target or task stage, so increasing capacity does not obscure maintenance failures.
'''
(project/'outputs/A03 - Storage and Expansion - Results.md').write_text(report,encoding='utf-8')
print('Packaged review, storage and expansion evidence; source hashes verified.')
