import unittest
import json
from context_memory import ContextMemory

class CharacterTokenizer:
    def encode(self, text, **kwargs):
        return list(text)

class MemoryTests(unittest.TestCase):
    def test_budget_and_valid_json(self):
        memory = ContextMemory()
        memory.update({'game_tick': 60, 'entities': [{'handle': f'e{i}', 'name':'stone-furnace', 'fuel':'coal=50'} for i in range(20)]})
        text, count = memory.render(CharacterTokenizer())
        self.assertLessEqual(count, 512)
        self.assertTrue(json.loads(text)['facts_are_last_observed_not_guaranteed_current'])

    def test_invalidation_and_four_failures(self):
        memory = ContextMemory()
        memory.update({'game_tick': 1, 'entities': [{'handle':'e1','name':'stone-furnace'}]})
        for tick in range(6):
            memory.update({'game_tick': tick, 'entities': []}, {'tool':'bad'}, 'failed', valid_handles={})
        self.assertEqual(memory.entities, {})
        self.assertEqual(len(memory.failures), 4)
        self.assertEqual(memory.failures[0]['observed_tick'], 2)

if __name__ == '__main__':
    unittest.main()
