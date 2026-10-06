"""Instance-local, reversible dispatch to the reviewed inference-only kernel."""

from collections import Counter
from contextlib import contextmanager
import math
import os
from pathlib import Path
import struct
import types

import torch
from cuda_review import assert_review_current
from runtime_paths import runtime_home


def unsupported_reason(x, weight, epsilon, training=False):
    """Mirror native preconditions without copies, device reads or launches.

    Return a stable fallback reason, or None for supported inference inputs.
    The native binding remains authoritative; its runtime errors propagate.
    """
    if training or not torch.is_inference_mode_enabled():
        return 'not_inference_mode'
    if not x.is_cuda or not weight.is_cuda:
        return 'non_cuda'
    if x.device != weight.device:
        return 'device_mismatch'
    if x.layout != torch.strided or weight.layout != torch.strided:
        return 'layout'
    if x.dtype != torch.bfloat16 or weight.dtype != torch.bfloat16:
        return 'dtype'
    if x.dim() < 1 or x.shape[-1] != 2560 or weight.dim() != 1 or weight.numel() != 2560:
        return 'shape'
    if not x.is_contiguous() or not weight.is_contiguous():
        return 'noncontiguous'
    if x.is_neg() or weight.is_neg():
        return 'negative_view'
    if x.requires_grad or weight.requires_grad:
        return 'requires_grad'
    if not math.isfinite(epsilon) or not 0 < epsilon <= 1:
        return 'epsilon'
    converted = struct.unpack('f', struct.pack('f', epsilon))[0]
    if not math.isfinite(converted) or converted < 2 ** -126:
        return 'epsilon_fp32'
    if x.numel() // 2560 > 8192:
        return 'row_limit'
    return None


def load_reviewed_extension():
    """Load/build only active reviewed sources after matching correctness evidence.

    Compilation uses existing bounded build settings. Review/load failures stop
    the custom condition rather than silently running the reference backend.
    """
    assert_review_current('benchmark')
    from torch.utils.cpp_extension import load
    source = Path(__file__).resolve().parents[1] / 'cuda'
    build = runtime_home() / 'build/rmsnorm'
    build.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MAX_JOBS', '2')
    os.environ.setdefault('TORCH_CUDA_ARCH_LIST', '12.0')
    return load(name='pilot_rmsnorm', sources=[str(source/'rmsnorm.cpp'), str(source/'rmsnorm.cu')],
                build_directory=str(build), extra_cflags=['-O3'],
                extra_cuda_cflags=['-O3', '--fmad=false', '-lineinfo'], verbose=True)


class RMSNormDispatch:
    """Install reversible forwards on compatible full-width Qwen3 norms.

    Existing parameters and state-dictionary names remain unchanged. Callers
    freeze parameters and use inference_mode. Diagnostics are opt-in and should
    be disabled for timing. Installation and restoration never launch CUDA.
    """
    def __init__(self, model, operation, diagnostics=False):
        from transformers.models.qwen3.modeling_qwen3 import Qwen3RMSNorm
        self.model = model
        self.operation = operation
        self.diagnostics = diagnostics
        self.counts = Counter()
        self.shapes = Counter()
        self.originals = []
        self.skipped = []
        selected = []
        for name, module in model.named_modules():
            if type(module) is not Qwen3RMSNorm:
                continue
            allowed = name == 'model.norm' or (
                name.startswith('model.layers.') and name.rsplit('.', 1)[-1]
                in ('input_layernorm', 'post_attention_layernorm'))
            if not allowed or tuple(module.weight.shape) != (2560,):
                self.skipped.append(name)
                continue
            if '_pilot_original_forward' in module.__dict__:
                raise RuntimeError('An RMSNorm adapter is already installed')
            selected.append((name, module))
        if not selected:
            raise RuntimeError('No compatible Qwen3 full-width norms found')
        self.module_names = [name for name, _ in selected]
        for name, module in selected:
            original = module.forward
            had_override = 'forward' in module.__dict__
            self.originals.append((module, original, had_override))
            module._pilot_original_forward = original
            module.forward = types.MethodType(self._make_forward(name, original), module)

    def _make_forward(self, name, original):
        """Capture each original explicitly so wrappers cannot share a late binding."""
        def forward(module, hidden_states):
            reason = unsupported_reason(hidden_states, module.weight,
                                        module.variance_epsilon, module.training)
            if self.diagnostics:
                self.counts['custom' if reason is None else 'fallback:'+reason] += 1
                self.shapes[(name, tuple(hidden_states.shape))] += 1
            if reason is not None:
                return original(hidden_states)
            return self.operation(hidden_states, module.weight, module.variance_epsilon)
        return forward

    def coverage(self):
        """Return CPU metadata proving dispatch and exposing unsupported-call reasons."""
        return {'replaced_modules': self.module_names, 'untouched_norms': self.skipped,
                'counts': dict(self.counts),
                'observed_shapes': [{'module': name, 'shape': list(shape), 'calls': count}
                                    for (name, shape), count in self.shapes.items()]}

    def restore(self):
        """Restore instance/class dispatch exactly, without changing model weights."""
        for module, original, had_override in reversed(self.originals):
            if had_override:
                module.forward = original
            else:
                del module.forward
            del module._pilot_original_forward
        self.originals.clear()


@contextmanager
def custom_rmsnorm(model, operation, diagnostics=False):
    """Restore the reference forwards even when an operation or validation fails."""
    dispatch = RMSNormDispatch(model, operation, diagnostics)
    try:
        yield dispatch
    finally:
        dispatch.restore()
