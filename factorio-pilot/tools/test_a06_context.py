"""CPU regression checks for A06 visibility, chronology and optimizer isolation."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from a06_context import (canonical, digest, pad_encoding, project, render, semantic_messages,
                         training_encoding, validate_action, validate_payload)
from a06_dataset import TRAIN_RUNS, optimizer_rows, ROW_FIELDS
from observation_policy import ObservationPolicy


class Tokenizer:
    eos_token_id = 9

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False):
        ids = []
        for m in messages:
            ids += [1, {'system': 2, 'user': 3, 'assistant': 4}[m['role']]]
            ids += [ord(c) + 10 for c in m['content']] + [9, 8]
        return ids + ([1, 4] if add_generation_prompt else [])


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        run = self.root / 'factorio-pilot/evidence/runs' / TRAIN_RUNS['train_carry']
        self.steps = [json.loads(line) for line in (run / 'scripted/steps.jsonl').read_text().splitlines()]
        self.visibility = ObservationPolicy('automatic', self.steps[0]['observation_before'], 0)
        self.payload = project(self.visibility.visible(0))

    def test_visible_projection_rejects_metadata_and_raw_exceptions(self):
        visible = self.visibility.visible(0)
        visible['fixture_id'] = 'hidden'
        with self.assertRaises(ValueError):
            project(visible)
        visible = self.visibility.visible(0)
        visible['observation']['equipment'][0]['teacher_hint'] = 'store'
        with self.assertRaises(ValueError):
            project(visible)
        visible = self.visibility.visible(0)
        visible['result'] = {'ok': False, 'tool': 'wait', 'error': 'raw exception secret'}
        with self.assertRaises(ValueError):
            project(visible)
        self.assertNotIn('production', self.payload['observation'])
        self.assertNotIn('physical_plate_space', self.payload['observation']['carrying'])
        validate_payload(self.payload)

    def test_windows_feedback_only_after_execution_and_relative_ticks(self):
        origin = self.steps[0]['tick_before']
        windows = []
        for i, step in enumerate(self.steps[:5]):
            before = project(self.visibility.visible(i*900))
            self.assertEqual(len(before['recent_production_windows']), 0 if i < 4 else 1)
            if step['window']:
                w = deepcopy(step['window'])
                w['start_tick'] -= origin
                w['end_tick'] -= origin
                windows.append(w)
            self.visibility.update(step['observation_after'], (i+1)*900, step['action'], step['result'], None, windows)
        self.assertEqual(project(self.visibility.visible(4500))['recent_production_windows'][0]['start_tick'], 0)
        self.assertNotIn('consecutive_low_windows', project(self.visibility.visible(4500))['recent_production_windows'][0])
        self.assertNotIn('below_target', project(self.visibility.visible(4500))['recent_production_windows'][0])
        self.assertEqual(project(self.visibility.visible(4500))['result']['ok'], True)

    def test_handles_counts_and_capacities(self):
        validate_action(self.steps[0]['action'], self.payload)
        for action in ({'tool': 'fuel', 'args': {'building_handle': 'stale', 'coal_count': 3}},
                       {'tool': 'fuel', 'args': {'building_handle': 'e2', 'coal_count': True}},
                       {'tool': 'store_plates', 'args': {'chest_handle': 'e1', 'plate_count': 101}},
                       {'tool': 'finish', 'args': {}}):
            with self.assertRaises(ValueError):
                validate_action(action, self.payload)
        p = deepcopy(self.payload)
        p['observation']['carrying']['available_carry_space'] = 1
        with self.assertRaises(ValueError):
            validate_payload(p)

    def test_whole_pair_trimming_and_essential_rejection(self):
        tok = Tokenizer()
        action = self.steps[0]['action']
        current = deepcopy(self.payload)
        current.update(elapsed_ticks=2700, observation_tick=2700)
        previous = []
        for tick in (0, 900, 1800):
            p = deepcopy(self.payload)
            p.update(elapsed_ticks=tick, observation_tick=tick)
            previous.append((p, action))
        base, count, _ = render('guide', current, [], tok, max_prompt_tokens=10000)
        messages, n, dropped = render('guide', current, previous[-2:], tok, max_prompt_tokens=count)
        self.assertEqual(messages, base)
        self.assertEqual((n, dropped), (count, 2))
        with self.assertRaises(ValueError):
            render('guide', current, [], tok, max_prompt_tokens=count-1)
        messages, _, _ = render('guide', current, previous, tok, max_prompt_tokens=10000)
        self.assertEqual(len(messages), 6)

    def test_target_only_loss_and_padding(self):
        tok = Tokenizer()
        current = deepcopy(self.payload)
        current.update(elapsed_ticks=900, observation_tick=900)
        messages, _, _ = render('g', current, [(self.payload, self.steps[0]['action'])], tok)
        encoding = training_encoding(tok, messages, self.steps[0]['action'])
        n = encoding['prompt_tokens']
        self.assertTrue(all(x == -100 for x in encoding['labels'][:n]))
        self.assertEqual(encoding['labels'][n:], encoding['input_ids'][n:])
        self.assertEqual(encoding['labels'][-1], tok.eos_token_id)
        padded = pad_encoding(encoding, len(encoding['input_ids'])+3, 0)
        self.assertEqual(padded['labels'][-3:], [-100]*3)
        self.assertEqual(padded['attention_mask'][-3:], [0]*3)

    def test_semantic_hash_ignores_handle_spelling(self):
        current = deepcopy(self.payload)
        current.update(elapsed_ticks=900, observation_tick=900)
        messages, _, _ = render('g', current, [(self.payload, self.steps[0]['action'])], Tokenizer(), 10000)
        changed = json.loads(canonical(messages).replace('e1', 'handle17').replace('e2', 'handle18').replace('e3', 'handle19'))
        self.assertNotEqual(digest(messages), digest(changed))
        self.assertEqual(digest(semantic_messages(messages)), digest(semantic_messages(changed)))

    def test_rejects_future_history_windows_and_nonfinite_numbers(self):
        with self.assertRaises(ValueError):
            render('guide', self.payload, [(self.payload, self.steps[0]['action'])], Tokenizer())
        for value in (float('nan'), float('inf'), True):
            p = deepcopy(self.payload)
            p['observation']['equipment'][0]['burner']['remaining_burning_fuel_joules'] = value
            with self.assertRaises(ValueError):
                validate_payload(p)
        p = deepcopy(self.payload)
        p['recent_production_windows'] = [{'index': 0, 'start_tick': 0, 'end_tick': 3600, 'actual_ticks': 3600,
                                          'iron_plates': 19, 'target': 16, 'below_target': False, 'consecutive_low_windows': 0}]
        with self.assertRaises(ValueError):
            validate_payload(p)

    def test_reserved_fixture_and_lineage_rejected(self):
        protocol = json.loads((self.root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json').read_text())
        row = {k: None for k in ROW_FIELDS}
        row.update(schema_version=1, protocol_id=protocol['protocol_id'], fixture_id='train_carry', partition='train',
                   episode_id=TRAIN_RUNS['train_carry']+'/scripted', label_source='executed_scripted')
        optimizer_rows([row], protocol)
        for patch in ({'fixture_id': 'test_drill_storage'}, {'partition': 'validation'}, {'episode_id': 'reserved/scripted'},
                      {'label_source': 'reviewed_replay'}):
            with self.assertRaises(ValueError):
                optimizer_rows([{**row, **patch}], protocol)


if __name__ == '__main__':
    unittest.main()
