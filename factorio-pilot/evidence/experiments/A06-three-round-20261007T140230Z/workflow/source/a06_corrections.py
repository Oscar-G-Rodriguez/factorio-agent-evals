"""Train-only corrective release: proposals never qualify without executed replay."""
import argparse
import json
from pathlib import Path
from a06_context import canonical, digest, semantic_messages, validate_action, render, project, training_encoding
from a06_workflow import read, write, sha, protocol


def equivalent_key(messages,action):
    normalized=semantic_messages(messages+[{'role':'assistant','content':canonical(action)}])
    for message in normalized:
        if message['role']=='user':
            payload=json.loads(message['content'])
            for key in ('elapsed_ticks','observation_tick','observation_age_ticks'): payload.pop(key,None)
            for window in payload['recent_production_windows']:
                for key in ('index','start_tick','end_tick'): window.pop(key,None)
            message['content']=canonical(payload)
    return digest(normalized)


def problem(row):
    obs=row['agent_visible_input']['observation']
    action=row.get('action')
    teacher=row['teacher_proposal']
    if action==teacher: return None
    if row['failed_action']:
        if isinstance(action,dict) and action.get('tool') in ('collect_output','store_plates'):
            return 'blocked transfer'
        return 'invalid action'
    furnace=next(e for e in obs['equipment'] if e['name']=='stone-furnace')
    carrying=obs['carrying']['carried_plates']
    if teacher['tool']=='fuel':
        entity=next(e for e in obs['equipment'] if e['handle']==teacher['args']['building_handle'])
        fuel=entity['burner']
        if fuel['coal_in_fuel_inventory']==0 and fuel['remaining_burning_fuel_joules']<=1000000:
            return 'fuel neglect'
    if isinstance(action,dict) and action.get('tool')=='wait':
        if (carrying==100 and furnace['output_storage']['iron_plates']>=60
            or carrying<100 and furnace['output_storage']['iron_plates']>=95):
            return 'verified harmful wait'
    return None


def candidates(episode,root):
    config=read(episode/'config.json')
    if config['purpose']!='train-diagnostic' or config['fixture']['partition']!='train':
        raise ValueError('Corrections cannot originate from reserved fixtures')
    if config['condition'] not in ('round1_4bit','round2_4bit'):
        raise ValueError('Corrections require an executed prior training round')
    rows=[json.loads(line) for line in (episode/'steps.jsonl').read_text().splitlines()]
    priorities=protocol(root)[0]['corrections']['priority']
    selected=[];seen=set()
    for row in rows:
        label=problem(row)
        if not label: continue
        action=row['teacher_proposal']
        validate_action(action,row['agent_visible_input'])
        key=equivalent_key(row['prompt_messages'],action)
        if key in seen: continue
        seen.add(key)
        selected.append({'episode':str(episode),'fixture_id':config['fixture']['id'],'step':row['step'],
                         'target_action':action,'problem':label,'semantic_key':key,
                         'trace_sha256':sha(episode/'steps.jsonl')})
    selected.sort(key=lambda c:(priorities.index(c['problem']),c['step']))
    return selected[:protocol(root)[0]['corrections']['max_candidates_per_fixture']]


