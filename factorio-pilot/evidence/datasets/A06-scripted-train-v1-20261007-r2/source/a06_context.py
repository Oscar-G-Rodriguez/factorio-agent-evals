"""A06 common CPU renderer. No game, model, or GPU is loaded here."""
import hashlib
import json
import math
from copy import deepcopy


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError('Unknown or missing fields: expected ' + str(required))


def number(value, integer=False, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError('Invalid finite number')
    if integer and type(value) is not int:
        raise ValueError('Expected integer')
    return value


def project(visible):
    """Whitelist ObservationPolicy.visible; raw allowlisted leftovers never enter prompts."""
    keys(visible, ('observation_policy', 'observation', 'observation_tick', 'elapsed_ticks',
                   'observation_age_ticks', 'result', 'recent_production_windows'))
    if visible['observation_policy'] != 'automatic':
        raise ValueError('A06 requires automatic observations')
    tick = number(visible['elapsed_ticks'], True)
    observed = number(visible['observation_tick'], True)
    age = number(visible['observation_age_ticks'], True)
    if observed != tick or age != 0:
        raise ValueError('Automatic snapshot must be current and relative to the episode origin')
    raw = visible['observation']
    keys(raw, ('inventory', 'carrying', 'equipment'), ('production', 'last_production_test', 'goal_plates_per_minute'))
    keys(raw['inventory'], (), ('coal', 'iron-plate', 'burner-mining-drill', 'stone-furnace', 'wooden-chest'))
    coal = number(raw['inventory'].get('coal', 0), True)
    plates = number(raw['inventory'].get('iron-plate', 0), True)
    carry = raw['carrying']
    keys(carry, ('carried_plates', 'available_carry_space', 'benchmark_carried_plate_limit'),
         ('agent_index', 'carried_chests', 'inventory_slots', 'physical_plate_space'))
    if carry['carried_plates'] != plates or carry['benchmark_carried_plate_limit'] != 100 or carry['available_carry_space'] != 100-plates:
        raise ValueError('Carrying observation disagrees with fixed capacity')
    number(carry['available_carry_space'], True)
    equipment = []
    handles = set()
    if not isinstance(raw['equipment'], list):
        raise ValueError('Equipment must be a list')
    for entity in raw['equipment']:
        keys(entity, ('handle', 'name', 'position', 'status'),
             ('direction', 'fuel', 'drop_position', 'burner', 'output_storage', 'furnace_source', 'furnace_result'))
        name = entity['name']
        if name not in ('burner-mining-drill', 'stone-furnace', 'wooden-chest'):
            raise ValueError('Unknown equipment')
        handle = entity['handle']
        if not isinstance(handle, str) or not handle or handle in handles or not isinstance(entity['status'], str):
            raise ValueError('Invalid handle or status')
        handles.add(handle)
        keys(entity['position'], ('x', 'y'))
        for coordinate in entity['position'].values():
            number(coordinate, minimum=-float('inf'))
        out = {k: deepcopy(entity[k]) for k in ('handle', 'name', 'position', 'status')}
        if name != 'wooden-chest':
            burner = entity['burner']
            keys(burner, ('coal_in_fuel_inventory', 'remaining_burning_fuel_joules'), ('currently_burning',))
            out['burner'] = {k: number(burner[k], integer=k == 'coal_in_fuel_inventory')
                             for k in ('coal_in_fuel_inventory', 'remaining_burning_fuel_joules')}
        if name != 'burner-mining-drill':
            storage = entity['output_storage']
            keys(storage, ('iron_plates', 'free_plate_capacity'), ('slots',))
            capacity = 100 if name == 'stone-furnace' else 1600
            count = number(storage['iron_plates'], True)
            free = number(storage['free_plate_capacity'], True)
            if count + free != capacity:
                raise ValueError('Storage capacity mismatch')
            out['output_storage'] = {'iron_plates': count, 'free_plate_capacity': free}
        equipment.append(out)
    if sorted(e['name'] for e in equipment) != ['burner-mining-drill', 'stone-furnace', 'wooden-chest']:
        raise ValueError('Expected the fixed three entities')
    equipment.sort(key=lambda e: (e['name'], e['position']['x'], e['position']['y']))
    windows = visible['recent_production_windows']
    if not isinstance(windows, list) or len(windows) > 2:
        raise ValueError('At most two observed windows')
    projected_windows = []
    for w in windows:
        keys(w, ('index', 'start_tick', 'end_tick', 'actual_ticks', 'iron_plates', 'target', 'below_target', 'consecutive_low_windows'))
        for k in ('index', 'start_tick', 'end_tick', 'actual_ticks', 'iron_plates', 'target', 'consecutive_low_windows'):
            number(w[k], True)
        if w['end_tick'] > observed or w['end_tick'] - w['start_tick'] != 3600 or w['actual_ticks'] != 3600 or w['target'] != 16 or type(w['below_target']) is not bool or w['below_target'] != (w['iron_plates'] < 16):
            raise ValueError('Invalid or future production window')
        projected_windows.append(deepcopy(w))
    feedback = visible['result']
    if feedback is not None:
        keys(feedback, ('ok', 'tool'), ('error', 'transferred_iron_plates'))
        if type(feedback['ok']) is not bool or feedback['tool'] not in ('fuel', 'collect_output', 'store_plates', 'check', 'wait', 'invalid'):
            raise ValueError('Invalid action feedback')
        if 'error' in feedback and (feedback['ok'] or feedback['error'] != 'Action failed; inspect if current factory state is needed. Check the tool arguments.'):
            raise ValueError('Raw or inappropriate error feedback')
        if 'transferred_iron_plates' in feedback:
            count = number(feedback['transferred_iron_plates'], True)
            if count > 100 or not feedback['ok'] or feedback['tool'] not in ('collect_output', 'store_plates'):
                raise ValueError('Invalid transfer feedback')
    return {'observation_policy': 'automatic', 'elapsed_ticks': tick, 'observation_tick': observed,
            'observation_age_ticks': age, 'observation': {'inventory': {'coal': coal, 'iron-plate': plates},
            'carrying': {k: carry[k] for k in ('carried_plates', 'available_carry_space', 'benchmark_carried_plate_limit')},
            'equipment': equipment}, 'result': deepcopy(feedback), 'recent_production_windows': projected_windows}


def validate_action(action, payload):
    keys(action, ('tool', 'args'))
    tool = action['tool']
    specs = {'fuel': ('building_handle', 'coal_count', ('burner-mining-drill', 'stone-furnace'), 3),
             'collect_output': ('furnace_handle', 'plate_count', ('stone-furnace',), 100),
             'store_plates': ('chest_handle', 'plate_count', ('wooden-chest',), 100)}
    if tool in ('wait', 'check'):
        keys(action['args'], ())
    elif tool in specs:
        handle_key, count_key, names, maximum = specs[tool]
        keys(action['args'], (handle_key, count_key))
        count = number(action['args'][count_key], True, 1)
        valid = {e['handle'] for e in payload['observation']['equipment'] if e['name'] in names}
        if count > maximum or action['args'][handle_key] not in valid:
            raise ValueError('Unsupported count or stale/wrong entity handle')
    else:
        raise ValueError('Unsupported action')
    canonical(action)


def token_ids(tokenizer, messages, generation):
    return tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=generation)


