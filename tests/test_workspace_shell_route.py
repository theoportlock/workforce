from flask import Flask, g, request

from workforce.server import routes


def build_test_app(ctx_map=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    routes.register_routes(app)
    app.test_ctx_map = ctx_map or {}

    @app.before_request
    def _inject_test_ctx():
        if request.path.startswith("/workspace/"):
            parts = request.path.strip("/").split("/")
            if len(parts) >= 2:
                ws_id = parts[1]
                g.workspace_id = ws_id
                g.ctx = app.test_ctx_map.get(ws_id)

    return app


def test_workspace_shell_returns_html_for_known_workspace():
    workspace_id = "ws_abc12345"
    app = build_test_app(ctx_map={workspace_id: object()})

    with app.test_client() as client:
        response = client.get(f"/workspace/{workspace_id}")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert '<div id="app"></div>' in html or '<div id="root"></div>' in html
    assert f'window.__WORKSPACE_ID__ = "{workspace_id}"' in html
    assert f'window.__WORKSPACE_BASE_URL__ = "/workspace/{workspace_id}"' in html
    # Relative script URLs resolve incorrectly for /workspace/<id> without a trailing slash.
    assert f'<script src="/workspace/{workspace_id}/static/app.js"></script>' in html
    assert '<script src="./static/app.js"></script>' not in html


def test_workspace_shell_returns_404_for_invalid_workspace_id():
    app = build_test_app()

    with app.test_client() as client:
        response = client.get("/workspace/not-a-valid-id")

    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "Invalid workspace ID format"


def test_workspace_shell_returns_404_for_unknown_workspace():
    app = build_test_app()

    with app.test_client() as client:
        response = client.get("/workspace/ws_deadbeef")

    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "Workspace not found"


def test_workspace_static_asset_route_serves_loader_for_known_workspace():
    workspace_id = "ws_abc12345"
    app = build_test_app(ctx_map={workspace_id: object()})

    with app.test_client() as client:
        response = client.get(f"/workspace/{workspace_id}/static/app.js")

    assert response.status_code == 200
    assert response.mimetype in {"text/javascript", "application/javascript"}
    body = response.get_data(as_text=True)
    assert 'assets/manifest.json' in body


def test_workspace_static_asset_route_rejects_unknown_workspace():
    app = build_test_app()

    with app.test_client() as client:
        response = client.get('/workspace/ws_deadbeef/static/app.js')

    assert response.status_code == 404
    data = response.get_json()
    assert data['error'] == 'Workspace not found'