def audit_corrections(release,root,runtime,tokenizer,snapshot):
    release=Path(release).resolve()
    manifest=read(release/'manifest.json')
    plan,plan_hash=protocol(root)
    if manifest['protocol_sha256']!=plan_hash: raise ValueError('Correction protocol changed')
    if {p.name for p in release.iterdir() if p.is_file()}!={'manifest.json','train.jsonl'}:
        raise ValueError('Unexpected correction release files')
    if sha(release/'train.jsonl')!=manifest['train_sha256']: raise ValueError('Correction data changed')
    rows=[json.loads(line) for line in (release/'train.jsonl').read_text().splitlines()]
    fixture_ids=set();seen=set()
    parent=read(root/'factorio-pilot/protocols/a06-qwen-sft-v1.json')
    allowed={f['id'] for f in parent['fixtures'] if f['partition']=='train'}
    guide=(root/parent['context']['guide_path']).read_bytes().decode('utf-8')
    for row in rows:
        if row['fixture_id'] not in allowed or row['partition']!='train' or row['label_source']!='reviewed_replay':
            raise ValueError('Reserved or unverified correction row')
        fixture_ids.add(row['fixture_id'])
        episode=Path(row['episode']).resolve();verification=Path(row['verification_run']).resolve()
        if episode.parent!=runtime/'runs' or verification.parent!=runtime/'runs':
            raise ValueError('Correction provenance escapes runtime')
        config=read(episode/'config.json')
        if config['fixture']['id']!=row['fixture_id'] or config['purpose']!='train-diagnostic':
            raise ValueError('Correction lineage partition mismatch')
        if sha(episode/'steps.jsonl')!=row['trace_sha256'] or sha(verification/'correction_verification.json')!=row['verification_sha256']:
            raise ValueError('Execution evidence changed')
        proof=read(verification/'correction_verification.json')
        if not all(proof.get(k) is True for k in ('accepted','exact_pre_action_restore','corrective_action_executed','observed_problem_addressed','full_horizon_survived')):
            raise ValueError('Correction lacks required execution checks')
        for name,key in (('continuation.jsonl','continuation_sha256'),('corrective_action.json','action_receipt_sha256'),
                         ('candidate_restore.json','candidate_restore_sha256'),('native_save.json','native_save_sha256')):
            if sha(verification/name)!=proof[key]: raise ValueError('Corrective execution record changed')
        restore=read(verification/'candidate_restore.json')
        if not restore['exact_match'] or restore['expected']!=restore['actual']:
            raise ValueError('Pre-action restore was not exact')
        continuation=[json.loads(line) for line in (verification/'continuation.jsonl').read_text().splitlines()]
        if not continuation or continuation[0]['action']!=row['target_action'] or continuation[-1]['step']!=79 or proof['final_tick']-proof['origin_tick']!=72000:
            raise ValueError('Missing executed target or full horizon')
        if any(b['tick']-a['tick']!=900 for a,b in zip(continuation,continuation[1:])):
            raise ValueError('Correction continuation cadence changed')
        if proof['stop_reason']!='survived_simulation_limit' or len(proof['measurement_windows'])!=20:
            raise ValueError('Full original horizon not observed')
        if any(w['consecutive_low_windows']>=2 for w in proof['measurement_windows']):
            raise ValueError('Scripted continuation had sustained failure')
        receipt=read(verification/'native_save.json')
        master=runtime/receipt['archive_relative_to_runtime']
        if not master.resolve().is_relative_to(runtime/'native-fixtures') or sha(master)!=receipt['sha256']:
            raise ValueError('Pre-action master save changed')
        trace=[json.loads(line) for line in (episode/'steps.jsonl').read_text().splitlines()]
        original=trace[row['decision_index']]
        if original['prompt_messages']!=row['messages'] or original['teacher_proposal']!=row['target_action']:
            raise ValueError('Correction changed actual inputs or target proposal')
        if proof['candidate']['step']!=row['decision_index'] or proof['candidate']['episode']!=row['episode'] or proof['target_action']!=row['target_action']:
            raise ValueError('Proof belongs to another state or target')
        payload=original['agent_visible_input']
        validate_action(row['target_action'],payload)
        history=[]
        for previous in trace[max(0,row['decision_index']-2):row['decision_index']]:
            action=previous['action']
            if isinstance(action,dict) and set(action)=={'tool','args'}:
                history.append((previous['agent_visible_input'],action))
        reproduced,_,_=render(guide,payload,history,tokenizer)
        if reproduced!=row['messages']: raise ValueError('Historical model context does not reconstruct')
        encoding=training_encoding(tokenizer,row['messages'],row['target_action'])
        if len(encoding['input_ids'])>plan['training']['max_training_sequence_tokens']:
            raise ValueError('Correction exceeds training token limit')
        key=equivalent_key(row['messages'],row['target_action'])
        if key in seen: raise ValueError('Equivalent correction duplicated')
        seen.add(key)
    if len(rows)<plan['corrections']['minimum_distinct_rows'] or len(fixture_ids)<plan['corrections']['minimum_fixtures']:
        raise ValueError('Insufficient verified corrective data')
    if manifest['rows']!=len(rows) or sorted(fixture_ids)!=manifest['fixtures']:
        raise ValueError('Incorrect correction counts')
    return rows,{'passed':True,'rows':len(rows),'fixtures':sorted(fixture_ids),'manifest_sha256':sha(release/'manifest.json')}


def build_release(verifications,output,root,runtime,tokenizer,snapshot):
    rows=[];seen=set()
    for verification in verifications:
        proof=read(verification/'correction_verification.json')
        if not proof['accepted']: continue
        candidate=proof['candidate'];episode=Path(candidate['episode'])
        trace=[json.loads(line) for line in (episode/'steps.jsonl').read_text().splitlines()]
        original=trace[candidate['step']]
        key=equivalent_key(original['prompt_messages'],candidate['target_action'])
        if key in seen: continue
        seen.add(key)
        rows.append({'schema_version':1,'partition':'train','fixture_id':candidate['fixture_id'],
            'episode':str(episode),'decision_index':candidate['step'],'messages':original['prompt_messages'],
            'target_action':candidate['target_action'],'label_source':'reviewed_replay',
            'trace_sha256':sha(episode/'steps.jsonl'),'verification_run':str(verification),
            'verification_sha256':sha(verification/'correction_verification.json')})
    output.mkdir(exist_ok=False)
    (output/'train.jsonl').write_text(''.join(canonical(r)+'\n' for r in rows))
    write(output/'manifest.json',{'protocol_sha256':protocol(root)[1],'rows':len(rows),
        'fixtures':sorted({r['fixture_id'] for r in rows}),'train_sha256':sha(output/'train.jsonl')})
    return audit_corrections(output,root,runtime,tokenizer,snapshot)[1]


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-home',type=Path,required=True)
    parser.add_argument('--verifications',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];runtime=args.runtime_home.resolve()
    from transformers import AutoTokenizer
    snapshot=Path(read(runtime/'artifacts/model-revision.json')['snapshot_path'])
    tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
    print(json.dumps(build_release([Path(p) for p in read(args.verifications)],args.output,root,runtime,tokenizer,snapshot)))
