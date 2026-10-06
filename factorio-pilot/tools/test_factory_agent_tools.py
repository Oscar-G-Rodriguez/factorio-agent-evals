import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fle.env import Direction
from game_bridge import GameBridge
from factory_agent_tools import FactoryBridge

class FactoryToolsTests(unittest.TestCase):
    def setUp(self):
        self.bridge = FactoryBridge(SimpleNamespace())
        self.bridge.handles['e1'] = SimpleNamespace(name='burner-mining-drill', direction=Direction.RIGHT,
                                                   position=SimpleNamespace(x=16,y=71))

    def test_fuel_translates_item_and_handle(self):
        with patch.object(GameBridge,'action',return_value={}) as call:
            self.bridge.action({'tool':'fuel','args':{'building_handle':'e1','coal_count':50}})
            self.assertEqual(call.call_args.args[0],{'tool':'insert_item','args':{'entity':'Coal','target':'e1','quantity':50}})

    def test_furnace_uses_actual_drill_geometry(self):
        with patch.object(GameBridge,'action',return_value={}) as call:
            self.bridge.action({'tool':'place_furnace_at_output','args':{'drill_handle':'e1'}})
            self.assertEqual(call.call_args.args[0]['args'],{'entity':'StoneFurnace','reference_position':{'x':16,'y':71},'direction':'RIGHT','spacing':0})

    def test_premature_finish_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.action({'tool':'finish','args':{}})
        self.bridge.last_test={'seconds':60,'iron_plates':16}
        self.assertEqual(self.bridge.action({'tool':'finish','args':{}}),{'done':True})

    def test_wrong_handle_and_counts_rejected(self):
        for handle,count in [('Coal',50),('e1',True),('e1',51),('e1',0)]:
            with self.assertRaises(ValueError):
                self.bridge.action({'tool':'fuel','args':{'building_handle':handle,'coal_count':count}})

if __name__=='__main__':
    unittest.main()
