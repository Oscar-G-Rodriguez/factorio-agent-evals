"""A small JSON-to-FLE adapter. Model text is never evaluated as Python."""
import inspect
import math
import time
from fle.env import Direction
from fle.env.entities import Position, Entity
from fle.env.game_types import Prototype, Resource

TOOLS = ('inspect_inventory', 'nearest', 'move_to', 'place_entity',
         'place_entity_next_to', 'get_entity', 'get_entities', 'insert_item',
         'rotate_entity', 'can_place_entity', 'pickup_entity')
PROTOTYPES = ('BurnerMiningDrill', 'StoneFurnace', 'BurnerInserter',
              'WoodenChest', 'TransportBelt', 'Coal', 'IronOre', 'IronPlate')

# These describe the JSON adapter, rather than the broader Python FLE API.
# allowed arguments, required arguments, explanation
TOOL_SPECS = {
    'inspect_inventory': ((), (), 'Read the player inventory. Takes no arguments.'),
    'nearest': (('type',), ('type',), 'Find the nearest resource: IronOre, Coal, or Stone. Returns a position.'),
    'move_to': (('position',), ('position',), 'Move the player to a position. No laying or leading arguments.'),
    'place_entity': (('entity','direction','position','exact'), ('entity','position'), 'Place a supplied building prototype. direction defaults UP; exact defaults true. Mining drills must cover ore; their direction determines the output side.'),
    'place_entity_next_to': (('entity','reference_position','direction','spacing'), ('entity','reference_position'), 'Place a building adjacent to the building at reference_position. direction is the placement side (default RIGHT); spacing is an integer gap, default 0. A furnace adjacent to a drill output can receive mined ore directly.'),
    'get_entity': (('entity','position'), ('entity','position'), 'Read a building by prototype name and position. Returns a fresh entity handle and status.'),
    'get_entities': (('entities','position','radius'), (), 'Read nearby buildings. entities is a prototype name or list (empty means all); optional position defaults to the player; radius defaults 100, maximum 500.'),
    'insert_item': (('entity','target','quantity'), ('entity','target'), 'Insert Coal from player inventory into a building handle such as e1. quantity is an integer 1..500 (default 5). Fuel drills, furnaces, and burner inserters. Manual ore insertion is forbidden for this task.'),
    'rotate_entity': (('entity','direction'), ('entity','direction'), 'Rotate an existing building handle such as e1 to UP, RIGHT, DOWN, or LEFT.'),
    'can_place_entity': (('entity','position','direction'), ('entity','position'), 'Check if a building can fit at a position. Optional direction defaults UP. Placement availability alone does not prove the presence of ore.'),
    'pickup_entity': (('entity',), ('entity',), 'Remove an existing building using its handle such as e1. This invalidates that handle. Cannot pick up loose ore or specify a prototype/position.'),
}

