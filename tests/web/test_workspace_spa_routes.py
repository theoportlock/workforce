import re

from flask import Flask

from workforce.server import routes


def _extract_paths(html: str):
    return re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html)


def _make_test_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    routes.register_routes(app)
    return app


def test_workspace_shell_returns_html():
    app = _make_test_app()
    workspace_id = "ws_123"

    with app.test_client() as client:
        response = client.get(f"/workspace/{workspace_id}")

    assert response.status_code == 200
    assert "text/html" in response.content_type
    body = response.get_data(as_text=True)
    assert "<base href=\"/workspace/ws_123/\">" in body
    assert "<div id=\"app\"></div>" in body


def test_workspace_shell_referenced_assets_return_200():
    app = _make_test_app()

    with app.test_client() as client:
        shell = client.get("/workspace/ws_abc")
        html = shell.get_data(as_text=True)
        paths = _extract_paths(html)

        # app.js is referenced directly from the shell
        app_js_path = next(path for path in paths if path.endswith("app.js"))
        resolved_app_js = f"/workspace/ws_abc/{app_js_path.lstrip('./')}"
        app_js = client.get(resolved_app_js)
        assert app_js.status_code == 200

        # Manifest and built JS/CSS are loaded by app.js and must resolve from workspace mount
        manifest = client.get("/workspace/ws_abc/assets/manifest.json")
        assert manifest.status_code == 200

        manifest_json = manifest.get_json()
        assert manifest_json and "entry" in manifest_json

        entry = manifest_json["entry"]
        js_response = client.get(f"/workspace/ws_abc/{entry['js']}")
        css_response = client.get(f"/workspace/ws_abc/{entry['css']}")

        assert js_response.status_code == 200
        assert css_response.status_code == 200


def test_missing_assets_404_and_spa_shell_still_delivered():
    app = _make_test_app()

    with app.test_client() as client:
        missing = client.get("/workspace/ws_missing/assets/does-not-exist.js")
        assert missing.status_code == 404

        shell = client.get("/workspace/ws_missing")
        assert shell.status_code == 200
        assert "text/html" in shell.content_type
