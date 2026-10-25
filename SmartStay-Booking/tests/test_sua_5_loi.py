import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location(
    "fullstack_repair", Path(__file__).resolve().parents[1] / "AP_DUNG_SUA_5_LOI.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bundle, self.target = root / "bundle", root / "old"
        self.backend, self.frontend = (
            self.target / "smartstay-backend",
            self.target / "quickstay-frontend",
        )
        for folder in [
            self.bundle / "smartstay-backend/backend/app",
            self.bundle / "quickstay-frontend/src",
            self.backend / "backend/app",
            self.frontend / "src",
        ]:
            folder.mkdir(parents=True)
        (self.backend / "docker-compose.yml").write_text("services: {}")
        (self.backend / "backend/app/main.py").write_text("old backend")
        (self.backend / ".env").write_text(
            "APP_ENV=development\nJWT_SECRET=keep-private\nTRUSTED_ORIGINS=https://existing.example\n"
        )
        (self.frontend / "package.json").write_text("{}")
        (self.frontend / "src/App.jsx").write_text("old frontend")
        (self.frontend / ".env.local").write_text(
            "VITE_SMARTSTAY_API_BASE=https://existing.example"
        )
        self.entries = {
            "files": [("backend/app/main.py", "new backend")],
            "frontend_files": [
                ("src/App.jsx", "new frontend"),
                ("src/AudioGuide.jsx", "new audio"),
            ],
            "root_files": [("HUONG_DAN_SUA_5_LOI.md", "new guide")],
        }
        self.manifest = {"version": "repair-test"}
        for section, entries in self.entries.items():
            self.manifest[section] = []
            for relative, text in entries:
                source = self.bundle / module.SECTIONS[section] / relative
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(text)
                self.manifest[section].append(
                    {
                        "path": relative,
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                )
        self.save_manifest()

    def save_manifest(self):
        (self.bundle / "UPDATE_MANIFEST.json").write_text(json.dumps(self.manifest))

    def apply(self, **kwargs):
        return module.apply_repair(
            self.bundle, self.backend, self.frontend, project=self.target, **kwargs
        )

    def test_fullstack_update_backs_up_both_sides_and_preserves_local_settings(self):
        result = self.apply()
        self.assertEqual(
            (self.backend / "backend/app/main.py").read_text(), "new backend"
        )
        self.assertEqual((self.frontend / "src/App.jsx").read_text(), "new frontend")
        self.assertEqual(
            (result["backup"] / "smartstay-backend/backend/app/main.py").read_text(),
            "old backend",
        )
        self.assertEqual(
            (result["backup"] / "quickstay-frontend/src/App.jsx").read_text(),
            "old frontend",
        )
        self.assertIn("JWT_SECRET=keep-private", (self.backend / ".env").read_text())
        self.assertIn("http://localhost:4173", (self.backend / ".env").read_text())
        self.assertEqual(
            (self.frontend / ".env.local").read_text(),
            "VITE_SMARTSTAY_API_BASE=https://existing.example",
        )

    def test_tampered_frontend_is_rejected_before_backend_changes(self):
        (self.bundle / "quickstay-frontend/src/App.jsx").write_text("tampered")
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(
            (self.backend / "backend/app/main.py").read_text(), "old backend"
        )
        self.assertFalse((self.target / "repair-backups").exists())

    def test_copy_failure_rolls_back_every_replaced_file(self):
        copy = module.atomic_copy

        def fail_audio(source, destination):
            if destination.name == "AudioGuide.jsx":
                raise OSError("simulated write failure")
            copy(source, destination)

        with patch.object(module, "atomic_copy", side_effect=fail_audio):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(
            (self.backend / "backend/app/main.py").read_text(), "old backend"
        )
        self.assertEqual((self.frontend / "src/App.jsx").read_text(), "old frontend")
        self.assertFalse((self.frontend / "src/AudioGuide.jsx").exists())

    def test_dry_run_makes_no_changes(self):
        self.assertIsNone(self.apply(dry_run=True)["backup"])
        self.assertEqual((self.frontend / "src/App.jsx").read_text(), "old frontend")
        self.assertFalse((self.target / "repair-backups").exists())

    def test_destination_symlink_cannot_escape_project(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.frontend / "src/App.jsx").unlink()
        (self.frontend / "src").rmdir()
        (self.frontend / "src").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(
            (self.backend / "backend/app/main.py").read_text(), "old backend"
        )
        self.assertEqual(list(outside.iterdir()), [])

    def test_production_environment_is_preserved_exactly(self):
        original = "APP_ENV=production\nTRUSTED_ORIGINS=https://prod.example\nJWT_SECRET=private\n"
        (self.backend / ".env").write_text(original)
        self.apply()
        self.assertEqual((self.backend / ".env").read_text(), original)

    def test_source_folder_symlink_is_rejected(self):
        source = self.bundle / "quickstay-frontend"
        outside = Path(self.temp.name) / "external-source"
        source.rename(outside)
        source.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(
            (self.backend / "backend/app/main.py").read_text(), "old backend"
        )


if __name__ == "__main__":
    unittest.main()
