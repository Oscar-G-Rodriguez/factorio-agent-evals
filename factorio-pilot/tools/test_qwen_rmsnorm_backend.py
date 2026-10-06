"""CPU contracts for guarded dispatch; no model weights or GPU are required."""
import unittest
from types import SimpleNamespace
import torch
from transformers.models.qwen3.modeling_qwen3 import Qwen3RMSNorm
from qwen_rmsnorm_backend import custom_rmsnorm, unsupported_reason


class FakeTensor:
    """Metadata-only tensor surrogate for precondition tests without CUDA."""
    def __init__(self, shape=(1, 2560), **values):
        self.shape = shape
        self.is_cuda = True
        self.device = 'cuda:0'
        self.layout = torch.strided
        self.dtype = torch.bfloat16
        self.requires_grad = False
        self.contiguous = True
        self.negative = False
        self.__dict__.update(values)
    def dim(self): return len(self.shape)
    def numel(self):
        import math
        return math.prod(self.shape)
    def is_contiguous(self): return self.contiguous
    def is_neg(self): return self.negative


class BackendTests(unittest.TestCase):
    def test_metadata_bounds(self):
        """All unsupported conditions are caught before the native call."""
        cases = [(FakeTensor(is_cuda=False), 'non_cuda'),
                 (FakeTensor(dtype=torch.float32), 'dtype'),
                 (FakeTensor(shape=(1, 128)), 'shape'),
                 (FakeTensor(contiguous=False), 'noncontiguous'),
                 (FakeTensor(negative=True), 'negative_view'),
                 (FakeTensor(requires_grad=True), 'requires_grad'),
                 (FakeTensor(shape=(8193,2560)), 'row_limit'),
                 (FakeTensor(device='cuda:1'), 'device_mismatch'),
                 (FakeTensor(layout=torch.sparse_coo), 'layout')]
        with torch.inference_mode():
            for x, reason in cases:
                with self.subTest(reason=reason):
                    self.assertEqual(unsupported_reason(x, FakeTensor((2560,)), 1e-6), reason)
            self.assertIsNone(unsupported_reason(FakeTensor((0,2560)), FakeTensor((2560,)), 1e-6))
            self.assertIsNone(unsupported_reason(FakeTensor((8192,2560)), FakeTensor((2560,)), 1e-6))
            for epsilon in (0, -1, float('nan'), float('inf'), 2):
                self.assertEqual(unsupported_reason(FakeTensor(), FakeTensor((2560,)), epsilon), 'epsilon')
            for epsilon in (1e-300,1e-40):
                self.assertEqual(unsupported_reason(FakeTensor(), FakeTensor((2560,)), epsilon), 'epsilon_fp32')

    def test_inference_required(self):
        self.assertEqual(unsupported_reason(FakeTensor(), FakeTensor((2560,)), 1e-6), 'not_inference_mode')

    def model(self):
        """A tiny norm-only module tree matches Qwen paths, without a Qwen model."""
        root = torch.nn.Module()
        root.model = torch.nn.Module()
        root.model.layers = torch.nn.ModuleList([torch.nn.Module()])
        layer = root.model.layers[0]
        layer.input_layernorm = Qwen3RMSNorm(2560)
        layer.post_attention_layernorm = Qwen3RMSNorm(2560)
        layer.self_attn = torch.nn.Module()
        layer.self_attn.q_norm = Qwen3RMSNorm(128)
        root.model.norm = Qwen3RMSNorm(2560)
        return root.eval().requires_grad_(False)

    def test_cpu_fallback_and_restoration(self):
        root = self.model()
        norm = root.model.norm
        original = norm.forward
        keys = list(root.state_dict())
        x = torch.randn(2,2560)
        with torch.inference_mode():
            expected = original(x)
            with custom_rmsnorm(root, lambda *args: self.fail('CPU must not launch'), True) as dispatch:
                torch.testing.assert_close(norm(x), expected)
                self.assertEqual(len(dispatch.module_names), 3)
                self.assertEqual(dispatch.coverage()['counts'], {'fallback:non_cuda': 1})
                self.assertEqual(dispatch.skipped, ['model.layers.0.self_attn.q_norm'])
                self.assertEqual(list(root.state_dict()), keys)
            self.assertEqual(norm.forward, original)
            self.assertNotIn('forward', norm.__dict__)

    def test_restore_after_error(self):
        root = self.model()
        with self.assertRaisesRegex(RuntimeError, 'probe'):
            with custom_rmsnorm(root, lambda *args: None):
                raise RuntimeError('probe')
        self.assertNotIn('_pilot_original_forward', root.model.norm.__dict__)

    def test_double_install_rejected(self):
        root = self.model()
        with custom_rmsnorm(root, lambda *args: None):
            with self.assertRaisesRegex(RuntimeError, 'already installed'):
                with custom_rmsnorm(root, lambda *args: None): pass


if __name__ == '__main__':
    unittest.main()
