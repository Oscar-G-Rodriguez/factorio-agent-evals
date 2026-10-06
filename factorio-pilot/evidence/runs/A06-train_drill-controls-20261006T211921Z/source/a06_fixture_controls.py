"""A06 fixture preparation and CPU controls with native-save restore barriers.

Run against one local server. At each printed RESTORE_REQUIRED barrier, load the
saved native map externally, then send RESTORED on stdin. No model is loaded.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + '\n', encoding='utf-8')


def verify_presets(fixture: dict, snapshot: dict) -> None:
    """Refuse mismatched inventories/energy, capacities or burning fuel."""
    entities = {e['name']: e for e in snapshot['entities']}
    if set(entities) != {'burner-mining-drill', 'stone-furnace', 'wooden-chest'} or len(snapshot['entities']) != 3:
        raise RuntimeError('Fixture must contain exactly one drill, furnace and chest')
    expected = fixture['presets']
    actual = {'drill_coal': entities['burner-mining-drill']['coal'],
              'drill_burning_joules': entities['burner-mining-drill']['burning_joules'],
              'furnace_coal': entities['stone-furnace']['coal'],
              'furnace_burning_joules': entities['stone-furnace']['burning_joules'],
              'output_plates': entities['stone-furnace']['plates'],
              'carried_plates': snapshot['actor_inventory'].get('iron-plate', 0),
              'chest_plates': entities['wooden-chest']['plates'],
              'reserve_coal': snapshot['actor_inventory'].get('coal', 0)}
    for key, target in expected.items():
        tolerance = 1 if key.endswith('_joules') else 0
        if not math.isfinite(actual[key]) or abs(actual[key] - target) > tolerance:
            raise RuntimeError(f'Preset mismatch: {key}: {actual[key]} != {target}')
    if not snapshot['paused'] or snapshot['ticks_to_run'] != 0:
        raise RuntimeError('Fixture is not fully paused')
    for name in ('burner-mining-drill', 'stone-furnace'):
        if entities[name]['burning_item'] != 'coal':
            raise RuntimeError('Burning item must be verified coal')


def scripted_action(observation: dict) -> dict:
    """The A05 reference policy; no hidden information or new tool actions."""
    equipment = observation['equipment']
    burners = [e for e in equipment if 'burner' in e and e['burner']['coal_in_fuel_inventory'] <= 1]
    if burners:
        entity = min(burners, key=lambda e: (e['burner']['coal_in_fuel_inventory'], e['name'] != 'burner-mining-drill'))
        return {'tool': 'fuel', 'args': {'building_handle': entity['handle'], 'coal_count': 3}}
    if observation['carrying']['carried_plates']:
        chest = next(e for e in equipment if e['name'] == 'wooden-chest')
        return {'tool': 'store_plates', 'args': {'chest_handle': chest['handle'], 'plate_count': 100}}
    furnace = next(e for e in equipment if e['name'] == 'stone-furnace')
    if furnace['output_storage']['iron_plates'] >= 60:
        return {'tool': 'collect_output', 'args': {'furnace_handle': furnace['handle'], 'plate_count': 100}}
    return {'tool': 'wait', 'args': {}}


def physical_snapshot(bridge) -> dict:
    """Private readback covers machine progress and full actor inventory."""
    return bridge._json(bridge._actor() + '''
local result={tick=game.tick,paused=game.tick_paused,ticks_to_run=game.ticks_to_run,speed=game.speed,
 actor_position=actor.position,actor_inventory=storage.utils.get_contents_compat(carried),entities={}};
for _,e in pairs(actor.surface.find_entities_filtered{name={'burner-mining-drill','stone-furnace','wooden-chest'},position=actor.position,radius=100}) do
 local row={name=e.name,position=e.position,direction=e.direction,status=e.status};
 if e.burner then
  local b=e.burner; local burning=b.currently_burning;
  row.coal=b.inventory.get_item_count('coal'); row.burning_joules=b.remaining_burning_fuel;
  local burning_name=burning and burning.name;
  if type(burning_name)=='userdata' or type(burning_name)=='table' then burning_name=burning_name.name end;
  row.burning_item=burning_name or false;
  row.burner_heat=b.heat;
 end;
 if e.name=='burner-mining-drill' then row.mining_progress=e.mining_progress; row.drop_position=e.drop_position; end;
 if e.name=='stone-furnace' then
  row.crafting_progress=e.crafting_progress; row.products_finished=e.products_finished;
  row.input_inventory=storage.utils.get_contents_compat(e.get_inventory(defines.inventory.crafter_input));
  row.plates=e.get_output_inventory().get_item_count('iron-plate');
  row.free_plates=e.get_output_inventory().get_insertable_count('iron-plate');
 end;
 if e.name=='wooden-chest' then
  row.plates=e.get_inventory(defines.inventory.chest).get_item_count('iron-plate');
  row.free_plates=e.get_inventory(defines.inventory.chest).get_insertable_count('iron-plate');
 end;
 table.insert(result.entities,row);
end;
table.sort(result.entities,function(a,b) return a.name<b.name end);
rcon.print(helpers.table_to_json(result));''')


def apply_presets(bridge, fixture: dict) -> dict:
    """Evaluator-only starting endowments; never exposed as a model tool."""
    values = fixture['presets']
    # Registry-owned integer bounds are checked before interpolating Lua.
    bounds = {'drill_coal': (0, 3), 'furnace_coal': (0, 3),
              'drill_burning_joules': (1, 4000000), 'furnace_burning_joules': (1, 4000000),
              'output_plates': (0, 100), 'carried_plates': (0, 100),
              'chest_plates': (0, 1600), 'reserve_coal': (100, 400)}
    if set(values) != set(bounds) or any(type(v) is not int or not bounds[k][0] <= v <= bounds[k][1] for k, v in values.items()):
        raise ValueError('Invalid fixture preset')
    bridge._json(bridge._actor() + f'''
if not game.tick_paused or game.ticks_to_run~=0 then error('Preset requires paused world') end;
local function set_count(inv,name,count)
 local previous=inv.get_item_count(name); if previous>0 then inv.remove{{name=name,count=previous}} end;
 if count>0 and inv.insert{{name=name,count=count}}~=count then error('Preset inventory capacity failed') end;
end;
local entities=actor.surface.find_entities_filtered{{name={{'burner-mining-drill','stone-furnace','wooden-chest'}},position=actor.position,radius=100}};
if #entities~=3 then error('Wrong fixture entity count') end;
for _,e in pairs(entities) do
 if e.name=='burner-mining-drill' then
  set_count(e.burner.inventory,'coal',{values['drill_coal']});
  e.burner.currently_burning={{name='coal',quality='normal'}};
  e.burner.remaining_burning_fuel={values['drill_burning_joules']};
 elseif e.name=='stone-furnace' then
  set_count(e.burner.inventory,'coal',{values['furnace_coal']});
  e.burner.currently_burning={{name='coal',quality='normal'}};
  e.burner.remaining_burning_fuel={values['furnace_burning_joules']};
  set_count(e.get_output_inventory(),'iron-plate',{values['output_plates']});
 elseif e.name=='wooden-chest' then
  set_count(e.get_inventory(defines.inventory.chest),'iron-plate',{values['chest_plates']});
 end;
end;
set_count(carried,'coal',{values['reserve_coal']});
set_count(carried,'iron-plate',{values['carried_plates']});
rcon.print(helpers.table_to_json({{presets_applied=true}}));''')
    result = physical_snapshot(bridge)
    print('PRESET_READBACK ' + json.dumps(result), flush=True)
    verify_presets(fixture, result)
    return result


def await_restore(instance, bridge, expected: dict, label: str, destination: Path) -> None:
    print('RESTORE_REQUIRED ' + label, flush=True)
    if sys.stdin.readline().strip() != 'RESTORED':
        raise RuntimeError('Native map restore was not acknowledged')
    instance.rcon_client.close()
    instance.rcon_client.connect()
    # A reconnect preserves actors. Reload Lua tool functions if loading the map
    # cleared them; never call initialise(), which destroys saved characters.
    instance.lua_script_manager.load_init_into_game('initialise')
    instance.lua_script_manager.setup_tools(instance)
    for name in ('lualib_util', 'utils', 'alerts', 'connection_points',
                 'recipe_fluid_connection_mappings', 'serialize', 'serialize_direction_fix'):
        instance.lua_script_manager.load_init_into_game(name)
    actual = physical_snapshot(bridge)
    write_json(destination, {'controller': label, 'expected': expected, 'actual': actual,
                             'exact_match': actual == expected})
    if actual != expected:
        raise RuntimeError('Native map restore changed the recorded physical snapshot')
    print('RESTORE_VERIFIED ' + label, flush=True)


def run_control(instance, bridge, controller: str, task: dict, destination: Path) -> dict:
    from maintenance_tools import ProductionMonitor
    destination.mkdir()
    origin = bridge.tick()
    start_stats = instance.namespace._get_production_stats()
    monitor = ProductionMonitor(origin, start_stats['output'].get('iron-plate', 0))
    initial = bridge.observation()
    write_json(destination / 'initial_observation.json', initial)
    started = time.monotonic()
    stop = 'survived_simulation_limit'
    steps = failures = 0
    ore_mined = ore_consumed = 0
    with (destination / 'steps.jsonl').open('w', encoding='utf-8', buffering=1) as stream:
        for step in range(task['max_decisions']):
            if time.monotonic() - started >= task['wall_time_limit_seconds']:
                stop = 'wall_time_limit_incomplete'
                break
            observation = bridge.observation()
            before = bridge.tick()
            action = scripted_action(observation) if controller == 'scripted' else {'tool': 'wait', 'args': {}}
            error = None
            try:
                result = bridge.action(action)
            except ValueError as exc:
                error = str(exc)
                result = None
                failures += 1
            if bridge.tick() != before or bridge.advance(15) != task['decision_interval_ticks']:
                raise RuntimeError('Control violated the fixed action cadence')
            after = bridge.observation()
            stats = instance.namespace._get_production_stats()
            window = monitor.sample(bridge.tick(), stats['output'].get('iron-plate', 0))
            ore_mined = stats['output'].get('iron-ore', 0) - start_stats['output'].get('iron-ore', 0)
            ore_consumed = stats['input'].get('iron-ore', 0) - start_stats['input'].get('iron-ore', 0)
            row = {'step': step, 'tick_before': before, 'tick_after': bridge.tick(),
                   'elapsed_ticks': bridge.tick() - origin, 'observation_before': observation,
                   'action': action, 'result': result, 'failed_action': error is not None,
                   'error': error, 'observation_after': after, 'window': window,
                   'new_ore_mined': ore_mined, 'new_ore_consumed': ore_consumed}
            stream.write(json.dumps(row, default=str, allow_nan=False) + '\n')
            steps += 1
            if window:
                print(controller.upper() + '_WINDOW ' + json.dumps(window), flush=True)
            if monitor.failed:
                stop = 'sustained_production_failure'
                break
    summary = {'controller': controller, 'stop_reason': stop, 'steps': steps,
               'simulated_seconds': (bridge.tick() - origin) / 60,
               'wall_seconds': time.monotonic() - started, 'failed_actions': failures,
               'measurement_windows': monitor.windows,
               'new_iron_plates': sum(w['iron_plates'] for w in monitor.windows),
               'new_ore_mined': ore_mined, 'new_ore_consumed': ore_consumed,
               'final_observation': bridge.observation(), 'final_physical_snapshot': physical_snapshot(bridge),
               'no_manual_ore_insertion': True, 'model_loaded': False, 'custom_cuda_used': False}
    write_json(destination / 'summary.json', summary)
    print(controller.upper() + '_SUMMARY ' + json.dumps({k: summary[k] for k in
          ('stop_reason', 'simulated_seconds', 'failed_actions', 'new_iron_plates')}), flush=True)
    return summary


def main() -> None:
    from cuda_review import assert_review_current
    from maintenance_tools import build_maintenance_fixture
    from runtime_paths import runtime_home
    from fle.env import FactorioInstance
    args = argparse.ArgumentParser()
    args.add_argument('--fixture', choices=['train_drill'], default='train_drill')
    args.add_argument('--resume-run', type=Path)
    options = args.parse_args()
    repo = Path(__file__).resolve().parents[2]
    protocol_path = repo / 'factorio-pilot/protocols/a06-qwen-sft-v1.json'
    protocol = json.loads(protocol_path.read_text())
    fixture = next(f for f in protocol['fixtures'] if f['id'] == options.fixture)
    review = assert_review_current()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run = runtime_home() / 'runs' / f'A06-{options.fixture}-controls-{stamp}'
    run.mkdir(parents=True)
    (run / 'source').mkdir()
    names = ['a06_fixture_controls.py', 'maintenance_tools.py', 'logistics_tools.py',
             'factory_agent_tools.py', 'game_bridge.py', 'runtime_paths.py', 'cuda_review.py']
    hashes = {}
    for name in names:
        data = Path(__file__).with_name(name).read_bytes()
        (run / 'source' / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    write_json(run / 'config.json', {'protocol_id': protocol['protocol_id'], 'fixture': fixture,
        'protocol_sha256': hashlib.sha256(protocol_path.read_bytes()).hexdigest(), 'task': protocol['task'],
        'source_hashes': hashes, 'native_source_hashes': review['source_hashes'],
        'scope': 'one fixture, scripted/idle environment controls; no model or training',
        'server_version_expected': '2.0.73', 'restore_mode': 'complete_native_map_then_reconnect_without_initialise'})
    instance = FactorioInstance(address='127.0.0.1', tcp_port=27000, fast=True, reset_speed=10, reset_paused=True)
    if options.resume_run:
        source_run = options.resume_run.resolve()
        if source_run.parent != (runtime_home() / 'runs').resolve() or not source_run.name.startswith('A06-train_drill-controls-'):
            raise ValueError('Resume must use an existing local train_drill control run')
        from maintenance_tools import MaintenanceBridge
        bridge = MaintenanceBridge(instance, game_speed=10, carry_limit=100)
        for name in ('fixture_snapshot.json', 'setup.json', 'storage_function_inventory.json',
                     'native_save.json', 'native-server.override.yaml', 'helpers_prepare.json'):
            (run / name).write_bytes((source_run / name).read_bytes())
        snapshot = json.loads((run / 'fixture_snapshot.json').read_text())
        verify_presets(fixture, snapshot)
        save_name = json.loads((run / 'native_save.json').read_text())['native_save_filename'][:-4]
        write_json(run / 'fixture_provenance.json', {'prepared_in_run': source_run.name,
            'native_snapshot_reused': True, 'preparation_not_repeated': True})
        print('RUN ' + str(run), flush=True)
    else:
        bridge, setup = build_maintenance_fixture(instance, (repo / protocol['fixture_preparation']['starting_state_path']).read_text())
        write_json(run / 'setup.json', setup)
        snapshot = apply_presets(bridge, fixture)
        write_json(run / 'fixture_snapshot.json', snapshot)
        save_name = 'a06_' + options.fixture + '_' + stamp
        if not re.fullmatch('[A-Za-z0-9_]+', save_name):
            raise ValueError('Unsafe native save name')
        inventory = instance.rcon_client.send_command('''/sc local seen={}; local paths={}; local tables={};
    local function inspect(t,path)
     if seen[t] then return end; seen[t]=true;
     local scalar_count=0; local function_count=0; local table_count=0;
     for k,v in pairs(t) do
      local next_path=path..'.'..tostring(k);
      if type(v)=='function' then table.insert(paths,next_path); function_count=function_count+1;
      elseif type(v)=='table' then table_count=table_count+1; inspect(v,next_path);
      else scalar_count=scalar_count+1; end;
     end;
     table.insert(tables,{path=path,scalar_count=scalar_count,function_count=function_count,table_count=table_count});
    end;
    inspect(storage,'storage'); table.sort(paths); rcon.print(helpers.table_to_json({paths=paths,tables=tables}));''')
        write_json(run / 'storage_function_inventory.json', json.loads(inventory))
        print('RUN ' + str(run), flush=True)
        print('SAVE_HELPER_INSPECTION_REQUIRED', flush=True)
        if sys.stdin.readline().strip() != 'SAVE':
            raise RuntimeError('Save preparation not acknowledged')
        instance.rcon_client.send_command('/sc game.server_save(' + json.dumps(save_name) + ')')
        print('RUN ' + str(run), flush=True)
        print('NATIVE_SAVE ' + save_name + '.zip', flush=True)
    await_restore(instance, bridge, snapshot, 'scripted', run / 'scripted_restore.json')
    scripted = run_control(instance, bridge, 'scripted', protocol['task'], run / 'scripted')
    await_restore(instance, bridge, snapshot, 'idle', run / 'idle_restore.json')
    idle = run_control(instance, bridge, 'idle', protocol['task'], run / 'idle')
    passed = scripted['stop_reason'] == 'survived_simulation_limit' and scripted['failed_actions'] == 0 and all(
        w['iron_plates'] >= 16 for w in scripted['measurement_windows']) and len(scripted['measurement_windows']) == 20
    write_json(run / 'control_manifest.json', {'fixture_id': options.fixture, 'partition': fixture['partition'],
        'scripted_reachability_passed': passed, 'idle_endpoint': idle['stop_reason'],
        'idle_simulated_seconds': idle['simulated_seconds'], 'native_save_filename': save_name + '.zip',
        'restores_exactly_matched': True, 'dataset_ready': False, 'other_fixtures_validated': False})
    if not passed or idle['stop_reason'] != 'sustained_production_failure':
        raise RuntimeError('Fixture control checkpoint did not pass')
    print('FIXTURE_CONTROL_PASS', flush=True)


if __name__ == '__main__':
    main()
