import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
project = root/'factorio-pilot'
artifacts = project/'evidence/artifacts'
initial = json.loads((artifacts/'storage-context-probe.json').read_text(encoding='utf-8'))
subgoal = json.loads((artifacts/'storage-subgoal-probe.json').read_text(encoding='utf-8'))
assert initial['actual_game_actions_executed'] == subgoal['actual_game_actions_executed'] == 0
assert initial['source_event_sha256'] == subgoal['source_event_sha256']
current = (project/'tools/probe_storage_context.py').read_text(encoding='utf-8')
old = current.replace('import argparse\n', '')
old = old.replace("parser = argparse.ArgumentParser()\nparser.add_argument('--storage-subgoal-only', action='store_true')\nargs = parser.parse_args()\n", '')
start = old.index("conditions = [('recorded_history'")
end = old.index('    inputs = tokenizer.apply_chat_template', start)
old = old[:start]+"for condition, prompt in [('recorded_history', messages), ('fresh_context', [messages[0], messages[-1]])]:\n"+old[end:]
old = old.replace("'intervention': 'explicit storage subgoal appended to fresh prompt' if args.storage_subgoal_only else 'remove older user/assistant messages; keep identical system instructions and latest observed state/feedback',", "'intervention': 'remove older user/assistant messages; keep identical system instructions and latest observed state/feedback',")
old = old.replace("'results': results, 'limits': 'One observed state. History probe changes content and length together; cannot isolate token count from historical action bias. Explicit subgoal is assisted capability diagnosis, not autonomous maintenance success. Proposed actions are not executed or full-episode outcomes.'}", "'results': results, 'limits': 'One observed state and two greedy generations. Changes history content and length together; cannot isolate token count from historical action bias. Proposed actions are not executed or full-episode outcomes.'}")
old = old.replace("name = 'storage-subgoal-probe.json' if args.storage_subgoal_only else 'storage-context-probe.json'\n(project/'evidence/artifacts'/name).write_text(json.dumps(report, indent=2)+'\\n')", "(project/'evidence/artifacts/storage-context-probe.json').write_text(json.dumps(report, indent=2)+'\\n')")
for label, text, evidence in [('storage-context-probe-v1', old, initial), ('storage-subgoal-probe-v2', current, subgoal)]:
    data = text.encode('utf-8')
    assert hashlib.sha256(data).hexdigest() == evidence['source_sha256'], label
    destination = project/'source-snapshots'/label/'tools'
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'probe_storage_context.py').write_bytes(data)

table = '\n'.join(f"| {item['condition']} | {item['input_tokens']} | `{item['action']['tool']}` |" for item in initial['results']+subgoal['results'])
report = f'''# Storage tool-selection diagnostic

The maintenance agent had the storage tool in its system instructions, an observed wooden chest handle e1 with 1600 free plate capacity, 100 carried plates, zero benchmark carrying space, and feedback from a failed collection. The system message remained present despite history trimming. Tool visibility was verified from the exact recorded prompt at decision 23.

Three offline greedy generations used the same pinned Qwen revision and the same recorded current observation/feedback. No game actions were executed and no factory was reset.

| Condition | Input tokens | Proposed tool |
| --- | ---: | --- |
{table}

The recorded-history replay exactly reproduced the original failed collection action. Removing history changed the proposal to fuel, but did not elicit storage. Adding an explicit diagnostic subgoal—free carrying space by storing carried plates in the observed chest—elicited `store_plates` with chest e1 and quantity 100. That proposal matches the exposed tool contract and observed available capacity. It is an assisted capability check, not an executed transfer or autonomous maintenance improvement.

The result shows that this model can select the storage command when the subgoal is stated explicitly. The autonomous problem concerns selecting and prioritizing that subgoal while maintaining production and recovering from failures. The history change affected its choice; these single-state probes do not isolate history length from historical action content or establish a general explanation for every failure. Timing is a single unwarmed sample in a fixed order and is not a performance benchmark.

Next experiments should compare factual memory of carrying capacity and recent failures against ordinary history, while retaining storage as a model-selected action. More specific transfer failure codes can be developed separately and frozen for all scored conditions. Do not silently add the explicit storage hint to one memory condition or count an automatic transfer as a model decision.

Evidence: `factorio-pilot/evidence/artifacts/storage-context-probe.json` and `storage-subgoal-probe.json`. Exact probe source snapshots were verified against each artifact's SHA-256. The probe imports the native-source review gate before GPU execution; no native sources changed. To reproduce under the current project layout, run `tools/probe_storage_context.py`, then run it with `--storage-subgoal-only`, using the existing WSL virtual environment. The referenced maintenance run and model snapshot must remain available.
'''
(root/'outputs/Factorio Storage Decision Diagnostic.md').write_text(report, encoding='utf-8')
print(table)
