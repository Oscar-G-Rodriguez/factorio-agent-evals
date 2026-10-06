"""Retain the large diagnostic profile in Git without changing its original bytes."""
import gzip
import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root/'factorio-pilot/evidence/artifacts/inference-profile.json'
target = source.with_suffix('.json.gz')
with source.open('rb') as original, target.open('wb') as packed:
    with gzip.GzipFile(filename='', mode='wb', fileobj=packed, mtime=0) as stream:
        shutil.copyfileobj(original, stream)
digest = hashlib.sha256(source.read_bytes()).hexdigest()
with gzip.open(target, 'rb') as stream:
    assert hashlib.sha256(stream.read()).hexdigest() == digest
record = {'original': source.name, 'compressed': target.name,
          'original_bytes': source.stat().st_size, 'compressed_bytes': target.stat().st_size,
          'original_sha256': digest, 'compressed_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'decompression_hash_verified': True}
source.with_name('inference-profile-archive.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
print(json.dumps(record))