def render(guide, payload, history, tokenizer, max_prompt_tokens=3840):
    """Shared training/inference inputs; history contains actual attempted JSON actions."""
    if not isinstance(guide, str) or not guide:
        raise ValueError('A common guide is required')
    history = deepcopy(history[-2:])
    last_tick = -1
    for previous, action in history:
        validate_payload(previous)
        if previous['elapsed_ticks'] <= last_tick or previous['elapsed_ticks'] >= payload['elapsed_ticks']:
            raise ValueError('History must precede current state in chronological order')
        last_tick = previous['elapsed_ticks']
        keys(action, ('tool', 'args'))  # Failed attempts stay attempts, never teacher replacements.
        canonical(action)
    validate_payload(payload)
    dropped = 0
    while True:
        messages = [{'role': 'system', 'content': guide}]
        for previous, action in history:
            messages += [{'role': 'user', 'content': canonical(previous)},
                         {'role': 'assistant', 'content': canonical(action)}]
        messages.append({'role': 'user', 'content': canonical(payload)})
        count = len(token_ids(tokenizer, messages, True))
        if count <= max_prompt_tokens:
            return messages, count, dropped
        if not history:
            raise ValueError('Essential context exceeds token budget')
        history.pop(0)
        dropped += 1


def validate_payload(payload):
    """Reject extra fields even on already compact payloads, including histories."""
    checked = project(payload)
    if checked != payload:
        raise ValueError('Payload is not the exact compact whitelist projection')


def training_encoding(tokenizer, messages, action):
    """Mask all prompt/header tokens; learn target JSON and assistant end marker only."""
    prompt = token_ids(tokenizer, messages, True)
    full = token_ids(tokenizer, messages + [{'role': 'assistant', 'content': canonical(action)}], False)
    if full[:len(prompt)] != prompt:
        raise ValueError('Chat template prefix differs; loss boundary cannot be inferred')
    target = full[len(prompt):]
    # Qwen emits a separator newline after the assistant end token. Do not train that separator.
    if tokenizer.eos_token_id not in target:
        raise ValueError('Target lacks assistant end token')
    end = target.index(tokenizer.eos_token_id) + 1
    full = prompt + target[:end]
    if len(full) > 4096 or end > 256:
        raise ValueError('Target or training sequence exceeds frozen budget')
    return {'input_ids': full, 'attention_mask': [1] * len(full),
            'labels': [-100] * len(prompt) + target[:end], 'prompt_tokens': len(prompt), 'target_tokens': end}


def pad_encoding(encoding, length, pad_token_id):
    if length < len(encoding['input_ids']):
        raise ValueError('Padding may not truncate')
    n = length - len(encoding['input_ids'])
    return {'input_ids': encoding['input_ids'] + [pad_token_id] * n,
            'attention_mask': encoding['attention_mask'] + [0] * n,
            'labels': encoding['labels'] + [-100] * n}


def semantic_messages(messages):
    """Ignore handle spelling; actions reference stable entity name and position."""
    result = deepcopy(messages)
    mapping = {}
    for message in result:
        if message['role'] == 'user':
            payload = json.loads(message['content'])
            mapping = {e['handle']: canonical([e['name'], e['position']]) for e in payload['observation']['equipment']}
            for e in payload['observation']['equipment']:
                del e['handle']
            message['content'] = canonical(payload)
        elif message['role'] == 'assistant':
            action = json.loads(message['content'])
            for key in ('building_handle', 'furnace_handle', 'chest_handle'):
                if key in action['args']:
                    action['args'][key] = mapping.get(action['args'][key], 'unresolved-handle')
            message['content'] = canonical(action)
    return result
