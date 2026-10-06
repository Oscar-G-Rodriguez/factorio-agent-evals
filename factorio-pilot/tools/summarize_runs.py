"""Summarize complete attempts; keep repeats separate and preserve negatives."""
from runtime_paths import runtime_home

import json
import math
import statistics
from collections import Counter
from pathlib import Path

root = runtime_home()
results = []
for summary_path in sorted(root.glob('runs/*/summary.json')):
    directory = summary_path.parent
    summary = json.loads(summary_path.read_text())
    steps = [json.loads(line) for line in (directory / 'steps.jsonl').read_text().splitlines()]
    config = json.loads((directory / 'config.json').read_text())
    annotation = json.loads((directory / 'quality-notes.json').read_text()) if (directory / 'quality-notes.json').exists() else {}
    latencies = sorted(step['response_seconds'] for step in steps)
    failures = Counter()
    for step in steps:
        if step['failed_action']:
            failures[(step.get('action') or {}).get('tool', 'parse')] += 1
    results.append({
        'run': directory.name, 'mode': summary['mode'], 'seed': config['seed'],
        'baseline_eligible': annotation.get('baseline_eligible', True),
        'quality_notes': annotation,
        'decisions': len(steps), 'failed_actions': summary['failed_actions'],
        'failed_actions_by_tool': dict(failures),
        'iron_plates_per_window': [window['iron_plates'] for window in summary['measurement_windows']],
        'window_ticks': [window['actual_ticks'] for window in summary['measurement_windows']],
        'task_success': summary['task_success'],
        'response_median_seconds': statistics.median(latencies),
        'response_p95_seconds_nearest_rank': latencies[math.ceil(0.95 * len(latencies)) - 1],
        'total_input_tokens': sum(step['input_tokens'] for step in steps),
        'total_output_tokens': sum(step['output_tokens'] for step in steps),
        'peak_torch_allocated_gib': max(step['peak_allocated_bytes'] for step in steps) / 1024**3,
        'wall_seconds_including_final_evaluation': summary['wall_seconds'],
        'stop_reason': summary['stop_reason'],
        'sampling_diversity': False if config['sampling']['do_sample'] is False else None,
    })
report = {'complete_runs': results,
    'memory_method': 'PyTorch peak live allocated bytes; excludes memory owned by other applications.',
    'repeat_limit': 'Greedy repeats with different seeds are not independent sampling draws.',
    'diagnostic_prompt_limitation': 'The first two attempts lacked verified seed tracking and are excluded. The controlled baseline has signatures but empty tool descriptions. The intervention adds verified controller descriptions; this is a usability correction, not a novel algorithm.',
    'research_claim': 'Preliminary engineering pilot; no general model-ranking or novel memory claim.'}
(root / 'artifacts' / 'run-metrics.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
