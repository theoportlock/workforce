from workforce import utils
from .client import Runner

def main(url_or_path, nodes=None, wrapper="{}"):
	"""
	CLI entry point for the runner.
	Accepts either a URL or a filesystem path and resolves it to a base URL.
	"""
	base_url = utils.resolve_target(url_or_path)
	runner = Runner(base_url, wrapper)
	runner.start(initial_nodes=nodes)
