import json
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from a06_workflow import selection,partition_gate,gpu_lock,process_identity,alive
from a06_corrections import candidates,problem,equivalent_key


class WorkflowTests(unittest.TestCase):
    def records(self):
        return [{'checkpoint_step':step,'config':{'purpose':'validation','fixture':{'partition':'validation','id':fixture}},
                 'summary':{'stop_reason':'survived_simulation_limit','simulated_seconds':1200,'new_iron_plates':375}}
                for step in (20,40) for fixture in ('validation_fuel','validation_storage')]
    def test_selection_tie_earliest_and_no_test(self):
        rows=self.records();self.assertEqual(selection(rows)['selected_step'],20)
        rows[-1]['summary']['new_iron_plates']=376;self.assertEqual(selection(rows)['selected_step'],40)
        rows[-1]['config']['purpose']='final-test'
        with self.assertRaises(ValueError):selection(rows)
    def test_incomplete_not_survival(self):
        rows=self.records();rows[0]['summary']['stop_reason']='wall_time_limit_incomplete'
        with self.assertRaises(ValueError):selection(rows)
    def test_missing_and_duplicate_conditions(self):
        with self.assertRaises(ValueError):selection(self.records()[:-1])
        with self.assertRaises(ValueError):selection(self.records()+self.records()[:1])
    def test_reserved_partition_rejection(self):
        for partition in ('validation','test'):
            with self.assertRaises(ValueError):partition_gate({'partition':partition},'train-diagnostic')
    def test_lock_prevents_duplicate_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            first=gpu_lock(Path(directory))
            try:
                with self.assertRaises(RuntimeError):gpu_lock(Path(directory))
            finally:first.close()
    def test_pid_identity_checks_start_and_command(self):
        identity=process_identity(os.getpid());self.assertTrue(alive(identity))
        self.assertFalse(alive(dict(identity,process_start_ticks='0')))
        self.assertFalse(alive(dict(identity,argv=['wrong-command'])))
    def test_offline_and_reserved_trace_cannot_supply_corrections(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'config.json').write_text(json.dumps({'purpose':'validation','fixture':{'partition':'validation'}}))
            with self.assertRaises(ValueError):candidates(path,path)


class TrainingCPUTests(unittest.TestCase):
    def test_masked_loss_adapter_updates_and_optimizer_resume(self):
        import torch
        torch.manual_seed(42)
        base=torch.nn.Parameter(torch.randn(4,4),requires_grad=False)
        a=torch.nn.Parameter(torch.randn(2,4)*.01);b=torch.nn.Parameter(torch.zeros(4,2))
        x=torch.randn(1,5,4);labels=torch.tensor([[-100,-100,-100,1,2]])
        optimizer=torch.optim.AdamW([a,b],lr=.01)
        frozen=base.detach().clone()
        def step(a,b,optimizer):
            optimizer.zero_grad(set_to_none=True)
            logits=x@(base+b@a).T
            loss=torch.nn.functional.cross_entropy(logits[:,:-1,:].reshape(-1,4),labels[:,1:].reshape(-1),ignore_index=-100)
            manual=torch.nn.functional.cross_entropy(logits[:,2:4,:].reshape(-1,4),labels[:,3:5].reshape(-1))
            self.assertTrue(torch.allclose(loss,manual));loss.backward();optimizer.step()
        step(a,b,optimizer)
        self.assertIsNone(base.grad);self.assertTrue(torch.equal(base,frozen));self.assertGreater(b.abs().sum().item(),0)
        import copy
        saved={'a':a.detach().clone(),'b':b.detach().clone(),'optimizer':copy.deepcopy(optimizer.state_dict())}
        step(a,b,optimizer);expected=(a.detach().clone(),b.detach().clone())
        resumed_a=torch.nn.Parameter(saved['a']);resumed_b=torch.nn.Parameter(saved['b'])
        resumed=torch.optim.AdamW([resumed_a,resumed_b],lr=.01);resumed.load_state_dict(saved['optimizer'])
        step(resumed_a,resumed_b,resumed)
        self.assertTrue(torch.equal(expected[0],resumed_a));self.assertTrue(torch.equal(expected[1],resumed_b))


if __name__=='__main__':unittest.main()
