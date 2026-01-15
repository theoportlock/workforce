from workforce import utils
from .client import Runner


def main(url_or_path, nodes=None, wrapper="{}", server_url: str | None = None):
	"""
	CLI entry point for the runner.
	Accepts either a URL or a filesystem path and resolves it to a workspace URL.
	"""
	parsed = utils.parse_workspace_url(url_or_path) if url_or_path else None

	if parsed:
		server_url, workspace_id = parsed
		base_url = f"{server_url}/workspace/{workspace_id}"
		wf_path = f"<remote:{workspace_id}>"
	else:
		wf_path = utils.ensure_workfile(url_or_path)
		resolved_server = utils.resolve_server(server_url=server_url)
		registration = utils.register_workspace(resolved_server, wf_path)
		workspace_id = registration.get("workspace_id") or utils.compute_workspace_id(wf_path)
		base_url = registration.get("url") or f"{resolved_server}/workspace/{workspace_id}"

	runner = Runner(base_url, workspace_id=workspace_id, workfile_path=wf_path, wrapper=wrapper)
	runner.start(initial_nodes=nodes)
