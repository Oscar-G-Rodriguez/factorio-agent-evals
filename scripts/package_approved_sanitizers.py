import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
artifacts = root/'factorio-pilot/evidence/artifacts'
status = json.loads((root/'work/cuda-debugger-validation-status.json').read_text(encoding='utf-8-sig'))
assert status['status'] == 'sanitizers_passed' and status['sanitizer_exit_code'] == 0 and status['registry_restored'] is True
results = []
for name in ('memcheck', 'racecheck', 'initcheck', 'synccheck'):
    log = artifacts/f'rmsnorm-{name}.txt'
    text = log.read_text(encoding='utf-8')
    summaries = [line for line in text.splitlines() if 'SUMMARY:' in line]
    assert summaries and all('0 errors' in line or '0 hazards' in line for line in summaries), (name, summaries)
    # Each sanitizer ran the full 25-case reviewed suite.
    record_line = next(line for line in text.splitlines() if line.startswith('RMSNORM_RESULT '))
    record = json.loads(record_line.removeprefix('RMSNORM_RESULT '))
    assert len(record['correctness_checks']) == 25 and all(c['passed'] for c in record['correctness_checks'])
    results.append({'tool': name, 'summary': summaries, 'correctness_cases_passed': 25,
                    'log': log.relative_to(root/'factorio-pilot').as_posix(), 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
manifest_path = artifacts/'cuda-source-review.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert record['source_hashes'] == {name: manifest['source_hashes']['cuda/'+name] for name in ('rmsnorm.cpp', 'rmsnorm.cu')}
previous = artifacts/'pre-authorization-native-review.json'
if not previous.exists(): shutil.copyfile(manifest_path, previous)
approval = {'status': 'all_four_sanitizers_passed', 'source_hashes': record['source_hashes'],
            'registry_session': status, 'tools': results, 'scope': 'reviewed bounded RMSNorm operator suite; not whole-model inference or native smoke binary'}
(artifacts/'approved-sanitizer-validation.json').write_text(json.dumps(approval, indent=2)+'\n', encoding='utf-8')
shutil.copyfile(root/'work/cuda-debugger-approved-previous.json', artifacts/'cuda-debugger-approved-previous.json')
shutil.copyfile(root/'work/approved-rmsnorm-sanitizers.log', artifacts/'approved-rmsnorm-sanitizers.txt')
manifest['sanitizer_status'] = 'reviewed_rmsnorm_passed_memcheck_racecheck_initcheck_synccheck'
manifest['sanitizer_validation_artifact'] = 'evidence/artifacts/approved-sanitizer-validation.json'
manifest_path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')

readme = root/'factorio-pilot/README.md'
text = readme.read_text(encoding='utf-8')
start = text.index('Compute Sanitizer requires a Windows GPU debugging interface setting')
end = text.index('\n', start)
text = text[:start]+"On October 6, with explicit user permission, the reviewed RMSNorm suite passed memcheck, racecheck, initcheck and synccheck with zero reported errors; each ran all 25 correctness cases. The temporary Windows debugger-interface value was restored to its prior absent state. Evidence is in `evidence/artifacts/approved-sanitizer-validation.json`. This validates the bounded operator suite, not whole-model integration. GPU clocks, power and TDR settings were unchanged."+text[end:]
text = text.replace('The revised binding passed 25 cases, while sanitizer validation remains incomplete pending the Windows debugging-interface authorization.', 'The revised binding passed 25 correctness cases and all four bounded sanitizer checks after user authorization; the temporary setting was restored.')
readme.write_text(text, encoding='utf-8')
review = root/'outputs/CUDA and C++ Source Review.md'
text = review.read_text(encoding='utf-8')
start = text.index('Compute Sanitizer can check memory access')
end = text.index('\n\n', start)
text = text[:start]+"On October 6 the user explicitly authorized the temporary Windows debugging-interface setting. Its previous absent state was recorded, `EnableInterface` alone was enabled, and the reviewed 25-case RMSNorm suite ran under memcheck, racecheck, initcheck and synccheck. Each reported zero errors; the setting was restored afterward and the registry key is absent again. Logs and matching source hashes are in `factorio-pilot/evidence/artifacts/approved-sanitizer-validation.json`. This closes the earlier permission blocker for this check. It covers the bounded RMSNorm operator suite, not third-party libraries generally, whole-model integration, or the separate native smoke binary. See [NVIDIA's sanitizer documentation](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html#windows-specific-behavior)."+text[end:]
review.write_text(text, encoding='utf-8')
protocol_path = root/'outputs/factorio-pilot-protocol.json'
protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
protocol['status'] = 'measured_pilot_complete_reviewed_rmsnorm_sanitizers_passed'
protocol['native_source_review']['sanitizer'] = manifest['sanitizer_status']
protocol['native_source_review']['registry_restored'] = True
protocol['sanitizer_followup'] = approval
protocol_path.write_text(json.dumps(protocol, indent=2)+'\n', encoding='utf-8')
print('Four sanitizer tools passed; exact native source hashes matched; prior registry state restored.')
