"""CPU-only source review gate. This never approves a changed source automatically."""
import argparse
import hashlib
import json
from pathlib import Path

NATIVE_SUFFIXES = {'.c', '.cc', '.cpp', '.cu', '.cuh', '.h', '.hpp'}

def native_inventory(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob('*'))
            if path.is_file() and path.suffix in NATIVE_SUFFIXES and '.git' not in path.parts}

def assert_review_current(stage='runtime', root=None, correctness_path=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    record_path = root/'evidence/artifacts/cuda-source-review.json'
    if not record_path.exists():
        raise RuntimeError('Native source review is missing; review all C++/CUDA before running.')
    record = json.loads(record_path.read_text())
    if record.get('status') != 'static_review_complete' or record.get('unresolved_launch_blockers'):
        raise RuntimeError('Native source review has unresolved launch blockers.')
    if native_inventory(root) != record['source_hashes']:
        raise RuntimeError('Native source files changed or were added/removed. A fresh code review is required.')
    if stage == 'benchmark':
        result_path = Path(correctness_path) if correctness_path else Path('/home/osci2/factorio-pilot/artifacts/rmsnorm-correctness.json')
        if not result_path.exists():
            raise RuntimeError('Run the reviewed bounded --tests-only suite before benchmarking.')
        result = json.loads(result_path.read_text())
        source_hashes = {name:record['source_hashes'][f'cuda/{name}'] for name in ('rmsnorm.cpp','rmsnorm.cu')}
        checks = result.get('correctness_checks', [])
        required = set(record['required_correctness_cases'])
        if result.get('source_hashes') != source_hashes or not checks or not all(c.get('passed') is True for c in checks) or not required.issubset(c['case'] for c in checks):
            raise RuntimeError('Correctness evidence is incomplete or belongs to different native sources.')
    elif stage not in ('runtime','correctness'):
        raise ValueError('Unknown review stage')
    return record

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('runtime','correctness','benchmark'), default='runtime')
    args = parser.parse_args()
    review = assert_review_current(args.stage)
    print(f"REVIEW_GATE_PASS stage={args.stage}; sanitizer={review['sanitizer_status']}")
