import subprocess
import zipfile
from pathlib import Path


def test_source_tree_contains_static_index_html():
    assert Path("workforce/web/static/index.html").is_file()


def test_wheel_contains_static_index_html(tmp_path):
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
