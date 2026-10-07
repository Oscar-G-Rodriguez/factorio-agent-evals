"""Finite, audited QLoRA worker. Weights and optimizer states remain outside Git."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import random
import signal
import time
from datetime import datetime, timezone
from pathlib import Path


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-home', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--round', type=int, choices=(1, 2, 3), required=True)
    parser.add_argument('--initial-adapter', type=Path)
    parser.add_argument('--corrections', type=Path)
    parser.add_argument('--probe-optimizer-steps', type=int, choices=(2, 3))
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--verify-reload', action='store_true')
    args = parser.parse_args()
    from cuda_review import assert_review_current
    review = assert_review_current()
    root = Path(__file__).resolve().parents[2]
    runtime = args.runtime_home.resolve()
    gpu_lock = (runtime / 'a06-gpu-worker.lock').open('a')
    fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    run = args.run.resolve()
    if run.parent != runtime / 'runs' or not run.name.startswith('A06-training-'):
        raise ValueError('Training output must be a new external A06 training directory')
    if args.round == 1 and (args.initial_adapter or args.corrections):
        raise ValueError('Round1 starts with unchanged weights')
    if args.round > 1 and not (args.initial_adapter and args.corrections):
        raise ValueError('Later rounds need selected previous adapter and verified corrections')
    run.mkdir(exist_ok=args.resume)
    source = run / 'source'
    source.mkdir(exist_ok=args.resume)
    names = ('a06_train.py', 'a06_context.py', 'a06_dataset.py', 'cuda_review.py','a06_workflow.py','a06_corrections.py')
    hashes = {}
    for name in names:
        path = Path(__file__).with_name(name)
        if args.resume and (source/name).read_bytes()!=path.read_bytes():
            raise ValueError('Resume source changed; refuse incompatible continuation')
        if not args.resume: (source / name).write_bytes(path.read_bytes())
        hashes[name] = sha(path)
    config_path = root / 'factorio-pilot/protocols/a06-three-round-v1.json'
    config = json.loads(config_path.read_text())
    settings = config['training']
    if args.resume and (run/config_path.name).read_bytes()!=config_path.read_bytes():
        raise ValueError('Resume protocol changed')
    if not args.resume: (run / config_path.name).write_bytes(config_path.read_bytes())
    started = time.monotonic()
    status = {'phase': 'loading', 'pid': os.getpid(), 'process_start_ticks': Path('/proc/self/stat').read_text().split()[21],
              'started_utc': datetime.now(timezone.utc).isoformat(), 'round': args.round, 'run': str(run),
              'source_hashes': hashes, 'native_source_hashes': review['source_hashes'],
              'config_sha256': sha(config_path), 'custom_cuda_used': False, 'probe_only':bool(args.probe_optimizer_steps),
              'versions': {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'accelerate', 'peft', 'bitsandbytes')}}
    write_json(run / 'status.json', status)
    print('RUN ' + str(run), flush=True)
    interrupted = [False]
    def request_pause(signum,frame): interrupted[0]=True
    signal.signal(signal.SIGTERM,request_pause)
    signal.signal(signal.SIGINT,request_pause)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
        from a06_dataset import load_optimizer_dataset
        from a06_context import training_encoding, pad_encoding
        metadata = json.loads((runtime / 'artifacts/model-revision.json').read_text())
        snapshot = Path(metadata['snapshot_path'])
        protocol = json.loads((root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json').read_text())
        if snapshot.name != protocol['model']['revision']:
            raise ValueError('Model revision changed')
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
        release = root / 'factorio-pilot/evidence/datasets' / config['round1']['dataset']
        encodings, audit = load_optimizer_dataset(root, release, tokenizer, snapshot)
        rng = random.Random(config['seed'])
        order = list(range(len(encodings)))
        rng.shuffle(order)
        if args.round > 1:
            # Importing the separate verifier is intentional: round1 releases remain immutable.
            from a06_corrections import audit_corrections
            rows, correction_audit = audit_corrections(args.corrections, root, runtime, tokenizer, snapshot)
            corrected = [training_encoding(tokenizer, r['messages'], r['target_action']) for r in rows]
            if not corrected:
                raise ValueError('No verified corrections; cannot perform meaningful round2')
            examples = [encodings[i] for i in order[:160]] + [rng.choice(corrected) for _ in range(160)]
            rng.shuffle(examples)
            status['correction_audit'] = correction_audit
            status['initial_adapter_files'] = {p.name: sha(p) for p in args.initial_adapter.iterdir() if p.is_file()}
        else:
            examples = [encodings[i] for i in order]
        if len(examples) != settings['optimizer_steps'] * settings['gradient_accumulation']:
            raise ValueError('Declared sample count does not match optimizer steps')
        if any(len(e['input_ids']) > settings['max_training_sequence_tokens'] for e in examples):
            raise ValueError('Training example exceeds measured-safe sequence limit; no silent truncation')
        torch.manual_seed(config['seed'])
        torch.cuda.manual_seed_all(config['seed'])
        model = AutoModelForCausalLM.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False,
            use_safetensors=True, dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa',
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant': False})
        resume_checkpoint = None
        if args.resume:
            checkpoints = sorted((p for p in run.glob('checkpoint-*') if (p/'receipt.json').exists()), key=lambda p:int(p.name.split('-')[-1]))
            if not checkpoints: raise ValueError('No complete checkpoint to resume')
            resume_checkpoint = checkpoints[-1]
            receipt = json.loads((resume_checkpoint/'receipt.json').read_text())
            if receipt['config_sha256']!=sha(config_path) or any(sha(resume_checkpoint/name)!=expected for name,expected in receipt['files'].items()):
                raise ValueError('Resume checkpoint hash/config mismatch')
        if resume_checkpoint or args.initial_adapter:
            model = PeftModel.from_pretrained(model, resume_checkpoint or args.initial_adapter, is_trainable=True)
        else:
            model = get_peft_model(model, LoraConfig(r=settings['rank'], lora_alpha=settings['alpha'],
                lora_dropout=settings['dropout'], target_modules=settings['target_modules'], bias='none', task_type='CAUSAL_LM'))
        trainable = [p for p in model.parameters() if p.requires_grad]
        if not trainable or any(p.requires_grad and 'lora_' not in n for n, p in model.named_parameters()):
            raise RuntimeError('Unexpected trainable base weights')
        optimizer = torch.optim.AdamW(trainable, lr=settings['learning_rate'], weight_decay=settings['weight_decay'])
        first_step=0
        if resume_checkpoint:
            saved=torch.load(resume_checkpoint/'optimizer.pt',map_location='cuda',weights_only=True)
            optimizer.load_state_dict(saved['optimizer'])
            torch.set_rng_state(saved['torch_rng_state'].cpu())
            torch.cuda.set_rng_state_all([s.cpu() for s in saved['cuda_rng_state']])
            first_step=saved['optimizer_step']
        model.train()
        status.update(phase='training', trainable_parameters=sum(p.numel() for p in trainable),
                      dataset_audit=audit, micro_steps=0, optimizer_steps=0, device=torch.cuda.get_device_name(0))
        if not args.resume:write_json(run / 'config.json', status | {'training': settings, 'sample_order': order if args.round == 1 else 'recorded_per_step'})
        losses = []
        if first_step>=settings['optimizer_steps']:raise ValueError('Completed checkpoint must not be retrained')
        torch.cuda.reset_peak_memory_stats()
        frozen_samples={n:p.detach().flatten()[:64].clone() for n,p in model.named_parameters() if not p.requires_grad and p.numel() and ('embed_tokens' in n or 'norm.weight' in n)} if args.verify_reload else {}
        adapter_before=[p.detach().clone() for p in trainable] if args.verify_reload else []
        with (run / 'training.jsonl').open('a' if args.resume else 'x', buffering=1) as log:
            for step in range(first_step,args.probe_optimizer_steps or settings['optimizer_steps']):
                if time.monotonic() - started > config['limits']['worker_wall_seconds']:
                    raise TimeoutError('Training budget exceeded; not a gameplay failure')
                optimizer.zero_grad(set_to_none=True)
                group_losses = []
                before = time.perf_counter()
                for offset in range(settings['gradient_accumulation']):
                    micro_start = time.perf_counter()
                    sample = examples[step * settings['gradient_accumulation'] + offset]
                    batch = pad_encoding(sample, len(sample['input_ids']), tokenizer.pad_token_id)
                    batch = {k: torch.tensor([v], dtype=torch.long, device='cuda') for k, v in batch.items()}
                    output = model(**batch)
                    if not torch.isfinite(output.loss).item():
                        raise RuntimeError('Nonfinite loss')
                    value = output.loss.item()
                    (output.loss / settings['gradient_accumulation']).backward()
                    group_losses.append(value)
                    del batch, output
                    # Avoid WDDM memory pressure from inactive cached allocations.
                    # Recorded as a runtime revision, never a training-data change.
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    log.write(json.dumps({'optimizer_step': step+1, 'micro_step': offset,
                        'encoding_sha256': hashlib.sha256(json.dumps(sample, sort_keys=True).encode()).hexdigest(),
                        'loss': value, 'sequence_tokens': len(sample['input_ids']),
                        'seconds':time.perf_counter()-micro_start,
                        'allocated_bytes':torch.cuda.memory_allocated(), 'reserved_bytes':torch.cuda.memory_reserved()})+'\n')
                grads = [p.grad for p in trainable if p.grad is not None]
                if not grads or any(not torch.isfinite(g).all().item() for g in grads):
                    raise RuntimeError('Missing or nonfinite adapter gradients')
                norm = torch.nn.utils.clip_grad_norm_(trainable, settings['max_gradient_norm'])
                if not math.isfinite(norm.item()):
                    raise RuntimeError('Nonfinite gradient norm')
                optimizer.step()
                torch.cuda.synchronize()
                losses += group_losses
                receipt = {'optimizer_step': step+1, 'mean_loss': sum(group_losses)/len(group_losses),
                    'gradient_norm': norm.item(), 'seconds': time.perf_counter()-before,
                    'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                    'peak_reserved_bytes': torch.cuda.max_memory_reserved()}
                log.write(json.dumps(receipt)+'\n')
                status.update(phase='training', optimizer_steps=step+1, micro_steps=(step+1)*settings['gradient_accumulation'],
                              latest=receipt, elapsed_seconds=time.monotonic()-started)
                from a06_workflow import pause_requested
                pausing=interrupted[0] or pause_requested(runtime)
                if (step+1)%settings['resume_checkpoint_interval']==0 or pausing or args.verify_reload and step+1==(args.probe_optimizer_steps or settings['optimizer_steps']):
                    checkpoint = run / ('checkpoint-' + str(step+1))
                    model.save_pretrained(checkpoint, safe_serialization=True)
                    torch.save({'optimizer': optimizer.state_dict(), 'torch_rng_state': torch.get_rng_state(),
                        'cuda_rng_state': torch.cuda.get_rng_state_all(), 'optimizer_step': step+1,
                        'sample_encoding_hashes':[hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest() for e in examples]}, checkpoint/'optimizer.pt')
                    write_json(checkpoint/'receipt.json', {'step': step+1, 'round': args.round,
                        'files': {p.name: sha(p) for p in checkpoint.iterdir() if p.is_file()}, 'config_sha256': sha(config_path)})
                    status.setdefault('checkpoints', []).append(str(checkpoint))
                write_json(run / 'status.json', status)
                print('TRAIN_STEP '+json.dumps(receipt), flush=True)
                if pausing:
                    status.update(phase='paused',passed=False,reason='User pause request at optimizer boundary')
                    write_json(run/'status.json',status)
                    return
        if args.verify_reload:
            if not any(not torch.equal(p,before) for p,before in zip(trainable,adapter_before)):
                raise RuntimeError('Adapter parameters did not update')
            if any(p.grad is not None for p in model.parameters() if not p.requires_grad):
                raise RuntimeError('Frozen base received gradients')
            named=dict(model.named_parameters())
            if any(not torch.equal(named[n].detach().flatten()[:64],before) for n,before in frozen_samples.items()):
                raise RuntimeError('Frozen base sample changed')
            model.eval();model.config.use_cache=True
            messages=json.loads((release/'train.jsonl').read_text().splitlines()[0])['messages']
            inputs=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True).to('cuda')
            with torch.inference_mode(): original=model.generate(**inputs,max_new_tokens=64,do_sample=False).cpu()
            checkpoint=run/('checkpoint-'+str(step+1))
            base=model.unload()
            del model,optimizer,trainable,adapter_before,frozen_samples
            torch.cuda.empty_cache()
            model=PeftModel.from_pretrained(base,checkpoint,is_trainable=False).eval()
            model.config.use_cache=True
            with torch.inference_mode(): reloaded=model.generate(**inputs,max_new_tokens=64,do_sample=False).cpu()
            if not torch.equal(original,reloaded): raise RuntimeError('Reloaded adapter changed greedy tokens')
            write_json(run/'reload-verification.json',{'passed':True,'adapter_updated':True,'base_gradient_absent':True,
                'sampled_frozen_base_unchanged':True,'greedy_token_identity':True,'tokens':original.tolist(),
                'checkpoint_sha256':{p.name:sha(p) for p in checkpoint.iterdir() if p.is_file()}})
        status.update(phase='complete', passed=True, elapsed_seconds=time.monotonic()-started,
            mean_loss=sum(losses)/len(losses), first_group_mean_loss=sum(losses[:8])/8,
            last_group_mean_loss=sum(losses[-8:])/8, scope='Memory/runtime probe only; no saved adapter' if args.probe_optimizer_steps else 'Training only; gameplay improvement requires held-out execution')
        write_json(run / 'summary.json', status)
        write_json(run / 'status.json', status)
    except Exception as exc:
        status.update(phase='failed', passed=False, error_type=type(exc).__name__, error=str(exc)[-2000:], elapsed_seconds=time.monotonic()-started)
        write_json(run / 'status.json', status)
        raise


if __name__ == '__main__':
    main()
