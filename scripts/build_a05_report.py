"""Build the one-fixture executed observation-policy pilot record."""
from pathlib import Path
import json
import argparse
import hashlib

parser=argparse.ArgumentParser()
parser.add_argument('run_ids',nargs='+')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=='scripts' else Path(r'C:\Users\osci2\Documents\Second Brain\Projects\Factorio Agent Evals\Public Repository')
runs=[]
for name in args.run_ids:
    directory=repo/'factorio-pilot/evidence/runs'/name
    config=json.loads((directory/'config.json').read_text())
    summary=json.loads((directory/'summary.json').read_text())
    rows=[json.loads(line) for line in (directory/'steps.jsonl').read_text().splitlines()]
    runs.append((name,config,summary,rows))
models=[r for r in runs if r[1]['controller']=='model']
assert len(models)==2 and {r[1]['observation_policy'] for r in models}=={'automatic','requested'}
assert models[0][1]['source_hashes']==models[1][1]['source_hashes']
assert models[0][1]['system_prompt']==models[1][1]['system_prompt']
assert models[0][1]['starting_state_sha256']==models[1][1]['starting_state_sha256']
initial_equal=models[0][3][0]['agent_visible_input']['observation']==models[1][3][0]['agent_visible_input']['observation']
lines=['# A05 - Observation policy - Pilot results','',
       'This executed pilot checks whether Qwen requests current factory information when automatic updates are removed. '
       'It includes an inspection-paying scripted reachability control and one model episode per condition on one maintenance fixture. '
       'It is a machinery check, not a model ranking or a held-out policy evaluation.','',
       '## Methods','',
       'Both model conditions use the pinned Qwen3-4B-Instruct-2507 revision, original PyTorch BF16/SDPA inference, '
       'ordinary history, greedy decoding, 8,192 total tokens and 256 output tokens. The goal and game guide are identical. '
       'Each starts from the same saved reset state and scripted factory: one drill, furnace and chest, three coal per machine '
       'and a verified 60-second warm-up. Every decision, including check, failure and wait, advances 900 ticks (15 game seconds). '
       'Two consecutive 60-second windows below 16 plates end the episode. The horizon is 20 game minutes or 80 decisions, '
       'with a 600-second wall budget checked between decisions.','',
       'The automatic condition receives a fresh snapshot after each action. The requested condition receives an initial snapshot '
       'and refreshes only after a successful check, after that decision\'s 15-second advancement. Snapshot time and age are disclosed. '
       'Both receive the same filtered action feedback: success/failure, the tool name and a bounded transferred plate count where relevant. '
       'Nested raw results, inventory before/after counts and raw exception messages stay in the evaluator log. '
       'Production windows update in the prompt only when observation delivery permits them.','',
       'The scripted requested-inspection controller uses the visible snapshot and alternates maintenance with checking. '
       'Its success tests reachability under the inspection budget and is excluded from model scores. '
       'All five project native files were inspected, the exact-hash gate passed, and native sources remained unchanged. '
       'The custom RMSNorm backend, prefix reuse, memory policies and training were not varied in this experiment.','',
       f'Both model runs used identical evaluated Python hashes, guide text and starting-state file hashes. Exact initial visible observation equality: **{initial_equal}**. '
       'The export audit replays visible state against the private trace and verifies retained source/export bytes. '
       'Thirty-six CPU tests passed, including six observation-policy tests covering leakage, stale timestamps, failed checks and copy isolation.','',
       '## Results','',
       '| Controller / observations | Endpoint | Game minutes | Decisions | Failed actions | Checks | Max snapshot age s | Input / output tokens | Episode wall s |',
       '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
for name,c,s,rows in runs:
    lines.append(f'| {c["controller"]} / {c["observation_policy"]} | `{s["stop_reason"]}` | {s["simulated_seconds"]/60:g} | {s["steps"]} | {s["failed_actions"]} | {s["inspection_count"]} | {s["maximum_observation_age_seconds"]:g} | {s["tokens"]["input_total"]} / {s["tokens"]["output_total"]} | {s["wall_seconds"]:.2f} |')
lines+=['','Wall time excludes model loading and fixture setup. Response timing retains the A04 generation-only boundary, '
        'not K02\'s complete-response boundary; those timing tables must not be pooled. GPU memory is peak PyTorch allocation, '
        'not total device usage.','']
for name,c,s,rows in runs:
    counts=[w['iron_plates'] for w in s['measurement_windows']]
    lines.append(f'`{name}` plates by measured minute: `{counts}`. Peak allocated GPU bytes: `{s["gpu_peak_allocated_bytes"]}`.')
    lines.append('')
lines+=['## Interpretation and limits','',
        'This automatic-statistics condition is a new baseline with common filtered feedback, timestamps and observation guidance. '
        'It is not a byte-identical rerun of the earlier A04 ordinary-history episode; differences from A04 cannot be attributed '
        'to observation delivery alone.','',
        'These conditions change observation delivery, including the opportunity cost of inspection and resulting context length. '
        'They do not isolate reasoning ability from sensing cost or establish that longer history alone causes failure. '
        'A controller may infer changes from its own transfers; that is permitted information, not an automatic stat update. '
        'Previously observed state can legitimately be stale. Full evaluator observations and raw results remain private to the controller.','',
        'One episode per condition on one fixture cannot support a general improvement claim or a fine-tuning conclusion. '
        'Additional distinct frozen solvable fixtures and held-out tasks are still required. '
        'The scripted trace can seed examples, but it is not yet a training dataset or held-out benchmark. '
        'Any later fine-tuning comparison should retain this unchanged-model baseline and evaluate executed held-out episodes.','',
        '## Evidence and reproduction','',
        '[Visibility audit](../factorio-pilot/evidence/artifacts/A05-observation-audit.json) records replay checks and initial observations.']
for name,c,s,rows in runs:
    lines+=['',f'- [{name}](../factorio-pilot/evidence/runs/{name}/): configuration, fixture, action trace, summary, exact source snapshots and export hashes.']
lines+=['','From the repository root in the configured ordinary-user Linux runtime:','','```bash',
        'export FACTORIO_PILOT_HOME="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"',
        'sudo docker compose -f "$FACTORIO_PILOT_HOME/cluster/compose.yaml" start factorio_0',
        '"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/maintenance_agent.py --controller scripted --observation-policy requested --minutes 20',
        'sudo docker compose -f "$FACTORIO_PILOT_HOME/cluster/compose.yaml" start factorio_0',
        '"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/maintenance_agent.py --controller model --observation-policy automatic --minutes 20',
        'sudo docker compose -f "$FACTORIO_PILOT_HOME/cluster/compose.yaml" start factorio_0',
        '"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/maintenance_agent.py --controller model --observation-policy requested --minutes 20',
        '```','',
        'Run sequentially against the existing local server: each command resets the world. Review every native file and confirm '
        'the exact-hash gate before GPU/model runs. The pinned FLE environment, model snapshot and reset artifact are external '
        'runtime prerequisites described in the [runtime README](../factorio-pilot/README.md). The default observation policy '
        'remains legacy A04; explicit automatic/requested modes create A05 records.','']
lines+=['An earlier automatic attempt, `A05-observation-automatic-model-20261006T181856Z`, stopped at RCON connection before gameplay '
        'because the server was not running. It is excluded from scores. The server log recorded SIGTERM after the preceding control; '
        'the SIGTERM source was not established. Restarting the existing container before the next model attempt allowed it to connect. '
        'This is an infrastructure failure, not a model maintenance failure.','']
destination=repo/'outputs/A05 - Observation Policy - Pilot Results.md'
assert not destination.exists(), 'Preserve an existing result before regenerating'
destination.write_bytes('\n'.join(lines).encode('utf-8'))
print(str(destination))
