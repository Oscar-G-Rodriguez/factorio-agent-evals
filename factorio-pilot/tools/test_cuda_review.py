"""Review gates must fail closed when native code changes or evidence is missing."""
import json
import tempfile
import unittest
from pathlib import Path
from cuda_review import assert_review_current, native_inventory

class CudaReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'cuda').mkdir()
        for name in ('rmsnorm.cpp','rmsnorm.cu'):
            (self.root/'cuda'/name).write_text('// reviewed fixture\n')
        folder = self.root/'evidence/artifacts'
        folder.mkdir(parents=True)
        self.record = {'status':'static_review_complete','unresolved_launch_blockers':[],
                       'source_hashes':native_inventory(self.root),'sanitizer_status':'pending',
                       'required_correctness_cases':['zero','epsilon_underflow']}
        self.manifest = folder/'cuda-source-review.json'
        self.manifest.write_text(json.dumps(self.record))

    def test_current_review_allows_bounded_runtime(self):
        self.assertEqual(assert_review_current(root=self.root)['status'],'static_review_complete')

    def test_modified_added_and_removed_sources_are_blocked(self):
        for change in ('modified','added','removed'):
            with self.subTest(change=change):
                path = self.root/'cuda/rmsnorm.cu'
                path.write_text('// reviewed fixture\n')
                extra = self.root/'cuda/new.cu'
                if extra.exists(): extra.unlink()
                if change=='modified': path.write_text('// different\n')
                elif change=='added': extra.write_text('// new kernel\n')
                else: path.unlink()
                with self.assertRaisesRegex(RuntimeError,'fresh code review'):
                    assert_review_current(root=self.root)

    def test_missing_review_and_unresolved_blockers_are_rejected(self):
        self.record['unresolved_launch_blockers']=['out of bounds']
        self.manifest.write_text(json.dumps(self.record))
        with self.assertRaises(RuntimeError): assert_review_current(root=self.root)
        self.manifest.unlink()
        with self.assertRaises(RuntimeError): assert_review_current(root=self.root)

    def test_benchmark_requires_matching_complete_correctness(self):
        result_path = self.root/'checks.json'
        with self.assertRaises(RuntimeError):
            assert_review_current('benchmark',self.root,result_path)
        result = {'source_hashes':{n:self.record['source_hashes'][f'cuda/{n}'] for n in ('rmsnorm.cpp','rmsnorm.cu')},
                  'correctness_checks':[{'case':'zero','passed':True}]}
        result_path.write_text(json.dumps(result))
        with self.assertRaises(RuntimeError): assert_review_current('benchmark',self.root,result_path)
        result['correctness_checks'].append({'case':'epsilon_underflow','passed':True})
        result_path.write_text(json.dumps(result))
        assert_review_current('benchmark',self.root,result_path)
        result['source_hashes']['rmsnorm.cu']='stale'
        result_path.write_text(json.dumps(result))
        with self.assertRaises(RuntimeError): assert_review_current('benchmark',self.root,result_path)

if __name__ == '__main__': unittest.main()
