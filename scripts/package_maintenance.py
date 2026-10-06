import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
project = root/'factorio-pilot'
runs = sorted((project/'evidence/runs').glob('A04-maintenance-*'))
rows = []
for run in runs:
    if not (run/'summary.json').exists(): continue
    config = json.loads((run/'config.json').read_text(encoding='utf-8'))
    summary = json.loads((run/'summary.json').read_text(encoding='utf-8'))
    events = [json.loads(line) for line in (run/'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(events) == summary['steps']
    assert all(e['elapsed_ticks'] == (i+1)*900 for i, e in enumerate(events))
    assert all(w['actual_ticks'] == 3600 for w in summary['measurement_windows'])
    snapshot = project/'source-snapshots'/('maintenance-controls-v1' if config['controller'] != 'model' else 'maintenance-development-v2')/'tools'
    for name, expected in config['source_hashes'].items():
        data = (snapshot/name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, (run.name, name, expected, hashlib.sha256(data).hexdigest())
    # Produced plates remain in furnace output, actor inventory or chest.
    final = summary['final_observation']
    total = final['inventory']['iron-plate']+sum(e.get('output_storage', {}).get('iron_plates', 0) for e in final['equipment'])
    produced = final['production']['output']['iron-plate']
    assert total == produced, (run.name, total, produced)
    counts = Counter(e['action']['tool'] for e in events if e['action'] and not e['error'])
    row = {'run': run.name, 'controller': config['controller'], 'stop_reason': summary['stop_reason'],
           'game_seconds': summary['simulated_seconds'], 'wall_seconds_excluding_load_and_setup': summary['wall_seconds'],
           'decisions': summary['steps'], 'failed_actions': summary['failed_actions'],
           'window_plates': [w['iron_plates'] for w in summary['measurement_windows']],
           'successful_tool_counts': dict(counts), 'failure_indicators': summary['failure_indicators'],
           'plate_conservation': {'produced_including_warmup': produced, 'accounted': total},
           'median_response_seconds': summary['median_response_seconds'], 'source_snapshot': snapshot.parent.relative_to(project).as_posix()}
    row['timed_generation_seconds'] = sum(e['response_seconds'] for e in events)
    row['other_evaluation_wall_seconds'] = summary['wall_seconds']-row['timed_generation_seconds']
    row['history_pairs_trimmed'] = summary.get('history_pairs_trimmed_total')
    row['tokens'] = summary['tokens']
    row['gpu_peak_allocated_bytes'] = summary['gpu_peak_allocated_bytes']
    row['observed_input_token_range'] = [min(e['input_tokens'] for e in events), max(e['input_tokens'] for e in events)]
    row['first_low_window_end_seconds'] = next((w['end_tick']-config['fixture_origin_tick'] for w in summary['measurement_windows'] if w['below_target']), None)
    if row['first_low_window_end_seconds'] is not None: row['first_low_window_end_seconds'] /= 60
    row['first_empty_and_expired_burner_seconds'] = next((e['elapsed_ticks']/60 for e in events if any(entity.get('burner', {}).get('coal_in_fuel_inventory') == 0 and entity['burner']['remaining_burning_fuel_joules'] <= 0 for entity in e['observation']['equipment'])), None)
    row['first_carrying_full_seconds'] = next((e['elapsed_ticks']/60 for e in events if e['observation']['carrying']['available_carry_space'] == 0), None)
    row['first_full_furnace_output_seconds'] = next((e['elapsed_ticks']/60 for e in events if any(entity['name'] == 'stone-furnace' and entity['output_storage']['free_plate_capacity'] == 0 for entity in e['observation']['equipment'])), None)
    row['failed_tool_counts'] = dict(Counter(e['action']['tool'] for e in events if e['action'] and e['error']))
    rows.append(row)
(project/'evidence/artifacts/maintenance-development-results.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
table = '\n'.join(f"| {r['controller']} | {r['game_seconds']/60:g} | {r['decisions']} | {r['failed_actions']} | {r['stop_reason']} | {r['wall_seconds_excluding_load_and_setup']:.2f} |" for r in rows)
details = '\n\n'.join(f"`{r['run']}`: plate windows {r['window_plates']}; successful actions {r['successful_tool_counts']}; failed actions {r['failed_tool_counts']}; final failure indicators {r['failure_indicators']}. Timed generation: {r['timed_generation_seconds']:.2f}s; other evaluation wall time: {r['other_evaluation_wall_seconds']:.2f}s. History pairs trimmed: {r['history_pairs_trimmed']}. First observed expired burner: {r['first_empty_and_expired_burner_seconds']} game seconds; first full carrying inventory: {r['first_carrying_full_seconds']} game seconds." for r in rows)
finding = ''
model_rows = [r for r in rows if r['controller'] == 'model']
if model_rows:
    row = model_rows[-1]
    if row['stop_reason'] == 'sustained_production_failure':
        finding = f"Qwen reached sustained failure after {row['game_seconds']/60:g} game minutes ({row['wall_seconds_excluding_load_and_setup']:.2f} wall seconds, excluding model loading and setup). It made {row['failed_actions']} failed actions. Its final state contains expired burners {row['failure_indicators']['empty_and_expired_burners']} and {row['failure_indicators']['reserve_coal']} coal still in reserve. Inspect the saved trace to distinguish missed refueling from output/storage errors; the fixture did not force resource exhaustion. This single-chain maintenance task already exposes model failures, so further complexity can wait until the memory/backend comparisons use a frozen baseline."
protocol_path = root/'outputs/factorio-pilot-protocol.json'
protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
protocol['maintenance_development'] = {'results': rows, 'target': 16, 'decision_interval_ticks': 900,
    'failure_rule': 'two_consecutive_60_second_windows_below_16', 'max_game_seconds': 1200,
    'max_decisions': 80, 'refill_max_coal': 3, 'carrying_benchmark_limit': 100,
    'custom_cuda_used': False, 'memory_comparison_complete': False}
protocol_path.write_text(json.dumps(protocol, indent=2)+'\n', encoding='utf-8')
report = f'''# Factorio maintenance development results

The earlier construction/expansion success check stopped before recurring fuel and storage demands were tested. Its final machines still held 38–44 coal, with 300 in reserve; one furnace held 94/100 plates. Those results remain preserved and are not pooled with this maintenance task.

## Methods

The new maintenance runner starts from a scripted one-drill/one-furnace/one-chest fixture, using the same validated placement and fueling tools. No ore or plates are injected. Each machine receives three coal. A 60-second warm-up must produce at least 16 plates before evaluation begins; fixture construction and warm-up are excluded from model decisions and measured production windows.

The maintenance controller can refill a machine with 1–3 coal, collect up to 100 finished plates, store up to 100 carried plates, check, or wait. Fuel per action and the 100 carried-plate limit are disclosed benchmark rules. The chest has its real 1600-plate capacity. All equipment is within transfer range. Movement, construction, expansion and external disruptions are not part of this first maintenance fixture.

Every decision, including invalid actions, consumes exactly 900 simulation ticks (15 seconds). The world pauses during inference and runs at 10× during advancement. Nonoverlapping windows contain exactly 3600 ticks. Two consecutive windows below 16 plates constitute sustained production failure. Meeting the target does not stop the episode. Limits are 20 game minutes, 80 decisions and 600 wall seconds; reaching a limit is recorded honestly as survival through the horizon or an incomplete budget-limited run. The first low window and terminal failure are distinct from the physical instant an outage began.

The model condition uses pinned Qwen3-4B-Instruct-2507 with BF16 PyTorch SDPA, greedy generation, an 8192-token total context and 256 generated-token budget. Its prompt teaches the game mechanics and tool syntax but does not prescribe a complete maintenance action sequence. Ordinary history is trimmed when needed; model logs retain the assembled prompts and cumulative trimming count. Full current equipment observations make this a maintenance decision test, not yet a test of remembering unseen equipment. Structured memory and RAG comparisons are pending.

## Results

| Controller | Game minutes after warm-up | Decisions | Failed actions | Endpoint | Wall seconds, excluding load/setup |
| --- | ---: | ---: | ---: | --- | ---: |
{table}

{finding}

{details}

The idle control is a negative control. The scripted controller uses only visible fuel/storage state and the same permitted actions; its result tests reachability, not model quality. These are single-fixture development runs, not independent statistical samples. Every logged decision interval and complete measurement window was audited. In every completed run, produced plates equal the plates in furnace output, carried inventory and chest.

## GPU work and limits

With explicit user authorization, the reviewed bounded RMSNorm suite passed memcheck, racecheck, initcheck and synccheck with zero reported errors. Each tool ran all 25 correctness cases. The temporary Windows debugger interface was restored to its previous absent state. See `factorio-pilot/evidence/artifacts/approved-sanitizer-validation.json`.

These maintenance runs use the original PyTorch inference backend. The custom C++/CUDA kernel is not yet integrated into Qwen, so no faster-agent claim follows from its standalone operator timings. The intended next measurement is original versus integrated inference on identical saved prompts: logits/token agreement, generation latency and total evaluation wall time. Model generation, controlled simulation and observation/transfer costs must be distinguished. Because the game pauses during inference, faster CUDA does not give the agent extra simulated reaction time.

If Qwen survives this fixture, increase difficulty in a separately versioned task—for example a second chain or a disclosed demand schedule—then repeat a scripted survivability control. Do not change difficulty mid-comparison to manufacture failures. Preserve limits and surviving episodes when estimating time to failure.

## Reproduction

Start the existing pinned 2.0.73 server. Run only one controller at a time because each resets the same factory. From the repository root in Ubuntu/WSL:

```bash
export FACTORIO_PILOT_HOME="${{FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}}"
"$FACTORIO_PILOT_HOME/.venv/bin/python" -m unittest discover -s factorio-pilot/tools -p 'test_*.py'
bash factorio-pilot/setup/run-maintenance.sh --controller idle --minutes 20
bash factorio-pilot/setup/run-maintenance.sh --controller scripted --minutes 20
bash factorio-pilot/setup/run-maintenance.sh --controller model --minutes 20
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/export_evidence.py
```

Sources are preserved in the per-result snapshots above, with hashes verified against each configuration. Controls v1 and model v2 differ only in additional prompt/history logging and the first-low-window timestamp; the task, action cadence and endpoint are identical. Environment/model pins remain in the project README and saved artifacts. Previous construction, storage and kernel findings remain separate.
'''
(root/'outputs/A04 - Maintenance - Results.md').write_text(report, encoding='utf-8')
print(json.dumps(rows, indent=2))
