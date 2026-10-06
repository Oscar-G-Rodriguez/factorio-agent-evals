"""Annotate this pilot's interrupted run without modifying decision logs."""
import json
from pathlib import Path

root = Path('/home/osci2/factorio-pilot')
for config_path in (root/'runs').glob('*/config.json'):
    config = json.loads(config_path.read_text())
    directory = config_path.parent
    if config.get('context_policy') == 'structured-memory' and not (directory/'summary.json').exists():
        events = (directory/'steps.jsonl').read_text().splitlines()
        note = {'baseline_eligible':False,'comparison_eligible':False,'reason':'Inference process interrupted by CUDA unknown error before final evaluation; see context-experiment-interrupted.txt. Custom kernel was not compiled or loaded.',
                'complete_decisions':len(events),'production_result':'not_measured',
                'hardware_root_cause':'unconfirmed; fresh-process numerical CUDA check passed'}
        (directory/'quality-notes.json').write_text(json.dumps(note,indent=2)+'\n')
        print(directory.name, note['reason'])
source = Path(__file__).resolve().parents[2]/'work'
for filename in ('context-experiment-interrupted.log','rmsnorm-custom.log'):
    (root/'artifacts'/filename.replace('.log','.txt')).write_text((source/filename).read_text())
