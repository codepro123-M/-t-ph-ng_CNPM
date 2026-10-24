import pytest

from app.core.runtime_storage import resolve_safe_path


def test_safe_path_accepts_nested_files(tmp_path):
    assert resolve_safe_path(tmp_path, "audio/test.mp3") == tmp_path / "audio/test.mp3"


@pytest.mark.parametrize("relative", ["../outside/secret", "../audio-private/secret"])
def test_safe_path_rejects_traversal_and_sibling_prefix(tmp_path, relative):
    base = tmp_path / "audio"
    base.mkdir()
    with pytest.raises(ValueError, match="Path traversal"):
        resolve_safe_path(base, relative)


def test_safe_path_rejects_symlink_escape(tmp_path):
    base = tmp_path / "media"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    try:
        (base / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("This system does not permit creating symbolic links.")
    with pytest.raises(ValueError, match="Path traversal"):
        resolve_safe_path(base, "link/secret")
