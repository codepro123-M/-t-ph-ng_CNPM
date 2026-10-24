import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("booking_update", Path(__file__).resolve().parents[1] / "AP_DUNG_DAT_PHONG.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bundle, self.target = root / "bundle", root / "project"
        for directory in (self.bundle / "smartstay-backend", self.target):
            (directory / "backend/app").mkdir(parents=True)
            (directory / "docker-compose.yml").write_text("services: {}")
        self.file = self.bundle / "smartstay-backend/backend/app/main.py"
        self.file.write_text("# new backend")
        (self.target / "backend/app/main.py").write_text("# old backend")
        (self.target / ".env").write_text("APP_ENV=development\nJWT_SECRET=keep-private-value\nTRUSTED_ORIGINS=https://existing.example\nS3_SECRET_KEY=keep-s3-private\n")
        (self.bundle / "UPDATE_MANIFEST.json").write_text(json.dumps({"files": [{"path":"backend/app/main.py","sha256":hashlib.sha256(self.file.read_bytes()).hexdigest()}]}))

    def test_update_backs_up_code_and_preserves_secrets_runtime_and_existing_origins(self):
        (self.target / "backend/runtime_data").mkdir()
        (self.target / "backend/runtime_data/keep.txt").write_text("existing media")
        result = module.apply_update(self.bundle, self.target)
        self.assertEqual((self.target / "backend/app/main.py").read_text(), "# new backend")
        self.assertEqual((result["backup"] / "backend/app/main.py").read_text(), "# old backend")
        values = module.env_values((self.target / ".env").read_text())
        self.assertEqual(values["JWT_SECRET"], "keep-private-value")
        self.assertEqual(values["S3_SECRET_KEY"], "keep-s3-private")
        self.assertEqual(values["TRUSTED_ORIGINS"], "https://existing.example,http://localhost:4173,http://127.0.0.1:4173")
        self.assertEqual((self.target / "backend/runtime_data/keep.txt").read_text(), "existing media")

    def test_bad_hash_or_escape_is_rejected_before_modifying_anything(self):
        self.file.write_text("tampered")
        with self.assertRaises(ValueError):
            module.apply_update(self.bundle, self.target)
        self.assertFalse((self.target / "booking-backups").exists())
        self.assertEqual((self.target / "backend/app/main.py").read_text(), "# old backend")

    def test_production_origins_are_not_changed_and_development_update_is_idempotent(self):
        text = "APP_ENV=production\nTRUSTED_ORIGINS=https://prod.example\nJWT_SECRET=keep\n"
        self.assertEqual(module.local_origins(text), text)
        dev = (self.target / ".env").read_text()
        once = module.local_origins(dev)
        self.assertEqual(module.local_origins(once), once)

    def test_symlink_outside_project_is_rejected(self):
        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("must stay")
        dest = self.target / "backend/app/main.py"
        dest.unlink()
        dest.symlink_to(outside)
        with self.assertRaises(ValueError):
            module.apply_update(self.bundle, self.target)
        self.assertEqual(outside.read_text(), "must stay")


if __name__ == "__main__":
    unittest.main()
