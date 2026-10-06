"""Package guided development results separately from the frozen context pilot."""
import hashlib
import json
import statistics
from pathlib import Path

project = Path(__file__).resolve().parents[2]
root = Path('/home/osci2/factorio-pilot')
rows = []
for path in sorted((root/'runs').glob('working-development-*/summary.json')):
    summary = json.loads(path.read_text())
    config = json.loads((path.parent/'config.json').read_text())
    events = [json.loads(line) for line in (path.parent/'steps.jsonl').read_text().splitlines()]
    fast = config.get('game_speed') == 10
    snapshot = 'working-agent-fast-v2' if fast else 'working-agent-v1'
    matches = {name: hashlib.sha256((project/'factorio-pilot/source-snapshots'/snapshot/'tools'/name).read_bytes()).hexdigest() == expected
               for name, expected in config['source_hashes'].items()}
    if not all(matches.values()):
        raise ValueError(f'Source snapshot mismatch: {path.parent.name}')
    quality = {
        'source_snapshot': snapshot, 'source_hash_checks': matches,
        'simulation_speed': '10x throughout' if fast else 'started at 1x; switched to 10x during evaluation',
        'timing_scope': 'agent decisions and evaluation; excludes model loading and optional post-run viewing',
        'is_controlled_speed_comparison': False,
        'is_unassisted_planning': False, 'not_comparable_to_frozen_context_pilot': True,
    }
    (path.parent/'development-notes.json').write_text(json.dumps(quality,indent=2)+'\n')
    rows.append({
        'run':path.parent.name,'speed':quality['simulation_speed'],
        'source_snapshot':snapshot,'success':summary['task_success'],
        'decisions':summary['steps'],'failed_actions':summary['failed_actions'],
        'plates':[w['iron_plates'] for w in summary['measurement_windows']],
        'actual_ticks':[w['actual_ticks'] for w in summary['measurement_windows']],
        'wall_seconds':summary['wall_seconds'],
        'median_response_seconds':statistics.median(e['response_seconds'] for e in events),
        'input_tokens_total':sum(e['input_tokens'] for e in events),
        'output_tokens_total':sum(e['output_tokens'] for e in events),
    })
(root/'artifacts/working-agent-results.json').write_text(json.dumps(rows,indent=2)+'\n')
table = '\n'.join(f"| {'Fast confirmation' if r['speed']=='10x throughout' else 'Initial development'} | {r['decisions']} | {r['failed_actions']} | {r['plates'][0]}, {r['plates'][1]} | {r['wall_seconds']:.2f} s |" for r in rows)
text = f'''# Working Factorio Agent Results

The guided local Qwen agent built a working burner drill and furnace supply chain. Both completed development runs passed the automatic ore-supply audit and produced 19 plates in each unattended one-minute measurement window. The fast confirmation used 10× simulation speed and no post-run viewing delay.

| Run | Decisions | Failed actions | Plates per measured minute | Agent and evaluation time |
| --- | --- | --- | --- | --- |
{table}

## What made the agent work

The development interface exposes eight small tools with explicit JSON examples. Fuel takes a building handle and coal count; furnace placement calculates adjacency from the observed drill. The prompt supplies the factory procedure. Qwen selects coordinates from observations, returns each action, and receives real execution feedback. It completes only after its production test passes.

This is a guided construction result. The procedure and geometry helper reduce the planning task substantially, so these runs cannot establish general autonomous planning or the benefit of structured memory. The earlier four zero-output context runs remain preserved in the preliminary pilot report.

## Development change record

| Change | Purpose | Evidence and limits |
| --- | --- | --- |
| Smaller tool set and explicit JSON examples | Reduce argument and action-format mistakes | Both successful runs issued eight valid actions with zero failures. |
| Explicit factory procedure | Guide construction and fueling of both machines | The saved system prompt contains the sequence; this is assisted planning. |
| Fuel arguments use a building handle and coal count | Remove ambiguity between the inserted item and its destination | Fuel actions supplied 50 coal to each machine; adapter tests verify translation. |
| Furnace placement uses the observed drill geometry | Put the receiving furnace at the ore output | The supply-chain audit checks the drop position inside furnace bounds. |
| Compact observations omit unreliable FLE warnings | Prevent contradictory warnings from obscuring working equipment | Raw observations retain the warnings for inspection. This change was not tested separately. |
| Generation stops at the first complete JSON object, with a 256-token cap | Bound response generation and encourage one action per decision | Responses, tokens and generation times are saved per step; no isolated timing comparison was performed. |
| Observation time is elapsed ticks from reset | Avoid dependence on the server's absolute tick counter | Configurations identify this clock; raw observations retain game ticks. |
| Completion requires a production test, followed by independent evaluation | Prevent premature success claims | Each measured window advanced exactly 3,600 ticks and produced 19 plates; the ore-supply audit passed. |
| Default simulation speed is 10×; viewing delay is zero | Shorten real-world runs | The fast confirmation took 49.16 seconds after model loading; game-time production remained 19 plates per minute. |

These changes were introduced together. The results establish that the combined guided configuration works on this starting state; they do not identify the contribution of each change. Separate removal experiments are needed for that attribution.

## Measurement and verification

Each run resets the same saved starting state and map seed, uses greedy decoding, and pauses simulation while the model reasons. After construction, evaluation advances a 60-second warm-up and two exact 3,600-tick windows. The audit checks drill output geometry, furnace ore and plate inventories, coal actions, absence of harvesting/crafting, and both throughput windows. The restricted tools allow supplied coal insertion only. Twelve adapter and memory tests pass.

Recorded times exclude model loading and post-run viewing. The initial run changed from 1× to 10× during evaluation; its timing is descriptive and is not a controlled speed comparison. The fast confirmation remained at 10×. Fast simulation preserves the evaluation tick counts and does not accelerate model inference. Per-step response times and token counts are saved; GPU memory was not newly instrumented for these development runs.

## Reproduce the fast run

From PowerShell in the project directory, with the existing test server running:

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-working-agent.sh --visual --game-speed 10 --keep-visible-seconds 0
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/audit_working_agent.py
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/report_working_agent.py
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/export_evidence.py
```

The runner defaults to 10× speed and zero viewing delay. Add `--require-viewer` only when a connected graphical client is required. It waits before loading FLE. A newly restarted server must accept the viewer before FLE installs tools: upstream runtime functions in Factorio storage can still prevent map saving and later joins. The private UDP relay and server should remain running during viewing.

Configurations, actions, raw observations, final states, audits and development notes are under `factorio-pilot/evidence/runs/working-development-*`. Hash-verified sources are under `factorio-pilot/source-snapshots/working-agent-v1` and `working-agent-fast-v2`. The viewer-wait attempt has no model decisions or summary and is excluded. Pinned model, engine and package versions remain in the project README and each run configuration.

Next, remove one piece of guidance at a time or test a small recovery challenge while preserving the same production checks. That will show which behavior the model can carry out with less assistance.
'''
(project/'outputs/A02 - Guided Construction - Results.md').write_text(text)
protocol_path = project/'outputs/factorio-pilot-protocol.json'
protocol = json.loads(protocol_path.read_text())
protocol['working_agent_development'] = {'status':'guided_agent_verified','simulation_speed':10,'keep_visible_seconds':0,
    'not_comparable_to_original_context_experiment':True,'completed_runs':rows}
protocol_path.write_text(json.dumps(protocol,indent=2)+'\n')
print(json.dumps(rows,indent=2))
