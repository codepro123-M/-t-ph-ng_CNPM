"""Protect local secrets, existing source and paths during update installation."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "apply_smartstay_update", ROOT / "AP_DUNG_BAN_SUA.py"
)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


def source_and_project(tmp_path):
    source, project = tmp_path / "update", tmp_path / "project"
    for root in (source, project):
        (root / "backend/app").mkdir(parents=True)
        (root / "backend/app/main.py").write_text(root.name)
        (root / "docker-compose.yml").write_text("services: {}")
        (root / "scripts").mkdir()
    (source / "scripts/smoke_phase3.py").write_text("# updated smoke")
    return source, project


def test_update_keeps_env_git_and_runtime_and_backs_up_original_code(tmp_path):
    source, project = source_and_project(tmp_path)
    (source / ".env").write_text("NEVER_COPY=1")
    (project / ".env").write_text("KEEP_LOCAL=1")
    (project / ".git").mkdir()
    (project / ".git/config").write_text("local git metadata")
    (project / "backend/runtime_data").mkdir()
    (project / "backend/runtime_data/keep.txt").write_text("local data")
    result = updater.apply_update(source, project)
    assert (project / "backend/app/main.py").read_text() == "update"
    assert (Path(result["backup"]) / "backend/app/main.py").read_text() == "project"
    assert (project / ".env").read_text() == "KEEP_LOCAL=1"
    assert (project / ".git/config").read_text() == "local git metadata"
    assert (project / "backend/runtime_data/keep.txt").read_text() == "local data"
    assert (project / "scripts/smoke_phase3.py").is_file()
    assert not (Path(result["backup"]) / ".env").exists()


def test_update_rejects_symlink_escape_before_any_changes(tmp_path):
    source, project = source_and_project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / "scripts").rmdir()
    try:
        (project / "scripts").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable")
    with pytest.raises(ValueError, match="outside"):
        updater.apply_update(source, project)
    assert (project / "backend/app/main.py").read_text() == "project"
    assert list(outside.iterdir()) == []


def test_update_dry_run_has_no_writes(tmp_path):
    source, project = source_and_project(tmp_path)
    result = updater.apply_update(source, project, dry_run=True)
    assert result["files"] >= 3 and result["backup"] is None
    assert (project / "backend/app/main.py").read_text() == "project"
    assert not (project / "scripts/smoke_phase3.py").exists()
    assert not list(tmp_path.glob("smart-stay-code-backup-*"))
