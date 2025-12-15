import subprocess
import logging
from workforce import edit, utils

log = logging.getLogger(__name__)

def execute_node_on_server(ctx, node_id, label):
    """
    Execute node command on server; uses ctx.enqueue to record status/log updates.
    """
    try:
        # mark running
        ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "running")

        G = edit.load_graph(ctx.path)
        wrapper = G.graph.get('wrapper', '{}')

        if "{}" in wrapper:
            command = wrapper.replace("{}", utils.shell_quote_multiline(label))
        else:
            command = f"{wrapper} {utils.shell_quote_multiline(label)}"

        if not command.strip():
            ctx.enqueue(edit.save_node_log_in_graph, ctx.path, node_id, "[No command to run]")
            ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "ran")
            return

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        log_text = f"{stdout}\n{stderr}".strip()
        ctx.enqueue(edit.save_node_log_in_graph, ctx.path, node_id, log_text)

        if process.returncode == 0:
            ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "ran")
        else:
            ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "fail")
    except Exception:
        log.exception("Server-side execution failed for %s", node_id)
        ctx.enqueue(edit.edit_status_in_graph, ctx.path, "node", node_id, "fail")
