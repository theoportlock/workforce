import subprocess
import zipfile
from pathlib import Path


def test_source_tree_contains_static_index_html():
    assert Path("workforce/web/static/index.html").is_file()


def test_source_tree_contains_built_static_assets():
    static_root = Path("workforce/web/static")
    assert (static_root / "app.js").is_file()
    assert (static_root / "assets/manifest.json").is_file()

    manifest = (static_root / "assets/manifest.json").read_text(encoding="utf-8")
    assert "index-" in manifest


def test_wheel_contains_static_index_html_and_assets(tmp_path):
    cmd = [
        "python",
        "-m",
        "pip",
        "wheel",
        "--no-deps",
        "--wheel-dir",
        str(tmp_path),
        "--no-build-isolation",
        ".",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    wheels = list(tmp_path.glob("workforce-*.whl"))
    assert wheels, "expected wheel output"

    with zipfile.ZipFile(wheels[0]) as zf:
        members = set(zf.namelist())

    assert "workforce/web/static/index.html" in members
    assert "workforce/web/static/app.js" in members
    assert "workforce/web/static/assets/manifest.json" in members
    assert any(name.startswith("workforce/web/static/assets/index-") and name.endswith(".js") for name in members)
    assert any(name.startswith("workforce/web/static/assets/index-") and name.endswith(".css") for name in members)
