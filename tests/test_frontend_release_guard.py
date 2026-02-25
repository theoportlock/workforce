from pathlib import Path

from workforce.web.launcher import frontend_file


def test_frontend_index_is_present_for_release_builds():
    index_path = Path("workforce/web/static/index.html")
    assert index_path.exists(), (
        "Missing workforce/web/static/index.html. "
        "Build frontend assets and copy them into workforce/web/static before release."
    )


def test_frontend_loader_resolves_packaged_file_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    index_path = Path(frontend_file("index.html"))

    assert index_path.exists()
    assert index_path.name == "index.html"
