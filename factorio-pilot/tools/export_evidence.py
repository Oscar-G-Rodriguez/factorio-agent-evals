"""Copy small experiment artifacts into this checkout using staged run names."""
import re
import shutil
from pathlib import Path

root = Path('/home/osci2/factorio-pilot')
target = Path(__file__).resolve().parents[1] / 'evidence'


def staged_name(name):
    if re.fullmatch(r'[AK]\d{2}-[a-z0-9-]+-\d{8}T\d{6}Z(?:-seed\d+)?', name):
        return name
    for prefixes, stage in (
        (('baseline-', 'intervention-', 'development-'), 'A01'),
        (('working-development-',), 'A02'),
        (('logistics-development-',), 'A03'),
        (('maintenance-',), 'A04'),
    ):
        if name.startswith(prefixes):
            return f'{stage}-{name}'
    raise ValueError(f'Unrecognized run name: {name}')


for group in ('artifacts', 'runs'):
    source = root / group
    for path in source.rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.txt', '.pt'):
            relative = path.relative_to(source)
            if group == 'runs':
                relative = Path(staged_name(relative.parts[0]), *relative.parts[1:])
            destination = target / group / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            # DrvFS can deny Linux timestamp/permission copying to Windows.
            shutil.copyfile(path, destination)
print(f'Evidence copied to {target}')