class GameBridge:
    def __init__(self, instance):
        self.instance = instance
        self.handles = {}
        self.identities = {}
        self.next_handle = 1

    def tick(self):
        return int(self.instance.rcon_client.send_command('/sc rcon.print(game.tick)').strip())

    def advance(self, seconds):
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 60:
            raise ValueError('wait seconds must be an integer from 1 to 60')
        ticks = seconds * 60
        before = self.tick()
        self.instance.rcon_client.send_command(
            f'/sc game.speed=10; game.tick_paused=true; game.ticks_to_run={ticks}')
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            actual = self.tick() - before
            if actual == ticks:
                return actual
            if actual > ticks:
                raise RuntimeError('Simulation overshot controlled tick budget.')
            time.sleep(0.05)
        raise TimeoutError('Controlled simulation timed out.')

    def describe(self, value):
        if isinstance(value, Entity):
            key = (value.name, value.position.x, value.position.y)
            if key not in self.identities:
                self.identities[key] = f'e{self.next_handle}'
                self.next_handle += 1
            handle = self.identities[key]
            self.handles[handle] = value
            result = {'handle': handle, 'name': value.name,
                      'position': {'x': value.position.x, 'y': value.position.y}}
            for name in ('direction', 'status', 'inventory', 'fuel', 'warnings',
                         'drop_position', 'pickup_position', 'output_position',
                         'fuel_inventory', 'furnace_source', 'furnace_result'):
                if hasattr(value, name):
                    field = getattr(value, name)
                    result[name] = self.describe(field) if isinstance(field, (Position, dict)) else str(field)[:1500]
            return result
        if isinstance(value, Position):
            return {'x': value.x, 'y': value.y}
        if isinstance(value, (list, tuple)):
            return [self.describe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self.describe(item) for key, item in value.items()}
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        return str(value)

    def convert(self, key, value, tool_name=None):
        if key in ('position', 'reference_position'):
            if not isinstance(value, dict) or set(value) != {'x', 'y'}:
                raise ValueError(f'{key} must contain numeric x and y')
            if any(isinstance(n, bool) or not isinstance(n, (int, float)) or
                   not math.isfinite(n) or abs(n) > 500 for n in value.values()):
                raise ValueError('Coordinates must be finite and within 500 tiles')
            return Position(**value)
        if key in ('entity', 'entities'):
            if tool_name in ('rotate_entity', 'pickup_entity') and key == 'entity':
                if value not in self.handles:
                    raise ValueError(f'Unknown entity handle: {value}')
                return self.handles[value]
            def prototype(name):
                if name not in PROTOTYPES:
                    raise ValueError(f'Unsupported prototype: {name}')
                return getattr(Prototype, name)
            return {prototype(name) for name in value} if key == 'entities' and isinstance(value, list) else prototype(value)
        if key == 'type':
            if value not in ('IronOre', 'Coal', 'Stone'):
                raise ValueError('nearest type must be IronOre, Coal, or Stone')
            return getattr(Resource, value)
        if key == 'direction':
            if value not in ('UP', 'RIGHT', 'DOWN', 'LEFT'):
                raise ValueError('direction must be UP, RIGHT, DOWN, or LEFT')
            return getattr(Direction, value)
        if key == 'target':
            if value not in self.handles:
                raise ValueError(f'Unknown entity handle: {value}')
            return self.handles[value]
        if key in ('quantity', 'spacing', 'radius'):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 500:
                raise ValueError(f'{key} must be between 0 and 500')
            if key in ('quantity', 'spacing') and not isinstance(value, int):
                raise ValueError(f'{key} must be an integer')
            if key == 'quantity' and value == 0:
                raise ValueError('quantity must be positive')
            return value
        if key == 'exact' and isinstance(value, bool):
            return value
        raise ValueError(f'Unsupported argument: {key}')

    def action(self, action):
        if not isinstance(action, dict) or set(action) != {'tool', 'args'}:
            raise ValueError('Response must have exactly tool and args')
        name, arguments = action['tool'], action['args']
        if not isinstance(arguments, dict):
            raise ValueError('args must be an object')
        if name == 'done':
            if arguments:
                raise ValueError('done takes no arguments')
            return {'done': True}
        if name == 'wait':
            if set(arguments) != {'seconds'}:
                raise ValueError('wait takes seconds only')
            return {'advanced_ticks': self.advance(arguments['seconds'])}
        if name not in TOOLS:
            raise ValueError(f'Unknown tool: {name}')
        allowed, required, _ = TOOL_SPECS[name]
        if set(arguments) - set(allowed) or set(required) - set(arguments):
            raise ValueError(f'{name} accepts {allowed}; requires {required}')
        if name == 'insert_item' and arguments['entity'] != 'Coal':
            raise ValueError('This task permits supplied Coal insertion only; no manual ore insertion')
        tool = getattr(self.instance.namespace, name)
        converted = {key: self.convert(key, value, name) for key, value in arguments.items()}
        if name == 'get_entities':
            converted.setdefault('radius', 100)
        inspect.signature(tool).bind(**converted)
        # Movement requests need the game's asynchronous pathfinder to tick.
        # This action's physical time is measured, rather than assumed fixed.
        if name == 'move_to':
            self.instance.game_control.set_speed_and_unpause(10)
            try:
                return self.describe(tool(**converted))
            finally:
                self.instance.game_control.pause()
        result = self.describe(tool(**converted))
        if name == 'pickup_entity':
            handle = arguments['entity']
            old = self.handles.pop(handle)
            self.identities.pop((old.name, old.position.x, old.position.y), None)
        return result

    def observation(self):
        return {'inventory': self.describe(dict(self.instance.namespace.inspect_inventory())),
                'entities': self.describe(self.instance.namespace.get_entities(radius=100)),
                'production': self.instance.namespace._get_production_stats(),
                'game_tick': self.tick()}

    def prompt(self):
        return '\n\n'.join(f'{name}: allowed args={list(allowed)}; required={list(required)}. {description}'
                          for name, (allowed, required, description) in TOOL_SPECS.items())
