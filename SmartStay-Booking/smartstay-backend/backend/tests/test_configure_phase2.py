import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts" / "configure_phase2.py"
spec = importlib.util.spec_from_file_location("configure_phase2", PATH)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def project(tmp_path, text):
    (tmp_path / ".env").write_text(text, encoding="utf-8")
    (tmp_path / "docker-compose.https.yml").write_text("services: {}", encoding="utf-8")
    return tmp_path


def test_helper_preserves_keys_s3_and_is_idempotent(tmp_path):
    root = project(
        tmp_path,
        "APP_ENV=development\nJWT_SECRET="
        + "old-strong-key" * 4
        + "\nMEDIA_BACKEND=s3\nS3_ACCESS_KEY=keep-this\nS3_SECRET_KEY=keep-that\nCOMPOSE_FILE=docker-compose.yml,docker-compose.s3.yml\nCOMPOSE_PATH_SEPARATOR=,\n",
    )
    helper.configure(root)
    text = (root / ".env").read_text()
    values = helper.read_values(text)
    assert values["JWT_SECRET"] == "old-strong-key" * 4
    assert (
        len(
            {
                values[key]
                for key in ("JWT_SECRET", "REFRESH_TOKEN_SECRET", "SECRET_KEY")
            }
        )
        == 3
    )
    assert all(
        len(values[key]) >= 32
        for key in ("JWT_SECRET", "REFRESH_TOKEN_SECRET", "SECRET_KEY")
    )
    assert (
        values["COMPOSE_FILE"]
        == "docker-compose.yml,docker-compose.s3.yml,docker-compose.https.yml"
    )
    assert "S3_ACCESS_KEY=keep-this" in text and "S3_SECRET_KEY=keep-that" in text
    helper.configure(root)
    assert (root / ".env").read_text() == text


@pytest.mark.parametrize(
    "text",
    [
        "APP_ENV=production\n",
        "APP_ENV=development\nSECRET_KEY=short-key\n",
        "COMPOSE_FILE=custom.yml\n",
        "SUPERADMIN_PASSWORD=short\n",
    ],
)
def test_helper_does_not_modify_unsupported_configuration(tmp_path, text):
    root = project(tmp_path, text)
    with pytest.raises(ValueError):
        helper.configure(root)
    assert (root / ".env").read_text() == text


def test_helper_preserves_existing_password_with_spaces(tmp_path):
    root = project(
        tmp_path,
        "SUPERADMIN_USERNAME=existing_admin\nSUPERADMIN_PASSWORD='an existing password with spaces'\n",
    )
    helper.configure(root)
    values = helper.read_values((root / ".env").read_text())
    assert values["SUPERADMIN_USERNAME"] == "existing_admin"
    assert values["SUPERADMIN_PASSWORD"] == "an existing password with spaces"
