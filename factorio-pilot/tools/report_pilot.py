"""Validate comparison controls and produce a report from saved evidence."""
import hashlib
import json
import math
from pathlib import Path
import statistics
from collections import Counter

project = Path('/home/osci2/factorio-pilot')
workspace = Path(__file__).resolve().parent.parent
rows = []
controls = []
eligible = []
for path in sorted((project/'runs').glob('*/summary.json')):
    config = json.loads((path.parent/'config.json').read_text())
    if config.get('context_policy') not in ('history','structured-memory') or 'context_memory.py' not in config.get('source_hashes',{}):
        continue
    eligible.append((path, config))
assert eligible, 'No corrected-interface runs found'
latest_hashes = eligible[-1][1]['source_hashes']
selected = []
for policy in ('history','structured-memory'):
    matching = [(p,c) for p,c in eligible if c['context_policy']==policy and c['source_hashes']==latest_hashes]
    selected.extend(matching[-2:])
for path, config in sorted(selected, key=lambda pair: pair[0]):
    summary = json.loads(path.read_text())
    events = [json.loads(line) for line in (path.parent/'steps.jsonl').read_text().splitlines()]
    latencies = sorted(e['response_seconds'] for e in events)
    assert all(w['actual_ticks']==3600 for w in summary['measurement_windows'])
    assert all(e['memory_tokens'] <= 512 for e in events)
    assert all(e['actual_game_ticks_before'] <= e['actual_game_ticks_after'] for e in events)
    controls.append({k: config[k] for k in ('starting_state_sha256','actual_map_seed','model','source_hashes','max_decisions','sampling','max_total_sequence_tokens','max_new_tokens','system_prompt','precision','attention_backend','seed','tick_policy','pathfinder_poll_attempt_limit')})
    rows.append({'run':path.parent.name,'context_policy':config['context_policy'],
        'decisions':len(events),'failed_actions':summary['failed_actions'],
        'failed_action_rate':summary['failed_actions']/len(events),
        'plates':[w['iron_plates'] for w in summary['measurement_windows']],
        'median_response_seconds':statistics.median(latencies),
        'p95_response_seconds':latencies[math.ceil(.95*len(latencies))-1],
        'input_tokens':sum(e['input_tokens'] for e in events),
        'output_tokens':sum(e['output_tokens'] for e in events),
        'responses_at_token_limit':sum(e['generation_reached_token_limit'] for e in events),
        'failure_classes':dict(Counter(e['error'].split(':',1)[0] for e in events if e['error'])),
        'environment_seconds':sum(e['environment_seconds'] for e in events),
        'wall_seconds_including_evaluation':summary['wall_seconds'],
        'peak_allocated_gib':max(e['peak_allocated_bytes'] for e in events)/1024**3,
        'max_memory_tokens':max(e['memory_tokens'] for e in events),
        'history_messages_dropped':sum(e['dropped_history_messages'] for e in events),
        'stop_reason':summary['stop_reason'],'task_success':summary['task_success']})
assert len(rows)==4 and sum(r['context_policy']=='history' for r in rows)==2, 'Need exactly two runs per condition'
assert all(c==controls[0] for c in controls), 'Comparison controls differ'
reference = json.loads((project/'artifacts/reference-factory.json').read_text())
assert reference['target_met'] and reference['only_coal_inserted'] and reference['pickup_handle_invalidation_verified']
kernel = json.loads((project/'artifacts/rmsnorm-custom-benchmark.json').read_text())
assert all(c['passed'] for c in kernel['correctness_checks'])
report = {'context_runs':rows,'controls_match':True,'reference_windows':reference['measurement_windows'],
          'cuda':kernel,'sanitizer':'blocked_debug_interface_permission_pending',
          'claims':'one-model one-map short engineering pilot; no significance or end-to-end speed claim'}
(project/'artifacts/pilot-results.json').write_text(json.dumps(report,indent=2)+'\n')
production_finding = ('All four model runs produced zero iron plates.' if all(all(p==0 for p in r['plates']) for r in rows)
                      else 'Model production varied across runs; the table records each measured window and positive output still requires a supply-chain audit.')
memory_finding = ('Neither context condition reached the production target.' if not any(all(p>=16 for p in r['plates']) for r in rows)
                 else 'Some runs reached the throughput target; verified task success still requires the recorded supply-chain audit.')
text = ['# Factorio local agent pilot preliminary results','',
        'The local Qwen agent and its observed-fact memory were evaluated on an RTX 5070 Ti. '+production_finding+' A scripted control verified the production target is reachable. The custom C++/CUDA RMSNorm passed numerical checks and was benchmarked against the installed operator; whole-model benefit was not measured and sanitizer validation remains pending. These are preliminary engineering results for a future longer-running study.','',
        '## Factory and context experiment','',
        'The scripted reachability control produced '+', '.join(str(w['iron_plates']) for w in reference['measurement_windows'])+' iron plates in its two 60-second windows. It inserted only supplied coal, verified pause/tick control and pickup handle invalidation, and is excluded from model results. Final furnace ore/plate inventories and the action trace support automatic drill-to-furnace supply.','',
        '| Context | Decisions | Failed actions | Plates in windows | Median response | Input tokens | Peak allocated GPU memory |',
        '| --- | ---: | ---: | --- | ---: | ---: | ---: |']
for row in rows:
    text.append(f"| {row['context_policy']} | {row['decisions']} | {row['failed_actions']} ({row['failed_action_rate']:.1%}) | {row['plates']} | {row['median_response_seconds']:.2f} s | {row['input_tokens']:,} | {row['peak_allocated_gib']:.2f} GiB |")
