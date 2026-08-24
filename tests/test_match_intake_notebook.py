import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "pipeline" / "notebooks" / "2026_match_intake.ipynb"
PUBLISH_NOTEBOOK = ROOT / "pipeline" / "notebooks" / "2026_match_publish.ipynb"


class MatchIntakeNotebookTests(unittest.TestCase):
    def test_notebook_is_valid_and_all_code_cells_compile(self):
        document = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

        self.assertEqual(document["nbformat"], 4)
        code_cells = [cell for cell in document["cells"] if cell["cell_type"] == "code"]
        self.assertGreaterEqual(len(code_cells), 5)
        for index, cell in enumerate(code_cells):
            compile("".join(cell["source"]), f"notebook-cell-{index}", "exec")

    def test_notebook_has_review_gate_and_no_production_credentials(self):
        document = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        code = "\n".join(
            "".join(cell["source"])
            for cell in document["cells"]
            if cell["cell_type"] == "code"
        )

        self.assertIn("CREATE_REVIEW_BUNDLE = False", code)
        self.assertIn("--dry-run", code)
        self.assertNotIn("SUPABASE_SERVICE_KEY", code)
        self.assertNotIn("write_db", code)
        self.assertNotIn("load_match", code)

    def test_notebook_handles_empty_source_summary(self):
        document = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        code = "\n".join(
            "".join(cell["source"])
            for cell in document["cells"]
            if cell["cell_type"] == "code"
        )

        self.assertIn("report.get('source_manifest') or []", code)
        self.assertIn("(report.get('team_event_summary') or {}).get('unmapped_labels')", code)

    def test_publish_notebook_compiles_and_gates_staff_events_before_scores(self):
        document = json.loads(PUBLISH_NOTEBOOK.read_text(encoding="utf-8"))
        code_cells = [cell for cell in document["cells"] if cell["cell_type"] == "code"]
        for index, cell in enumerate(code_cells):
            compile("".join(cell["source"]), f"publish-notebook-cell-{index}", "exec")
        code = "\n".join("".join(cell["source"]) for cell in code_cells)

        self.assertIn("APPLY_STAFF_EVENTS = False", code)
        self.assertIn("STAFF_CONFIRMATION", code)
        self.assertIn("prepare_staff_events.py", code)
        self.assertIn("load_staff_events.py", code)
        self.assertLess(code.index("APPLY_STAFF_EVENTS = False"), code.index("PUBLISH_COUG_SCORES = False"))
        self.assertIn("apply the supplied staff events before previewing final scores", code)


if __name__ == "__main__":
    unittest.main()
