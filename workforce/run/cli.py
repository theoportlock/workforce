from workforce import utils
from workforce.server import start_server
from .client import Runner

def main(url_or_path, nodes=None, wrapper="{}"):
	"""
	CLI entry point for the runner.
	Accepts either a URL or a filesystem path and resolves it to a workspace URL.
	Ensures server is running on fixed port 5000.
	"""
	# Compute workspace_id from the path to match server's routing
	wf_path = url_or_path if not url_or_path.startswith(('http://', 'https://')) else utils.default_workfile()
	abs_path = utils.get_absolute_path(wf_path)
	workspace_id = utils.compute_workspace_id(abs_path)
	
	# Auto-start server if not running
	start_server(background=True)
	
	# Build workspace URL
	base_url = utils.get_workspace_url(workspace_id)
	
	runner = Runner(base_url, workspace_id=workspace_id, workfile_path=wf_path, wrapper=wrapper)
	runner.start(initial_nodes=nodes)
