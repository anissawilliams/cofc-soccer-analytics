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

    def test_publish_notebook_is_single_run_with_one_final_confirmation(self):
        document = json.loads(PUBLISH_NOTEBOOK.read_text(encoding="utf-8"))
        code_cells = [cell for cell in document["cells"] if cell["cell_type"] == "code"]
        for index, cell in enumerate(code_cells):
            compile("".join(cell["source"]), f"publish-notebook-cell-{index}", "exec")
        code = "\n".join("".join(cell["source"]) for cell in code_cells)

        self.assertIn("prepare_staff_events.py", code)
        self.assertIn("load_staff_events.py", code)
        self.assertIn("promote_match_intake.py", code)
        self.assertIn("publish_event_derived_coug_scores.py", code)
        self.assertEqual(code.count("input("), 1)
        self.assertIn("expected = f'PUBLISH {MATCH_SLUG}'", code)
        self.assertIn("PUBLISHED AND VERIFIED", code)
        self.assertIn("prepare_match_intake.py", code)
        self.assertIn("Inspect source files and refresh intake readiness", code)
        self.assertLess(
            code.index("display(Markdown(VALIDATION_PATH.read_text"),
            code.index("Publication stopped after intake review"),
        )
        self.assertNotIn("APPLY_EVIDENCE =", code)
        self.assertNotIn("APPLY_STAFF_EVENTS =", code)
        self.assertNotIn("APPLY_ARCHIVE =", code)
        self.assertNotIn("PUBLISH_COUG_SCORES =", code)


if __name__ == "__main__":
    unittest.main()
