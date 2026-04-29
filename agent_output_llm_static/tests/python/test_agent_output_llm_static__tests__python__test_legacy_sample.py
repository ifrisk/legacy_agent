import importlib.util
from pathlib import Path
import unittest


TARGET_FILE = Path(r"C:\Users\Administrator\Desktop\legacy_agent\examples\agent_output_llm_static\tests\python\test_legacy_sample.py")


def _load_target_module(file_path: Path):
    spec = importlib.util.spec_from_file_location("legacy_target_module", file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Test_Load_Target_Module(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_target_module(TARGET_FILE)
    def test__load_target_module_default(self):
        with self.assertRaises(RuntimeError):
            self.module._load_target_module(**{'file_path': None})




if __name__ == "__main__":
    unittest.main()
