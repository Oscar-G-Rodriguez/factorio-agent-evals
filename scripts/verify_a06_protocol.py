"""Check the frozen A06 recipes and split without game, model or GPU execution."""

import hashlib
import json
from pathlib import Path


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def check_protocol(root: Path) -> dict:
    """Validate design consistency; this does not establish live reachability."""
    path = root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json'
    protocol = json.loads(path.read_text(encoding='utf-8'))
    assert protocol['protocol_id'] == 'a06-qwen-sft-v1'
    assert protocol['stage_status'] == 'recipes_frozen_live_validation_pending'
    assert protocol['learning_method'] == 'supervised_qlora'
    task = protocol['task']
    assert task == {'decision_interval_ticks': 900, 'window_ticks': 3600,
                    'target_new_plates_per_window': 16, 'consecutive_low_windows_to_fail': 2,
                    'max_simulated_seconds': 1200, 'max_decisions': 80,
                    'wall_time_limit_seconds': 600, 'game_speed': 10,
                    'carry_capacity': 100, 'furnace_capacity': 100,
                    'chest_capacity': 1600, 'max_refill_coal': 3,
                    'warmup_seconds': 60, 'min_warmup_new_plates': 16}
    context = protocol['context']
    assert context['observation_policy'] == 'automatic'
    assert context['history_pairs'] == 2
    assert context['max_prompt_tokens'] + context['max_new_tokens'] == context['max_total_tokens'] == 4096
    assert context['max_new_tokens'] == 256
    assert context['guide_sha256'] == hashlib.sha256((root / context['guide_path']).read_bytes()).hexdigest()
    assert protocol['model']['revision'] == 'cdbee75f17c01a7cc42f958dc650907174af0554'
    assert protocol['comparison']['conditions'] == ['unchanged_bf16', 'unchanged_4bit', 'qlora_4bit']
    assert protocol['comparison']['do_sample'] is False
    assert protocol['comparison']['custom_rmsnorm'] is False
    assert protocol['dataset']['optimizer_partition'] == 'train'
    assert protocol['dataset']['loss_scope'] == 'target_assistant_action_and_end_token_only'
    assert protocol['fixture_preparation']['live_validation_required'] is True
    assert protocol['fixture_preparation']['burning_energy_absolute_tolerance_joules'] == 1
    expected_counts = {'train': 4, 'validation': 2, 'test': 3}
    counts = dict.fromkeys(expected_counts, 0)
    ids = set()
    preset_hashes = set()
    for fixture in protocol['fixtures']:
        assert fixture['id'] not in ids, 'Duplicate fixture ID'
        ids.add(fixture['id'])
        counts[fixture['partition']] += 1
        presets = fixture['presets']
        assert set(presets) == {'drill_coal', 'drill_burning_joules', 'furnace_coal',
                                'furnace_burning_joules', 'output_plates', 'carried_plates',
                                'chest_plates', 'reserve_coal'}
        assert all(type(value) is int for value in presets.values())
        assert 0 <= presets['drill_coal'] <= 3 and 0 <= presets['furnace_coal'] <= 3
        assert 0 < presets['drill_burning_joules'] <= 4000000
        assert 0 < presets['furnace_burning_joules'] <= 4000000
        assert 0 <= presets['output_plates'] <= task['furnace_capacity']
        assert 0 <= presets['carried_plates'] <= task['carry_capacity']
        assert 0 <= presets['chest_plates'] <= task['chest_capacity']
        assert 100 <= presets['reserve_coal'] <= 400
        digest = hashlib.sha256(canonical(presets)).hexdigest()
        assert digest == fixture['preset_sha256']
        assert digest not in preset_hashes, 'Identical recipe reused across partitions'
        preset_hashes.add(digest)
        # Necessary inventory-room bound, not proof of achievable throughput.
        room = sum(task[capacity] - presets[count] for capacity, count in
                   [('furnace_capacity', 'output_plates'), ('carry_capacity', 'carried_plates'),
                    ('chest_capacity', 'chest_plates')])
        assert room >= 20 * 16, 'Insufficient room for the minimum horizon production'
    assert counts == expected_counts
    state = root / protocol['fixture_preparation']['starting_state_path']
    assert hashlib.sha256(state.read_bytes()).hexdigest() == protocol['fixture_preparation']['starting_state_file_sha256']
    paths = ['outputs/A06 - Qwen Fine Tuning - Protocol.md',
             'factorio-pilot/protocols/a06-qwen-sft-v1.json',
             context['guide_path'], 'scripts/verify_a06_protocol.py']
    return {'protocol_id': protocol['protocol_id'], 'fixture_counts': counts,
            'unique_recipes': len(preset_hashes), 'status': 'design_consistency_passed',
            'live_fixture_validation': 'pending', 'dataset_validation': 'pending',
            'training': 'not_started',
            'files_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}}


if __name__ == '__main__':
    print(json.dumps(check_protocol(Path(__file__).resolve().parents[1]), indent=2))
