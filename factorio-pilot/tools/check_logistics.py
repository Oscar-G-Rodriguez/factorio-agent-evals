"""Scripted storage regression control; never a model evaluation."""
from runtime_paths import runtime_home

import hashlib
import json
import time
from pathlib import Path
from cuda_review import assert_review_current
assert_review_current()
from fle.env import FactorioInstance
from fle.commons.models.game_state import GameState
from logistics_tools import LogisticsBridge

root=runtime_home()
artifact=root/'artifacts/logistics-control.json'
instance=FactorioInstance(address='127.0.0.1',tcp_port=27000,fast=True,reset_speed=10,reset_paused=True)
instance.reset(game_state=GameState.parse_raw((root/'artifacts/starting-state.json').read_text()))
instance.game_control.pause()
bridge=LogisticsBridge(instance,visual=True,game_speed=10,carry_limit=100)
events=[];checks={};started=time.monotonic()

def call(tool,**args):
    action={'tool':tool,'args':args}
    result=bridge.action(action)
    events.append({'action':action,'result':result,'tick':bridge.tick()})
    print(json.dumps(events[-1],default=str),flush=True)
    return result

def storage(handle):
    target=bridge.handles[handle]
    return next(s for s in bridge.storage_status()['stores'] if s['name']==target.name and s['position']=={'x':target.position.x,'y':target.position.y})

def expect_no_transfer(tool,**args):
    before=bridge.storage_status()
    try: call(tool,**args)
    except ValueError as exc:
        events.append({'action':{'tool':tool,'args':args},'expected_error':str(exc)})
        assert bridge.storage_status()==before,'Rejected transfer changed inventory'
        return True
    raise AssertionError('Expected full/empty transfer to fail')

try:
    ore=call('find_iron');call('move',position=ore)
    drill=call('place_drill',position=ore,direction='RIGHT')
    furnace=call('place_furnace_at_output',drill_handle=drill['handle'])
    for building in (drill,furnace): call('fuel',building_handle=building['handle'],coal_count=50)
    call('wait',seconds=60)
    available=storage(furnace['handle'])['iron_plates']
    receipt=call('collect_output',furnace_handle=furnace['handle'],plate_count=100)
    assert receipt['transferred']==available and receipt['transferred']<100 and receipt['conserved']
    checks['partial_collection_never_creates_extra_plates']=True
    chest=call('place_storage',position={'x':ore['x']-3,'y':ore['y']-3})
    receipt=call('store_plates',chest_handle=chest['handle'],plate_count=100)
    assert receipt['transferred']==available and receipt['conserved']
    checks['partial_storage_conserves_plates']=True
    for _ in range(8): call('wait',seconds=60)
    full=storage(furnace['handle'])
    assert full['iron_plates']==100 and full['free_plate_capacity']==0
    blocked=call('wait',seconds=60)
    assert blocked['iron_plates']==0
    checks['uncollected_output_causes_real_production_stall']=True
    call('collect_output',furnace_handle=furnace['handle'],plate_count=100)
    resumed=call('wait',seconds=60)
    assert resumed['iron_plates']>=16
    checks['collection_restores_production']=True
    checks['carrying_limit_rejects_without_loss']=expect_no_transfer('collect_output',furnace_handle=furnace['handle'],plate_count=100)
    call('store_plates',chest_handle=chest['handle'],plate_count=100)
    call('collect_output',furnace_handle=furnace['handle'],plate_count=7)
    current=bridge.storage_status()
    produced=instance.namespace._get_production_stats()['output'].get('iron-plate',0)
    total=current['carried_plates']+sum(s['iron_plates'] for s in current['stores'])
    assert total==produced
    checks['produced_equals_carried_plus_furnace_plus_chest']=True
    conservation={'produced':produced,'accounted_for':total,'storage':current}
    # A separate artificial full-storage fixture; injected plates are excluded
    # from the production/conservation result above and from all model results.
    position=chest['position']
    fixture=bridge._json(bridge._actor()+f'''local e=actor.surface.find_entity('wooden-chest',{{x={position['x']},y={position['y']}}});
local inv=e.get_inventory(defines.inventory.chest); local inserted=inv.insert{{name='iron-plate',count=1600}};
rcon.print(helpers.table_to_json({{injected_plates=inserted,remaining_space=inv.get_insertable_count('iron-plate')}}));''')
    assert fixture['remaining_space']==0
    checks['full_chest_rejects_without_loss']=expect_no_transfer('store_plates',chest_handle=chest['handle'],plate_count=7)
    assert storage(chest['handle'])['slots']==16
    checks['actual_chest_capacity_observed']=True
    report={'kind':'scripted_logistics_validation_not_model','passed':all(checks.values()),'checks':checks,
            'production_conservation_before_injected_fixture':conservation,
            'artificial_full_chest_fixture_excluded_from_production_and_model_results':fixture,
            'benchmark_carried_plate_limit':100,'wall_seconds':time.monotonic()-started,'events':events,
            'source_hashes':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('logistics_tools.py','check_logistics.py','factory_agent_tools.py','game_bridge.py')}}
    artifact.write_text(json.dumps(report,indent=2,default=str)+'\n')
    print('LOGISTICS_PASS '+json.dumps(checks),flush=True)
except Exception as exc:
    artifact.write_text(json.dumps({'kind':'scripted_logistics_validation_not_model','passed':False,'error':str(exc),'checks':checks,'events':events},indent=2,default=str)+'\n')
    raise
