import copy
import unittest
from a06_fixture_controls import scripted_action, verify_presets, control_action


class FixtureControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {'presets': {'drill_coal': 0, 'drill_burning_joules': 1000000,
            'furnace_coal': 3, 'furnace_burning_joules': 3000000,
            'output_plates': 20, 'carried_plates': 0, 'chest_plates': 0, 'reserve_coal': 400}}
        self.snapshot = {'paused': True, 'ticks_to_run': 0, 'actor_inventory': {'coal': 400},
            'entities': [{'name': 'burner-mining-drill', 'coal': 0,
                          'burning_joules': 1000000, 'burning_item': 'coal'},
                         {'name': 'stone-furnace', 'coal': 3, 'burning_joules': 3000000,
                          'burning_item': 'coal', 'plates': 20},
                         {'name': 'wooden-chest', 'plates': 0}]}

    def test_readback_requires_counts_burning_item_and_paused_world(self):
        verify_presets(self.fixture, self.snapshot)
        for path, value in [('coal', 1), ('burning_item', False), ('burning_joules', float('nan'))]:
            altered = copy.deepcopy(self.snapshot)
            altered['entities'][0][path] = value
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                verify_presets(self.fixture, altered)
        altered = copy.deepcopy(self.snapshot)
        altered['ticks_to_run'] = 1
        with self.assertRaises(RuntimeError):
            verify_presets(self.fixture, altered)

    def test_one_joule_tolerance_does_not_hide_inventory_mismatch(self):
        self.snapshot['entities'][0]['burning_joules'] += 1
        verify_presets(self.fixture, self.snapshot)
        self.snapshot['entities'][0]['burning_joules'] += 1
        with self.assertRaises(RuntimeError):
            verify_presets(self.fixture, self.snapshot)

    def test_duplicate_entities_are_rejected(self):
        self.snapshot['entities'].append(copy.deepcopy(self.snapshot['entities'][0]))
        with self.assertRaises(RuntimeError):
            verify_presets(self.fixture, self.snapshot)

    def test_reference_prioritizes_low_drill_then_storage(self):
        observation = {'equipment': [
            {'name': 'burner-mining-drill', 'handle': 'drill', 'burner': {'coal_in_fuel_inventory': 0}},
            {'name': 'stone-furnace', 'handle': 'furnace', 'burner': {'coal_in_fuel_inventory': 3},
             'output_storage': {'iron_plates': 90}},
            {'name': 'wooden-chest', 'handle': 'chest'}], 'carrying': {'carried_plates': 100}}
        self.assertEqual(scripted_action(observation),
                         {'tool': 'fuel', 'args': {'building_handle': 'drill', 'coal_count': 3}})
        observation['equipment'][0]['burner']['coal_in_fuel_inventory'] = 3
        self.assertEqual(scripted_action(observation)['tool'], 'store_plates')
        observation['carrying']['carried_plates'] = 0
        self.assertEqual(scripted_action(observation)['tool'], 'collect_output')


    def test_congestion_control_preserves_default_and_obeys_carry_capacity(self):
        observation = {'equipment': [
            {'name': 'burner-mining-drill', 'handle': 'drill', 'burner': {'coal_in_fuel_inventory': 2}},
            {'name': 'stone-furnace', 'handle': 'furnace', 'burner': {'coal_in_fuel_inventory': 0},
             'output_storage': {'iron_plates': 98}},
            {'name': 'wooden-chest', 'handle': 'chest'}], 'carrying': {'carried_plates': 40}}
        self.assertEqual(control_action(observation)['tool'], 'fuel')
        self.assertEqual(control_action(observation, 'congestion-control')['tool'], 'collect_output')
        observation['carrying']['carried_plates'] = 100
        self.assertEqual(control_action(observation, 'congestion-control')['tool'], 'store_plates')
        observation['equipment'][1]['output_storage']['iron_plates'] = 20
        self.assertEqual(control_action(observation, 'congestion-control')['tool'], 'fuel')


if __name__ == '__main__':
    unittest.main()
