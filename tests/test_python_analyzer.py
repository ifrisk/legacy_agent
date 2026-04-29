import unittest
from pathlib import Path

from legacy_agent.analyzers.python_analyzer import analyze_python_file


class PythonAnalyzerTest(unittest.TestCase):
    def test_python_analyzer_extracts_functions(self):
        analysis = analyze_python_file(Path("examples/legacy_sample.py").resolve())
        names = [function.name for function in analysis.functions]
        self.assertIn("normalize_score", names)
        self.assertIn("classify_age", names)


if __name__ == "__main__":
    unittest.main()
