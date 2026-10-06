"""Generate one loopback-only server from the installed FLE resources."""
import json
from pathlib import Path
import shutil
import yaml
from fle.cluster.run_envs import ComposeGenerator

root = Path('/home/osci2/factorio-pilot')
state = root / 'cluster'
state.mkdir(parents=True, exist_ok=True)
generator = ComposeGenerator(state_dir=state, work_dir=root)
data = generator.compose_dict(1)
service = data['services']['factorio_0']
service['ports'] = ['127.0.0.1:' + item for item in service['ports']]
service['restart'] = 'no'
# Use an image digest to freeze server contents.
service['image'] = 'factoriotools/factorio@sha256:6471fbfb7eab3abf55bb53fed632606ecf17bf930891bccddff724afab9ed94c'
for volume in service['volumes']:
    if volume['target'] == '/opt/factorio/config':
        config = state / 'config'
        shutil.copytree(volume['source'], config, dirs_exist_ok=True)
        settings = config / 'server-settings.json'
        options = json.loads(settings.read_text())
        options['visibility'] = {'public': False, 'lan': False}
        options['token'] = ''
        settings.write_text(json.dumps(options, indent=2) + '\n')
        volume['source'] = str(config)
(state / 'compose.yaml').write_text(yaml.safe_dump(data, sort_keys=False))
print(f'Prepared one local-only Factorio server: {state / "compose.yaml"}')
