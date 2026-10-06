"""Reachability control using the same adapter; never a model evaluation."""
import json
from pathlib import Path
from fle.env import FactorioInstance
from fle.commons.models.game_state import GameState
from game_bridge import GameBridge

root = Path('/home/osci2/factorio-pilot/artifacts')
instance = FactorioInstance(address='127.0.0.1', tcp_port=27000, fast=True, reset_speed=10, reset_paused=True)
instance.reset(game_state=GameState.parse_raw((root/'starting-state.json').read_text()))
instance.game_control.pause()
bridge = GameBridge(instance)
events = []

def call(tool, **args):
    action = {'tool': tool, 'args': args}
    try:
        result = bridge.action(action)
        if tool not in ('wait','done'):
            bridge.advance(1)
        events.append({'action': action, 'result': result})
        print(json.dumps(events[-1], default=str), flush=True)
        return result
    except Exception as error:
        events.append({'action': action, 'error': str(error)})
        (root/'reference-factory-actions.json').write_text(json.dumps(events, indent=2, default=str))
        raise

ore = call('nearest', type='IronOre')
call('move_to', position=ore)
chest = call('place_entity', entity='WoodenChest', position={'x':ore['x']-4,'y':ore['y']}, exact=False)
call('pickup_entity', entity=chest['handle'])
assert chest['handle'] not in bridge.handles, 'Picked-up handle was not invalidated'
for offset in (0, 5):
    position = {'x': ore['x'], 'y': ore['y'] + offset}
    drill = call('place_entity', entity='BurnerMiningDrill', position=position, direction='RIGHT', exact=False)
    furnace = call('place_entity_next_to', entity='StoneFurnace', reference_position=drill['position'], direction='RIGHT', spacing=0)
    call('insert_item', entity='Coal', target=drill['handle'], quantity=50)
    call('insert_item', entity='Coal', target=furnace['handle'], quantity=50)
    # Refresh and rotation roundtrip exercises handle conversion.
    call('rotate_entity', entity=drill['handle'], direction='RIGHT')
    call('get_entity', entity='BurnerMiningDrill', position=drill['position'])
before_pause = bridge.tick()
import time
time.sleep(0.2)
assert bridge.tick() == before_pause
call('wait', seconds=60)
windows = []
for _ in range(2):
    before = instance.namespace._get_production_stats()
    ticks = bridge.tick()
    call('wait', seconds=60)
    after = instance.namespace._get_production_stats()
    windows.append({'actual_ticks': bridge.tick()-ticks, 'iron_plates': after['output'].get('iron-plate',0)-before['output'].get('iron-plate',0)})
report = {'kind': 'scripted_reference_not_model', 'actions': events, 'measurement_windows': windows,
          'pickup_handle_invalidation_verified': True,
          'pause_verified': True, 'final_factory': bridge.observation(),
          'only_coal_inserted': all(e['action']['args'].get('entity') == 'Coal' for e in events if e['action']['tool']=='insert_item'),
          'target_met': all(w['actual_ticks']==3600 and w['iron_plates']>=16 for w in windows)}
(root/'reference-factory.json').write_text(json.dumps(report, indent=2, default=str)+'\n')
(root/'reference-factory-actions.json').write_text(json.dumps(events, indent=2, default=str)+'\n')
(root/'adapter-tool-contract.txt').write_text(bridge.prompt()+'\n')
print('REFERENCE_RESULT '+json.dumps(report, default=str), flush=True)
assert report['target_met'], 'Reference factory did not reach the target'
