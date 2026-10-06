"""Copy small experiment artifacts into the Windows workspace for review."""
import shutil
from pathlib import Path

root = Path('/home/osci2/factorio-pilot')
target = Path('/mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/evidence')
for group in ('artifacts', 'runs'):
    source = root / group
    for path in source.rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.txt', '.pt'):
            destination = target / group / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # DrvFS can deny Linux timestamp/permission copying to Windows.
            shutil.copyfile(path, destination)
print(f'Evidence copied to {target}')
