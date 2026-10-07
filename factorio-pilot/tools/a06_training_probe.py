"""Bounded QLoRA compatibility/memory probe; no production adapter is saved."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-home', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    from cuda_review import assert_review_current
    review = assert_review_current()
    runtime = args.runtime_home.resolve()
    metadata = json.loads((runtime / 'artifacts/model-revision.json').read_text())
    snapshot = Path(metadata['snapshot_path'])
    protocol = json.loads((root / 'factorio-pilot/protocols/a06-qwen-sft-v1.json').read_text())
    if snapshot.name != protocol['model']['revision']:
        raise ValueError('Wrong model revision')
    run = runtime / 'runs' / ('A06-training-probe-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run.mkdir()
    print('RUN ' + str(run), flush=True)
    def save(name, value):
        temporary = run / (name + '.tmp')
        temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        temporary.replace(run / name)
    started = time.monotonic()
    status = {'phase': 'loading', 'pid': os.getpid(), 'run': str(run), 'started_utc': datetime.now(timezone.utc).isoformat(),
              'probe_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'native_source_hashes': review['source_hashes'], 'custom_cuda_used': False,
              'versions': {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'accelerate', 'peft', 'bitsandbytes')}}
    save('status.json', status)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from a06_dataset import load_optimizer_dataset
        from a06_context import pad_encoding
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError('CUDA BF16 unavailable')
        torch.manual_seed(42)
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
        release = root / 'factorio-pilot/evidence/datasets/A06-scripted-train-v1-20261007-r3'
        encodings, audit = load_optimizer_dataset(root, release, tokenizer, snapshot)
        model = AutoModelForCausalLM.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False,
            use_safetensors=True, torch_dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa',
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
        model.config.use_cache = False
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant': False})
        model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0,
            target_modules='all-linear', bias='none', task_type='CAUSAL_LM'))
        trainable = [p for p in model.parameters() if p.requires_grad]
        if not trainable or any(p.requires_grad and 'lora_' not in n for n, p in model.named_parameters()):
            raise RuntimeError('Unexpected trainable base weights')
        optimizer = torch.optim.AdamW(trainable, lr=2e-4)
        model.train()
        status.update(phase='probe_steps', device=torch.cuda.get_device_name(0),
            trainable_parameters=sum(p.numel() for p in trainable), dataset_manifest_sha256=audit['manifest_sha256'])
        save('status.json', status)
        short = min(encodings, key=lambda e: len(e['input_ids']))
        longest = max(encodings, key=lambda e: len(e['input_ids']))
        measurements = []
        for name, sample, length in (('short', short, len(short['input_ids'])),
                                      ('longest_recorded', longest, len(longest['input_ids'])),
                                      ('padded_contract_boundary', longest, 4096)):
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.reset_peak_memory_stats()
            batch = pad_encoding(sample, length, tokenizer.pad_token_id)
            batch = {key: torch.tensor([value], dtype=torch.long, device='cuda') for key, value in batch.items()}
            torch.cuda.synchronize()
            before = time.perf_counter()
            output = model(**batch)
            loss = output.loss
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite training loss')
            loss.backward()
            gradients = [p.grad for p in trainable if p.grad is not None]
            if not gradients or any(not torch.isfinite(g).all().item() for g in gradients):
                raise RuntimeError('Missing or nonfinite adapter gradients')
            norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            if not math.isfinite(norm.item()):
                raise RuntimeError('Nonfinite gradient norm')
            optimizer.step()
            torch.cuda.synchronize()
            measurements.append({'case': name, 'sequence_length': length, 'loss': loss.item(),
                'gradient_norm': norm.item(), 'step_seconds': time.perf_counter()-before,
                'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                'peak_reserved_bytes': torch.cuda.max_memory_reserved(), 'passed': True})
            del output, loss, batch
            status.update(last_case=name, measurements=measurements)
            save('status.json', status)
            print('PROBE_CASE ' + json.dumps(measurements[-1]), flush=True)
        status.update(phase='complete', passed=True, elapsed_seconds=time.monotonic()-started,
            scope='Three bounded smoke updates; no saved trained adapter, gameplay result or model improvement claim')
        save('summary.json', status)
        save('status.json', status)
    except Exception as error:
        status.update(phase='failed', passed=False, error_type=type(error).__name__, error=str(error)[-2000:],
                      elapsed_seconds=time.monotonic()-started)
        save('status.json', status)
        raise


if __name__ == '__main__':
    main()
