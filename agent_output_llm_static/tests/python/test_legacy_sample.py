import importlib.util
from pathlib import Path
import unittest


TARGET_FILE = Path(r"C:\Users\Administrator\Desktop\legacy_agent\examples\legacy_sample.py")


def _load_target_module(file_path: Path):
    spec = importlib.util.spec_from_file_location("legacy_target_module", file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class TestNormalize_Score(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_target_module(TARGET_FILE)
    def test_normalize_score_default(self):
        result = self.module.normalize_score(**{'score': 0})
        self.assertEqual(repr(result), '0')
    def test_normalize_score_score_0(self):
        result = self.module.normalize_score(**{'score': -1})
        self.assertEqual(repr(result), '0')
    def test_normalize_score_score_2(self):
        result = self.module.normalize_score(**{'score': 1})
        self.assertEqual(repr(result), '1')
    def test_normalize_score_score_3(self):
        result = self.module.normalize_score(**{'score': 99})
        self.assertEqual(repr(result), '99')


class TestClassify_Age(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_target_module(TARGET_FILE)
    def test_classify_age_default(self):
        result = self.module.classify_age(**{'age': 0})
        self.assertEqual(repr(result), "'minor'")
    def test_classify_age_age_0(self):
        with self.assertRaises(ValueError):
            self.module.classify_age(**{'age': -1})
    def test_classify_age_age_2(self):
        result = self.module.classify_age(**{'age': 1})
        self.assertEqual(repr(result), "'minor'")
    def test_classify_age_age_3(self):
        result = self.module.classify_age(**{'age': 17})
        self.assertEqual(repr(result), "'minor'")




if __name__ == "__main__":
    unittest.main()
