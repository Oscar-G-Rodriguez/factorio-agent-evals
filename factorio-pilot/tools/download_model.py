"""Download one official model revision without loading it onto the GPU."""
import json
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

root = Path('/home/osci2/factorio-pilot')
artifacts = root / 'artifacts'
artifacts.mkdir(parents=True, exist_ok=True)
model_id = 'Qwen/Qwen3-4B-Instruct-2507'
metadata = artifacts / 'model-revision.json'
if metadata.exists():
    revision = json.loads(metadata.read_text())['revision']
else:
    revision = HfApi().model_info(model_id).sha
    metadata.write_text(json.dumps({
        'model_id': model_id, 'revision': revision,
        'resolved_at_utc': datetime.now(timezone.utc).isoformat(),
    }, indent=2) + '\n')
local_path = snapshot_download(
    model_id, revision=revision, cache_dir=root / 'model-cache',
    allow_patterns=['*.json', '*.safetensors', '*.txt', '*.model', '*.jinja'],
    max_workers=2,
)
data = json.loads(metadata.read_text())
data['snapshot_path'] = local_path
metadata.write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps(data, indent=2))
