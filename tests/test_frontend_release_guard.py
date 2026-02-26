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


def test_frontend_entrypoint_contains_executable_bundle_code():
    """Guard against shipping placeholder frontend entrypoints."""

    app_js_path = Path("workforce/web/static/app.js")
    assert app_js_path.exists(), "Missing workforce/web/static/app.js release loader/entrypoint"

    app_js = app_js_path.read_text(encoding="utf-8")
    assert "Built frontend assets are copied here before release" not in app_js
    assert "fetch(" in app_js or "document." in app_js or "window." in app_js, (
        "workforce/web/static/app.js appears to be a placeholder; expected executable code"
    )

    manifest_path = Path("workforce/web/static/assets/manifest.json")
    assert manifest_path.exists(), "Missing frontend assets manifest"
