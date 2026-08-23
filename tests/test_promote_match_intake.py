import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from promote_match_intake import (  # noqa: E402
    PromotionError,
    apply_candidates,
    build_candidates,
    load_json_object,
    sha256_file,
    storage_path_for,
    validate_approval,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.operation = "select"
        self.payload = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def upsert(self, payload, on_conflict):
        self.operation = "upsert"
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.operation == "upsert":
            self.client.upserts.append((self.name, self.on_conflict, self.payload))
            return FakeResponse([{"id": f"row-{len(self.client.upserts)}", **self.payload}])
        return FakeResponse([])


class FakeBucket:
    def __init__(self, client, bucket):
        self.client = client
        self.bucket = bucket

    def upload(self, *, path, file, file_options):
        self.client.uploads.append((self.bucket, path, file.read(), file_options))


class FakeStorage:
    def __init__(self, client):
        self.client = client

    def from_(self, bucket):
        return FakeBucket(self.client, bucket)


class FakeClient:
    def __init__(self):
        self.uploads = []
        self.upserts = []
        self.storage = FakeStorage(self)

    def table(self, name):
        return FakeTable(self, name)


class MatchPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "00_source"
        self.bundle = self.root / "20_generated"
        (self.source / "wyscout").mkdir(parents=True)
        self.bundle.mkdir()

        self.team_a = self.source / "wyscout" / "download.xml"
        self.team_b = self.source / "wyscout" / "download copy.xml"
        self.team_a.write_text("<root>A</root>", encoding="utf-8")
        self.team_b.write_text("<root>B</root>", encoding="utf-8")
        self.slug = "2026-08-20_davidson"
        self.report_path = self.bundle / f"{self.slug}_intake_report.json"
        self.report = {
            "slug": self.slug,
            "season": "2026",
            "analytics": {"ready": True},
            "scoring": {"ready": False},
            "minutes": {"ready": False},
            "validation": {"status": "ready_for_staff_review"},
            "source_manifest": [
                {
                    "relative_path": "wyscout/download.xml",
                    "extension": ".xml",
                    "size_bytes": self.team_a.stat().st_size,
                    "sha256": sha256_file(self.team_a),
                },
                {
                    "relative_path": "wyscout/download copy.xml",
                    "extension": ".xml",
                    "size_bytes": self.team_b.stat().st_size,
                    "sha256": sha256_file(self.team_b),
                },
            ],
            "files": [
                {"relative_path": "wyscout/download.xml", "kind": "team_event_xml", "team": "Charleston Cougars"},
                {"relative_path": "wyscout/download copy.xml", "kind": "team_event_xml", "team": "Davidson"},
            ],
        }
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        (self.bundle / f"{self.slug}_canonical_team_events.csv").write_text("event\nshot\n", encoding="utf-8")
        (self.bundle / f"{self.slug}_match_flow.json").write_text("{}", encoding="utf-8")
        (self.bundle / f"{self.slug}_metadata.json").write_text("{}", encoding="utf-8")
        (self.bundle / f"{self.slug}_validation_report.md").write_text("review", encoding="utf-8")

        self.approval = {
            "schema_version": 1,
            "match_slug": self.slug,
            "season": "2026",
            "intake_report_sha256": sha256_file(self.report_path),
            "reviewed_by": "Staff Reviewer",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "approvals": {
                "source_archive": True,
                "match_analytics": True,
                "coug_scoring": False,
            },
            "notes": "Counts checked against Wyscout.",
        }
        self.approval_path = self.bundle / f"{self.slug}_approval.json"
        self.approval_path.write_text(json.dumps(self.approval), encoding="utf-8")

    def test_storage_path_is_content_addressed_and_safe(self):
        path = storage_path_for(
            prefix="cofc", season="2026", slug=self.slug, area="raw",
            source_system="wyscout", source_type="team_events", digest="a" * 64,
            filename="UNCW team events (FINAL).xml",
        )
        self.assertEqual(
            path,
            "cofc/2026/2026-08-20_davidson/raw/wyscout/team_events/aaaaaaaaaaaa_UNCW_team_events_FINAL_.xml",
        )

    def test_two_same_type_files_do_not_collide(self):
        approvals = validate_approval(self.approval, self.report, self.report_path)
        candidates = build_candidates(self.source, self.bundle, self.report, approvals, prefix="cofc")
        team_files = [row for row in candidates if row.source_type == "team_events"]
        self.assertEqual(len(team_files), 2)
        self.assertEqual(len({row.storage_path for row in team_files}), 2)
        self.assertEqual({row.metadata["detected_team"] for row in team_files}, {"Charleston Cougars", "Davidson"})

    def test_changed_source_is_rejected(self):
        self.team_a.write_text("<root>changed</root>", encoding="utf-8")
        approvals = validate_approval(self.approval, self.report, self.report_path)
        with self.assertRaisesRegex(PromotionError, "changed after intake"):
            build_candidates(self.source, self.bundle, self.report, approvals, prefix="cofc")

    def test_changed_report_invalidates_approval(self):
        self.report["metadata"] = {"opponent": "Different Team"}
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        with self.assertRaisesRegex(PromotionError, "changed after approval"):
            validate_approval(self.approval, self.report, self.report_path)

    def test_unready_product_cannot_be_approved(self):
        self.approval["approvals"]["coug_scoring"] = True
        with self.assertRaisesRegex(PromotionError, "not ready"):
            validate_approval(self.approval, self.report, self.report_path)

    def test_coug_scoring_requires_official_minutes(self):
        self.report["scoring"] = {"ready": True}
        self.approval["approvals"]["coug_scoring"] = True
        with self.assertRaisesRegex(PromotionError, "official minutes"):
            validate_approval(self.approval, self.report, self.report_path)

    def test_dry_run_needs_no_supabase_credentials(self):
        script = INGESTION_DIR / "promote_match_intake.py"
        result = subprocess.run(
            [
                sys.executable, str(script), "--source-dir", str(self.source),
                "--bundle-dir", str(self.bundle),
            ],
            check=True,
            capture_output=True,
            text=True,
            env={"PATH": str(Path(sys.executable).parent)},
        )
        self.assertIn("DRY RUN:", result.stdout)
        receipt = load_json_object(self.bundle / f"{self.slug}_promotion_receipt.json", "receipt")
        self.assertEqual(receipt["mode"], "dry_run")
        self.assertEqual(len(receipt["objects"]), 8)

    def test_approved_analytics_requires_both_outputs(self):
        (self.bundle / f"{self.slug}_match_flow.json").unlink()
        approvals = validate_approval(self.approval, self.report, self.report_path)
        with self.assertRaisesRegex(PromotionError, "match_flow.json"):
            build_candidates(self.source, self.bundle, self.report, approvals, prefix="cofc")

    def test_apply_uses_idempotent_storage_and_registry_keys(self):
        approvals = validate_approval(self.approval, self.report, self.report_path)
        candidates = build_candidates(self.source, self.bundle, self.report, approvals, prefix="cofc")
        client = FakeClient()

        first = apply_candidates(client, candidates, self.report, self.approval, "source-files")
        second = apply_candidates(client, candidates, self.report, self.approval, "source-files")

        self.assertEqual(len(first), len(candidates))
        self.assertEqual(len(second), len(candidates))
        first_paths = [row[1] for row in client.uploads[:len(candidates)]]
        second_paths = [row[1] for row in client.uploads[len(candidates):]]
        self.assertEqual(first_paths, second_paths)
        self.assertTrue(all(item[1] == "storage_bucket,storage_path" for item in client.upserts))
        self.assertTrue(all(item[2]["upload_status"] == "uploaded" for item in client.upserts))


if __name__ == "__main__":
    unittest.main()
