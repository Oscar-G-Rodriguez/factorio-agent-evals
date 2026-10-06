import unittest
from types import SimpleNamespace
from unittest.mock import patch
from factory_agent_tools import FactoryBridge
from logistics_tools import LogisticsBridge

class LogisticsToolsTests(unittest.TestCase):
    def setUp(self):
        self.bridge=LogisticsBridge(SimpleNamespace(namespace=SimpleNamespace(agent_index=0)),target_plate_rate=32)
        for handle,name in [('e1','stone-furnace'),('e2','wooden-chest')]:
            self.bridge.handles[handle]=SimpleNamespace(name=name,position=SimpleNamespace(x=17,y=70))

    def test_storage_does_not_allow_plates_into_furnaces(self):
        with self.assertRaises(ValueError):
            self.bridge.action({'tool':'store_plates','args':{'chest_handle':'e1','plate_count':10}})
        with self.assertRaises(ValueError):
            self.bridge.action({'tool':'collect_output','args':{'furnace_handle':'e2','plate_count':10}})

    def test_invalid_quantities_and_extra_arguments_are_rejected(self):
        for quantity in (0,101,True,1.5):
            with self.subTest(quantity=quantity),self.assertRaises(ValueError):
                self.bridge.action({'tool':'collect_output','args':{'furnace_handle':'e1','plate_count':quantity}})
        with self.assertRaises(ValueError):
            self.bridge.action({'tool':'collect_output','args':{'furnace_handle':'e1','plate_count':10,'item':'iron-ore'}})

    def test_finish_uses_expansion_target(self):
        self.bridge.last_test={'seconds':60,'iron_plates':19}
        with self.assertRaises(ValueError): self.bridge.action({'tool':'finish','args':{}})
        self.bridge.last_test={'seconds':60,'iron_plates':38}
        self.assertEqual(self.bridge.action({'tool':'finish','args':{}}),{'done':True})

    def test_partial_transfer_receipt_is_preserved(self):
        receipt={'requested':100,'transferred':17,'conserved':True}
        with patch.object(self.bridge,'_transfer',return_value=receipt):
            actual=self.bridge.action({'tool':'collect_output','args':{'furnace_handle':'e1','plate_count':100}})
        self.assertEqual(actual['transferred'],17)

if __name__=='__main__': unittest.main()
