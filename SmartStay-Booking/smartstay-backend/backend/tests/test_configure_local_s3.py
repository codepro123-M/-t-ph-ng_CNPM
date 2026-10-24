import importlib.util
from pathlib import Path

import pytest


path = Path(__file__).resolve().parents[2] / "scripts" / "configure_local_s3.py"
spec = importlib.util.spec_from_file_location("configure_local_s3", path)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.s3.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text(
        "APP_ENV=development\nJWT_SECRET=preserve-this-value\n"
        "MONGODB_URI=mongodb://my-existing-host\nMEDIA_BACKEND=local\n"
    )
    return tmp_path


def test_helper_preserves_jwt_and_database_and_is_idempotent(project):
    helper.configure(project)
    first = (project / ".env").read_text()
    values = helper.read_values(first)
    assert "JWT_SECRET=preserve-this-value" in first
    assert "MONGODB_URI=mongodb://my-existing-host" in first
    assert values["MEDIA_BACKEND"] == "s3"
    assert values["S3_ENDPOINT_URL"] == "http://s3:9000"
    assert len(values["S3_SECRET_KEY"]) >= 32
    assert values["COMPOSE_PATH_SEPARATOR"] == ","
    helper.configure(project)
    assert (project / ".env").read_text() == first


@pytest.mark.parametrize(
    "line",
    [
        "APP_ENV=production",
        "COMPOSE_FILE=custom.yml",
        "S3_ENDPOINT_URL=https://external.example",
        "S3_ACCESS_KEY=without-secret",
    ],
)
def test_helper_refuses_to_replace_external_or_incomplete_configuration(project, line):
    env = project / ".env"
    env.write_text(env.read_text() + line + "\n")
    before = env.read_bytes()
    with pytest.raises(ValueError):
        helper.configure(project)
    assert env.read_bytes() == before