text += ['', 'Both conditions use the same corrected tools, model revision, starting-state hash, map seed, source hashes, 32-decision budget, greedy decoding, BF16 inference and token limits. The only condition change is a memory supplement capped at 512 tokenizer tokens. It retains last-observed equipment facts and up to four failures, discarding complete old records when necessary; picked-up handles are invalidated. It does not access hidden state or use another model.', '',
         memory_finding+' The small sample and differing trajectories do not establish a reliable memory benefit.', '',
         'History messages dropped per included run: '+', '.join(f"{r['context_policy']}={r['history_messages_dropped']}" for r in rows)+'. Maximum memory supplement per run: '+', '.join(str(r['max_memory_tokens']) for r in rows)+' tokens.', '',
         'Output token totals per included run: '+', '.join(str(r['output_tokens']) for r in rows)+'. Responses reaching the 1,024-token cap: '+', '.join(str(r['responses_at_token_limit']) for r in rows)+'. Failures are separated by exception class in the saved metrics.', '',
         'Each evaluation pauses the game during reasoning, allows asynchronous movement with actual ticks logged, warms up for 60 simulated seconds, then measures two unattended 3,600-tick windows. Success requires at least 16 plates in both windows and a supply-chain audit. Positive throughput without that audit remains unconfirmed.', '',
         '## C++ and CUDA experiment', '',
         'The Python-callable C++ wrapper checks shape, dtype, device, contiguity and inference-only usage. The CUDA kernel normalizes each 2,560-feature row with one 256-thread block, FP32 reduction and explicit BF16 rounding before learned-weight multiplication. It follows the current PyTorch stream and does not modify the model.', '',
         f"All {len(kernel['correctness_checks'])} numerical, boundary and stream checks passed. Captured model tensors and synthetic inputs were compared with the installed Qwen operator and a float64 reference with BF16 rounding, using rtol=0.02 and atol=1e-5. This allows small numerical differences; it does not promise identical model token choices.", '',
         '| Phase | Reference median across batches | Custom median across batches | Median paired speedup |',
         '| --- | ---: | ---: | ---: |']
for phase in kernel['benchmark']:
    text.append(f"| {phase['phase']} | {statistics.median(b['reference']['median_ms'] for b in phase['batches']):.4f} ms | {statistics.median(b['custom']['median_ms'] for b in phase['batches']):.4f} ms | {statistics.median(b['speedup'] for b in phase['batches']):.2f}x |")
text += ['', 'Timing uses alternating reference/custom order, ten warm-ups per implementation and 100 pairs in each of three batches. Both operators include output allocation; inputs already reside on the GPU. CUDA-event samples include possible launch gaps. Raw samples and p95 values are saved. Operator gains do not establish faster complete model responses; full-model integration is deferred.', '',
         '## Limits and next experiments', '',
         'One model, one map and two greedy repetitions per condition support descriptive findings only. Absolute game ticks and movement timing can differ and appear in observations, so repeated runs do not receive bit-identical prompts. Greedy repetitions are not independent sampling draws. Prior signatures-only runs remain archived separately because they used a different tool contract. Some FLE warnings reported blocked output despite actual ore transfer; throughput and final inventories are stronger evidence than those warnings.', '',
         'An earlier memory attempt stopped with a CUDA unknown error during ordinary Qwen inference before a final production measurement. It is excluded from the comparison, with its partial log and explicit quality note retained. Its preceding complete history run is also archived outside the fresh four-run comparison. The custom kernel was not compiled or loaded at the interruption; the underlying cause remains unconfirmed. A fresh-process CUDA numerical check passed before retrying. The first custom-kernel build also failed because a broad PyTorch header required an unavailable sparse-library header; using the narrower CUDA stream header resolved that build dependency.', '',
         'Next: report elapsed ticks from reset to reduce incidental prompt differences, and test concise valid tool-call examples against the observed item/handle confusion. Then use longer runs that force history truncation and explicit recovery tasks. More map seeds, additional models and whole-model kernel integration follow after that. If no history was dropped in a run, its memory-retention benefits remain untested even though the memory supplement was evaluated.', '',
         'Compute Sanitizer remains blocked by the Windows debugging interface. Automatic approval review rejected its persistent system-wide registry change without explicit permission. Numerical checks passed, but sanitizer validation is incomplete. No power, clock or timeout settings were changed.', '',
         'The implementation was produced with Codex assistance. Independent mastery requires Oscar to explain, modify and rerun the important pieces; code generation alone does not demonstrate it.', '',
         '## Reproduction and evidence', '',
         'See `factorio-pilot/README.md` for commands and pinned dependencies. `evidence/artifacts/pilot-results.json` contains all metrics; individual run folders contain prompts, configurations, decisions, errors and factory states. `source-snapshots/context-pilot` preserves the evaluated source.']
text += ['', '## Sources', '',
         '- [Factorio Learning Environment](https://github.com/JackHopkins/factorio-learning-environment) and [original FLE paper](https://arxiv.org/abs/2503.09617). The environment is prior work; this pilot evaluates a small local integration.',
         '- [Qwen3 model](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).',
         '- [PyTorch C++ and CUDA operators](https://docs.pytorch.org/tutorials/advanced/cpp_custom_ops.html).',
         '- [NVIDIA Compute Sanitizer](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html#windows-specific-behavior).']
out = workspace.parent/'outputs'/'Factorio Pilot Preliminary Report.md'
out.write_text('\n'.join(text)+'\n')
print(json.dumps({'report':str(out),'context_runs':rows,'controls_match':True},indent=2))
