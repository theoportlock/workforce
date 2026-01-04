import os
import tempfile

from workforce.utils import ensure_workfile


def test_ensure_workfile_with_explicit_path(tmp_path):
    target = tmp_path / "custom.wf.graphml"
    result = ensure_workfile(str(target))
    assert os.path.abspath(target) == result


def test_ensure_workfile_uses_default_workfile(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    default_path = tmp_path / "Workfile"
    default_path.write_text("")

    result = ensure_workfile()

    assert result == str(default_path.resolve())


def test_ensure_workfile_creates_temp_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = ensure_workfile(None)

    assert result.startswith(tempfile.gettempdir())
    basename = os.path.basename(result)
    assert basename.startswith("workforce_tmp_")
    assert basename.endswith(".wf.graphml")
    assert not os.path.exists(result)
