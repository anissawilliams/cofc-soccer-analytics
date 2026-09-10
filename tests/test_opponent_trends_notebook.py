import ast
import json
import unittest
from pathlib import Path


NOTEBOOK = Path("pipeline/notebooks/2026_opponent_trends.ipynb")


class OpponentTrendsNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.code = "\n".join(
            "".join(cell.get("source", []))
            for cell in cls.notebook["cells"]
            if cell.get("cell_type") == "code"
        )

    def test_notebook_is_valid_and_code_cells_compile(self):
        self.assertEqual(self.notebook["nbformat"], 4)
        for cell in self.notebook["cells"]:
            if cell.get("cell_type") == "code":
                ast.parse("".join(cell.get("source", [])))

    def test_notebook_has_leakage_and_reconciliation_guards(self):
        self.assertIn("SCOUTING_DATE", self.code)
        self.assertIn("load_opponent_history(input_paths, OPPONENT_NAME, SCOUTING_DATE)", self.code)
        self.assertIn("No supported Wyscout Match Report PDFs", self.code)
        self.assertIn("'pypdf>=5.0.0'", self.code)

    def test_notebook_exports_evidence_not_automated_tactics(self):
        self.assertIn("opponent_match_history.csv", self.code)
        self.assertIn("recent_form_summary.json", self.code)
        self.assertIn("evidence_brief.md", self.code)
        markdown = "\n".join(
            "".join(cell.get("source", []))
            for cell in self.notebook["cells"]
            if cell.get("cell_type") == "markdown"
        )
        self.assertIn("coaches remain responsible for tactical interpretation", markdown)


if __name__ == "__main__":
    unittest.main()
