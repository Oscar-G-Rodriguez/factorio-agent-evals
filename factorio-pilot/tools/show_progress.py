"""Read the latest decision log without touching the running experiment."""
from runtime_paths import runtime_home

import json
import sys
from pathlib import Path

paths = list(runtime_home() / 'runs'.glob('*/steps.jsonl'))
path = max(paths, key=lambda p:p.stat().st_mtime)
events = [json.loads(line) for line in path.read_text().splitlines(keepends=True) if line.endswith('\n') and line.strip()]
try:
    config = json.loads((path.parent/'config.json').read_text())
except (FileNotFoundError, json.JSONDecodeError):
    print(json.dumps({'run':path.parent.name,'status':'loading_model_or_resetting_game'}))
    sys.exit(0)
print(json.dumps({'run':path.parent.name,'context_policy':config.get('context_policy'),
    'decisions_logged':len(events),'failed_actions':sum(e['failed_action'] for e in events),
    'responses_at_token_limit':sum(e['generation_reached_token_limit'] for e in events),
    'history_messages_dropped':sum(e['dropped_history_messages'] for e in events),
    'last_response_seconds':events[-1]['response_seconds'] if events else None,
    'max_memory_tokens':max((e.get('memory_tokens',0) for e in events),default=0),
    'evaluation_saved':(path.parent/'summary.json').exists()},indent=2))
