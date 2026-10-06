"""Build a scoped K02 report from retained validation and timing evidence."""
from pathlib import Path
import argparse
import json
import math
import statistics


def percentile95(values):
    """Use the empirical nearest-rank p95, matching the project operator reports."""
    return sorted(values)[math.ceil(.95*len(values))-1]


def main():
    """Report completed measurements; never turn a partial run into a speed claim."""
    parser = argparse.ArgumentParser()
    parser.add_argument('run_ids', nargs='+')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    runs = [(name,json.loads((repo/'factorio-pilot/evidence/runs'/name/'results.json').read_text())) for name in args.run_ids]
    completed = [data for _,data in runs if data['status']=='offline_benchmark_complete']
    outcome = ''
    if completed:
        ratios = []
        for data in completed:
            for item in data['timing']:
                pairs = []
                for block in range(data['args']['blocks']):
                    a = [s['seconds'] for s in item['samples']['eager'] if s['block']==block]
                    b = [s['seconds'] for s in item['samples']['custom'] if s['block']==block]
                    pairs.append(statistics.median(a)/statistics.median(b))
                ratios.append(statistics.median(pairs))
        outcome = (f' Custom dispatch produced {min(ratios):.2f}–{max(ratios):.2f}× eager/custom '
                   'paired median response ratios across these five prompts. The compiled reference '
                   'varied by prompt; the table below retains gains and slowdowns.')
    lines = ['# K02 - RMSNorm - Integrated inference results', '',
             'The custom C++/CUDA operator was connected to Qwen through an instance-local Python adapter. '
             'The adapter preserves existing weights and restores original forwards after each condition. '
             'This record covers offline saved-prompt inference; no Factorio actions were executed.'+outcome, '',
             '## Methods', '',
             'Five predeclared decisions from the retained A04 episode represent early play, fuel demand, full carrying inventory, '
             'a recent collection failure and a late decision. The prompt manifests retain exact messages, source steps and hashes. '
             'Qwen3-4B-Instruct-2507 uses the pinned revision, BF16, SDPA, greedy generation, an 8,192-token context limit and '
             '256-token output budget with the existing complete-JSON stopping rule. All parameters are frozen for inference.', '',
             'Only 2,560-feature full-width norms are eligible. Attention-head norms remain on the original implementation. '
             'Known unsupported inputs use the original forward; native/load errors stop the custom condition. '
             'Diagnostics record actual dispatch separately from timing. All five native files were re-inspected and their '
             'hash gate passed. A fresh bounded operator suite passed all 25 cases before model integration; no native '
             'sources or GPU settings were changed. Earlier matching sanitizer evidence remains operator evidence.', '',
             'The acceptance gate requires finite checked logits and identical greedy tokens/actions on this fixed manifest. '
             'Logit differences are retained as diagnostics. Agreement on five prompts is not universal numerical or behavioral equivalence.', '',
             '## Validation', '', '| Run | Endpoint | Checked responses | Passing responses |', '| --- | --- | ---: | ---: |']
    for name,data in runs:
        entries = data['validation']
        lines.append(f'| `{name}` | `{data["status"]}` | {len(entries)} | {sum(e["passed"] for e in entries)} |')
    lines += ['', '| Run | Custom norm modules | Custom calls observed | Maximum prefill logit difference |', '| --- | ---: | ---: | ---: |']
    for name,data in runs:
        entries = [e for e in data['validation'] if e['backend']=='custom']
        if entries:
            coverage = entries[0]['coverage']
            lines.append(f'| `{name}` | {len(coverage["replaced_modules"])} | {sum(e["coverage"]["counts"].get("custom",0) for e in entries)} | {max(e["logit_difference"]["max_absolute"] for e in entries):.6g} |')
    lines += ['', 'Logit differences are measured on the final prefill position, not every vocabulary score at every input position. '
              'The forced eight-token decode diagnostic also checks finite logits. Generated JSON envelopes were validated; '
              'parsed-action agreement is an offline result and does not establish executed episode improvement.', '',
              '## Timing and optimized reference', '',
              'Backend switching and adapter installation occur outside the response timer; the live controller installs its adapter once at loading. Complete response timing includes prompt tokenization, transfers, greedy generation, decoding and JSON-envelope validation, '
              'with synchronization at response boundaries. Loading/build costs are separate. First-pass validation latencies '
              'may contain cold initialization or compilation and are not warm benchmark estimates. The forced-token GPU segments '
              'in validation are single diagnostic samples and are not latency distributions.', '']
    if completed:
        lines += ['| Source step | Prompt tokens | Generated tokens |', '| ---: | ---: | ---: |']
        for entry in completed[-1]['validation']:
            if entry['backend']=='eager':
                lines.append(f'| {entry["step"]} | {entry["response"]["input_tokens"]} | {len(entry["response"]["tokens"])} |')
        lines += ['']
    complete = [(name,data) for name,data in runs if data['status']=='offline_benchmark_complete']
    if complete:
        lines += ['Warm response measurements use ten warm-ups and three blocks of 30 alternating samples per backend and prompt. '
                  'Median ratios are calculated from matched within-block medians. Raw samples retain tokens and parsed actions; '
                  'the benchmark stops if token agreement changes.', '',
                  '| Run / step | Backend | Samples | Median response ms | p95 ms | Eager/backend ratio |',
                  '| --- | --- | ---: | ---: | ---: | ---: |']
        for name,data in complete:
            for item in data['timing']:
                eager = item['samples']['eager']
                for backend,samples in item['samples'].items():
                    values = [sample['seconds']*1000 for sample in samples]
                    ratios = []
                    for block in range(data['args']['blocks']):
                        a = [sample['seconds'] for sample in eager if sample['block']==block]
                        b = [sample['seconds'] for sample in samples if sample['block']==block]
                        ratios.append(statistics.median(a)/statistics.median(b))
                    lines.append(f'| `{name}` / {item["step"]} | {backend} | {len(values)} | {statistics.median(values):.3f} | {percentile95(values):.3f} | {statistics.median(ratios):.3f}× |')
    else:
        lines.append('No completed warm-response benchmark is present in this record. Validation-pass latencies are preserved but are not used to claim a speedup.')
    for name,data in runs:
        compiled = [e for e in data['validation'] if e['backend']=='compiled']
        if compiled:
            lines += ['', f'`{name}` attempted the original model forward compiled with Inductor, default mode and dynamic shapes. '
                      f'The first compiled natural response took {compiled[0]["response"]["seconds"]:.2f} seconds, including cold compilation. '
                      'Compiler counters and all validation responses remain in the raw record. A compiled label alone does not prove speedup.']
        if data['errors']:
            lines += ['', f'`{name}` encountered a recorded runtime failure. Its traceback is retained in `results.json`; '
                      'partial validation and timing records are not presented as a completed comparison.']
    lines += ['', '## Evidence and reproduction', '']
    lines += ['The fresh [25-case native check](../factorio-pilot/evidence/artifacts/K02-fresh-rmsnorm-correctness.json) '
              'preceded model loading. Five CPU adapter tests cover guards, unsupported-input fallback and restoration. '
              'Run `python scripts/verify_k02_evidence.py` from any clone for a CPU-only audit of export hashes, '
              'source hashes, frozen prompts, coverage and every retained response/sample.', '']
    for name,data in runs:
        lines.append(f'- [{name} results](../factorio-pilot/evidence/runs/{name}/results.json), '
                     f'[frozen prompts](../factorio-pilot/evidence/runs/{name}/prompt-manifest.json), and '
                     f'[evaluated Python source](../factorio-pilot/evidence/runs/{name}/source/).')
    lines += ['', 'From the repository root in the configured Linux environment:', '', '```bash',
              'export FACTORIO_PILOT_HOME="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"',
              'bash factorio-pilot/setup/run-integrated-rmsnorm.sh --phase validate',
              'bash factorio-pilot/setup/run-integrated-rmsnorm.sh --phase benchmark --include-compiled', '```', '',
              'The runtime must contain the pinned model and matching operator correctness artifact. Read the '
              '[native review](CUDA%20and%20C%2B%2B%20Source%20Review.md) before GPU execution. Each run writes fresh K02 evidence; '
              'preserve old artifacts before repeating native checks. Native row bounds, unsupported-call handling and the '
              '[acceleration design](../docs/Inference%20Acceleration%20Design.md) remain applicable.', '',
              '## Limits', '',
              'This uses five states from one development fixture, not held-out fixtures or live episodes. '
              'Warm total-response timing is distinct from the single prefill/forced-decode diagnostic samples. '
              'Prefix-cache reuse and training remain separate work. The forward-only kernel supplies no backward path. '
              'No episode-wall-time speedup or improved factory maintenance follows from these offline measurements.', '']
    target = repo/'outputs/K02 - RMSNorm - Integrated Inference Results.md'
    if target.exists():
        raise RuntimeError('Preserve the previous K02 report before replacing it')
    target.write_text('\n'.join(lines),encoding='utf-8')
    print(str(target))


if __name__ == '__main__':
    main()
