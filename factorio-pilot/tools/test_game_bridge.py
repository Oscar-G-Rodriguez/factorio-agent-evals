"""Validate the narrow action boundary without a running game."""
import unittest
from game_bridge import GameBridge

class Dummy:
    pass

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.bridge = GameBridge(Dummy())

    def test_python_and_unknown_tools_are_rejected(self):
        for action in ('import os', {'tool': '__import__', 'args': {'name': 'os'}},
                       {'tool': 'eval', 'args': {'code': '1+1'}}):
            with self.assertRaises(ValueError):
                self.bridge.action(action)

    def test_nonfinite_and_unbounded_coordinates_are_rejected(self):
        for x in (float('nan'), float('inf'), 501, '1', True):
            with self.assertRaises(ValueError):
                self.bridge.convert('position', {'x': x, 'y': 0})

    def test_valid_position_and_no_argument_done(self):
        self.assertEqual(self.bridge.convert('position', {'x': 2, 'y': 3}).x, 2)
        self.assertEqual(self.bridge.action({'tool': 'done', 'args': {}}), {'done': True})
        with self.assertRaises(ValueError):
            self.bridge.action({'tool': 'done', 'args': {'extra': 1}})

    def test_unknown_handles_and_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.convert('target', 'e999')
        with self.assertRaises(ValueError):
            self.bridge.convert('game', 'anything')
        with self.assertRaises(ValueError):
            self.bridge.convert('entity', 'ElectricMiningDrill')

    def test_contract_rejects_raw_fle_arguments_and_manual_ore(self):
        for action in ({'tool':'inspect_inventory','args':{'all_players':True}},
                       {'tool':'move_to','args':{'position':{'x':0,'y':0},'laying':'TransportBelt'}},
                       {'tool':'insert_item','args':{'entity':'IronOre','target':'e1'}}):
            with self.assertRaises(ValueError):
                self.bridge.action(action)

    def test_integer_and_positive_quantities(self):
        for value in (0, 1.5, True):
            with self.assertRaises(ValueError):
                self.bridge.convert('quantity', value)

if __name__ == '__main__':
    unittest.main()
