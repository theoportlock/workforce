#!/usr/bin/env python
import socketio
import sys
import subprocess
import time
import requests


def get_prefix_suffix(graph, prefix='', suffix=''):
    graph_prefix = graph.get('graph', {}).get('prefix', '')
    graph_suffix = graph.get('graph', {}).get('suffix', '')
    use_prefix = prefix if prefix else graph_prefix
    use_suffix = suffix if suffix else graph_suffix
    return use_prefix, use_suffix


def shell_quote_multiline(script: str) -> str:
    return script.replace("'", "'\\''")


def run_tasks(url, prefix='', suffix=''):
    graph = requests.get(url).json()
    use_prefix, use_suffix = get_prefix_suffix(graph, prefix, suffix)

    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    run_nodes = [node for node, status in node_status.items() if status == 'run']
    node = run_nodes[0] if run_nodes else None

    if node:
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "running"})
        requests.post(f"{url}/run_node", json={"node_id": node, "prefix": use_prefix, "suffix": use_suffix})


def initialize_pipeline(url):
    graph = requests.get(url).json()
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}

    failed_nodes = [node for node, status in node_status.items() if status == 'fail']
    for node in failed_nodes:
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "run"})

    if not node_status:
        for node in graph['nodes']:
            node_id = node['id']
            indegree = sum(1 for e in graph['links'] if e['target'] == node_id)
            if indegree == 0:
                requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node_id, "status": "run"})


def schedule_tasks(url):
    graph = requests.get(url).json()
    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    ran_nodes = [node for node, status in node_status.items() if status == 'ran']

    for node in ran_nodes:
        for link in graph['links']:
            if link['source'] == node:
                requests.post(f"{url}/update_status", json={"element_type": "edge", "element_id": [link['source'], link['target']], "status": "to_run"})
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": None})

    edge_status = {(l['source'], l['target']): l.get('status', '') for l in graph['links']}

    ready_nodes = []
    for node in graph['nodes']:
        node_id = node['id']
        indegree = sum(1 for l in graph['links'] if l['target'] == node_id)
        if indegree > 0:
            incoming = [l for l in graph['links'] if l['target'] == node_id]
            if all(edge_status.get((l['source'], l['target'])) == 'to_run' for l in incoming):
                ready_nodes.append(node_id)

    # Activate ready nodes
    for node in ready_nodes:
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "run"})
        for l in graph['links']:
            if l['target'] == node:
                requests.post(f"{url}/update_status", json={"element_type": "edge", "element_id": [l['source'], l['target']], "status": None})

    node_status = {n['id']: n.get('status', '') for n in graph['nodes']}
    active_nodes = [node for node, status in node_status.items() if status in ('run', 'ran', 'running')]

    if not active_nodes:
        return 'complete'


def run_node(url, node, prefix='', suffix=''):
    graph = requests.get(url).json()
    use_prefix, use_suffix = get_prefix_suffix(graph, prefix, suffix)

    label = None
    for n in graph['nodes']:
        if n['id'] == node:
            label = n.get('label', '')
            break

    quoted_label = shell_quote_multiline(label)
    command = f"{use_prefix}{quoted_label}{use_suffix}".strip()
    requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "running"})

    try:
        subprocess.run(command, shell=True, check=True)
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "ran"})
    except subprocess.CalledProcessError:
        requests.post(f"{url}/update_status", json={"element_type": "node", "element_id": node, "status": "fail"})


def main(url, prefix='', suffix=''):
    graph = requests.get(url).json()
    use_prefix, use_suffix = get_prefix_suffix(graph, prefix, suffix)

    initialize_pipeline(url)
    status = ''
    while status != 'complete':
        status = schedule_tasks(url)
        run_tasks(url, use_prefix, use_suffix)

