"""Scripted connection/reset/timing checks, separate from model evaluations."""
from runtime_paths import runtime_home

import json
import time
from pathlib import Path
from fle.env import FactorioInstance
from fle.eval.tasks.task_factory import TaskFactory
from fle.commons.models.game_state import GameState

root = runtime_home() / 'artifacts'
root.mkdir(parents=True, exist_ok=True)
instance = FactorioInstance(address='127.0.0.1', tcp_port=27000,
                            fast=True, reset_speed=10, reset_paused=True)
task = TaskFactory.create_task('iron_plate_throughput')
task.setup(instance)
instance.game_control.pause()
connection = instance.rcon_client

def tick():
    return int(connection.send_command('/sc rcon.print(game.tick)').strip())

def advance(ticks):
    before = tick()
    connection.send_command(f'/sc game.speed=10; game.tick_paused=true; game.ticks_to_run={ticks}')
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        after = tick()
        if after - before == ticks:
            return after - before
        if after - before > ticks:
            raise RuntimeError('Simulation overshot the requested ticks.')
        time.sleep(0.05)
    raise TimeoutError('Controlled simulation did not advance in time.')

before = tick()
time.sleep(0.2)
assert tick() == before, 'Game advanced while paused.'
inventory = dict(instance.namespace.inspect_inventory())
score, _, observation = instance.eval_with_error('print(inspect_inventory())', timeout=10)
assert score != -1, observation
real_ticks = advance(60)
state = GameState.from_instance(instance)
(root / 'starting-state.json').write_text(state.to_raw())
instance.reset(game_state=state)
instance.game_control.pause()
assert dict(instance.namespace.inspect_inventory()) == inventory, 'Reset changed inventory.'
prompt = instance.get_system_prompt()
(root / 'fle-system-prompt.txt').write_text(prompt)
report = {
    'kind': 'scripted_development_smoke', 'task_key': task.task_key,
    'starting_inventory': inventory, 'valid_observation': observation,
    'pause_verified': True, 'requested_ticks': 60, 'actual_ticks': real_ticks,
    'reset_inventory_verified': True, 'system_prompt_characters': len(prompt),
    'factorio_version': connection.send_command('/sc rcon.print(helpers.table_to_json(script.active_mods))').strip(),
    'production_stats': instance.namespace._get_production_stats(),
}
(root / 'game-smoke.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
print(json.dumps(report, indent=2, default=str))
