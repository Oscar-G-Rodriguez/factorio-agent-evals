"""Export bounded research evidence and source receipts; never copy model weights."""
import argparse
import csv
import json
import shutil
from pathlib import Path
from a06_workflow import read,write,sha


def package(workflow,root,runtime):
    state=read(workflow/'state.json')
    output=root/'factorio-pilot/evidence/experiments'/workflow.name
    output.mkdir(parents=True,exist_ok=False)
    summaries=[]
    runs={Path(r['run']) for r in state['completed_jobs'] if r.get('run')}
    runs|={Path(p) for p in state['training'].values()}
    runs|={Path(p) for p in state.get('training_attempts',[]) if Path(p).exists()}
    if state.get('preflight_run'):runs.add(Path(state['preflight_run']))
    runs|={Path(p) for p in state['corrections'].values()}
    def copy_files(source,destination):
        destination.mkdir(parents=True,exist_ok=True)
        for path in source.rglob('*'):
            if not path.is_file() or path.suffix not in ('.json','.jsonl','.log','.py','.txt','.csv'):
                continue
            # Checkpoint receipts are evidence; tensors and weights stay external.
            if path.stat().st_size>25*1024*1024: continue
            target=destination/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
    copy_files(workflow,output/'workflow')
    for run in sorted(runs):
        if run.parent!=runtime/'runs': raise ValueError('Run outside external runtime')
        copy_files(run,output/'runs'/run.name)
        if (run/'summary.json').exists():
            summary=read(run/'summary.json')
            if 'condition' in summary: summaries.append(dict(summary,run=run.name))
    fields=('run','purpose','fixture_id','condition','stop_reason','simulated_seconds','new_iron_plates',
            'failed_actions','failed_action_rate','waits_during_maintenance_opportunity',
            'input_tokens','output_tokens','median_response_seconds','peak_allocated_bytes','peak_reserved_bytes')
    with (output/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(summaries)
    curves=[]
    for round_number,path in state['training'].items():
        for line in (Path(path)/'training.jsonl').read_text().splitlines():
            row=json.loads(line)
            if 'mean_loss' in row: curves.append({'round':int(round_number),**row})
    if curves:
        with (output/'training-curves.csv').open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(curves[0]));writer.writeheader();writer.writerows(curves)
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig,ax=plt.subplots(figsize=(7,4))
            for number in sorted({r['round'] for r in curves}):
                subset=[r for r in curves if r['round']==number]
                ax.plot([r['optimizer_step'] for r in subset],[r['mean_loss'] for r in subset],label=f'Round {number}')
            ax.set(xlabel='Optimizer update',ylabel='Mean target-token training loss',title='Training loss; gameplay measured separately')
            ax.legend();fig.tight_layout();fig.savefig(output/'training-curves.svg');plt.close(fig)
        except ImportError:
            write(output/'plot-status.json',{'available':False,'reason':'matplotlib unavailable; exact curve data retained as CSV'})
    final=[r for r in summaries if r['purpose']=='final-test']
    completed_rounds=len(state['training'])
    report=['# A06 Qwen fine tuning: three-round results','',
        f'Workflow `{workflow.name}`. Recorded phase: **{state["phase"]}**; completed training rounds: **{completed_rounds}/3**.', '',
        '## Methods','',
        'Single-seed QLoRA on Qwen3-4B-Instruct-2507. Original four train, two validation and three test fixtures share one factory layout. '
        'The guide, automatic observations, two history pairs, greedy decoding and 15-second simulation cadence are held fixed. '
        'Adapters are trained separately from gameplay; base weights remain frozen. Each round selects update 20 or 40 using validation survival, plates and earliest checkpoint. '
        'Corrections require train-only execution from exact native pre-action state and successful continuation through the original horizon. '
        'No custom RMSNorm is used in this comparison.','',
        '## Results','',
        '| Purpose | Condition | Factory | Survival (s) | New plates | Failed actions | Endpoint |',
        '| --- | --- | --- | ---: | ---: | ---: | --- |']
    for row in summaries:
        report.append(f'| {row["purpose"]} | {row["condition"]} | {row["fixture_id"]} | {row["simulated_seconds"]:g} | {row["new_iron_plates"]} | {row["failed_actions"]} | {row["stop_reason"]} |')
    report+=['','Full token, latency and GPU-memory measurements are in `comparison.csv`; target-token losses are in `training-curves.csv` when training completed.','',
        '## Failures and limitations','',
        state.get('error','No workflow stop error recorded.'),
        'Survival is capped at 1,200 simulated seconds. Wall-time cutoffs are incomplete observations, not game failures. '
        'Waiting-opportunity flags are heuristics, not causal proof. First-token latency includes prompt processing and first-token generation. '
        'Three related test factories and one seed do not establish broad generalization or statistical significance. '
        'Validation-selected checkpoints and training losses cannot substitute for final test results.','',
        '## My contribution','',
        'Built the constrained JSON game adapter, visible-context boundary, fixture and failure evaluation, supervised-data verification, '
        'QLoRA workflow, native-state correction replays, checkpoint selection and analysis. FLE supplies the game connection; '
        'Qwen supplies pretrained weights; PyTorch, PEFT and bitsandbytes supply training primitives. '
        'The separate project-authored C++/CUDA RMSNorm experiment retains its own correctness and inference timing evidence.','',
        '## Resume evidence','',
        f'- Implemented an audited local QLoRA and Factorio evaluation pipeline; completed {completed_rounds} training rounds and {len(summaries)} logged model episodes in this workflow.',
        '- Gameplay improvement claims require the matched final-test rows; no training-loss-only improvement claim is made.','',
        '## Reproduction','',
        'Use the pinned external runtime, model revision and package freeze recorded under the workflow evidence. '
        'Read the three-round protocol and native review before GPU execution. Reproduce from the public checkout using '
        '`a06_orchestrate.py --runtime-home <external-runtime> --owner <ordinary-user>` as the Docker supervisor. '
        'Adapters, optimizer tensors, native game archives and model weights remain outside Git; their hashes and receipts are retained.','']
    report_path=root/'outputs'/('A06 - Qwen Fine Tuning - Three Round Results '+workflow.name.removeprefix('A06-three-round-')+'.md')
    report_path.write_text('\n'.join(report))
    write(output/'manifest.json',{'workflow':workflow.name,'protocol_sha256':state['protocol_sha256'],
        'files_sha256':{p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()},
        'report_path':report_path.relative_to(root).as_posix(),'report_sha256':sha(report_path),'completed_rounds':completed_rounds,
        'final_episodes':len(final),'all_three_rounds_and_final_tests_complete':completed_rounds==3 and len(final)==15 and
        all(r['stop_reason'] in ('survived_simulation_limit','sustained_production_failure') for r in final)})
    print(json.dumps({'output':str(output),'report':str(report_path),'completed_rounds':completed_rounds,'final_episodes':len(final)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-home',type=Path,required=True);parser.add_argument('--workflow',type=Path,required=True)
    args=parser.parse_args();package(args.workflow,Path(__file__).resolve().parents[2],args.runtime_home.resolve())
