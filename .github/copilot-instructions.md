# Workforce – AI Coding Agent Guide

- Purpose: GraphML-backed workflow editor/runner; nodes store bash commands and statuses; server exposes REST + Socket.IO; GUI and CLI resolve URLs/files into active servers.
- Primary entrypoints: wf CLI dispatches GUI/RUN/SERVER/EDIT subcommands (workforce/__main__.py); tests live in tests/ and expect pytest.

## Core architecture
- Registry: temp file mapping Workfile → port/PID; resolved via resolve_target and cleaned before use (workforce/utils.py). default_workfile() opens ./Workfile if present.
- Server start: start_server in workforce/server/__init__.py sets up Flask + Socket.IO, background option via subprocess, caches queued mutations, registers routes and socket handlers, and spins graph worker thread.
- REST API: routes in workforce/server/routes.py provide graph CRUD, status edits, wrapper updates, node log upload, and /run which seeds run_id and decides roots (failed nodes → otherwise 0 in-degree or selected subset roots).
- Socket layer: workforce/server/sockets.py registers connect/subscribe and translates domain events to socket events (graph_update, node_ready, status_change, run_complete).
- Event bus + graph worker: ServerContext holds mod_queue, active_runs, and active_node_run. start_graph_worker in workforce/server/queue.py processes queued mutations, emits EventBus events, and enforces subset-only propagation: completed nodes mark outgoing edges to_run (only if target in run set); edges reaching all-ready targets set node status to run; RUN_COMPLETE emitted when no nodes left.
- Graph utilities: workforce/edit/graph.py loads/saves GraphML atomically, adds/removes nodes/edges (UUIDs), edits status/position/labels/wrapper/log. Graph attributes: node.label command, node.status "", run, running, ran, fail; edge.status "", to_run; graph.wrapper command template.
- Runner: workforce/run/client.py connects via Socket.IO, listens for node_ready, marks status running/ran/fail via /edit-status, sends logs via /save-node-log, wraps commands with wrapper ("{}" placeholder required for interpolation).
- GUI: workforce/gui/app.py launches Tk-based WorkflowApp; GUI background launch spawns python -m workforce gui <url> --foreground.

## Development workflow
- Create or open workflows: wf (opens ./Workfile), wf <file.graphml>, wf gui <path>, wf edit <subcommand> for API edits.
- Run execution: wf run <file|url> [--nodes id1 id2] [--wrapper "docker run -it ubuntu bash -c '{}'"]. Server auto-starts if not running.
- Server admin: wf server start/stop/ls [--port N] (default cleans registry and finds free port).
- Tests: use pytest from repo root; tests cover scheduler/resume/subset flow (tests/test_runner.py et al.).
- Packaging: Makefile has PyInstaller/deb/pkg targets; not part of normal dev loop.

## Patterns and cautions
- Always mutate graphs via server queue (ctx.enqueue/enqueue_status) to keep clients in sync and emit events; direct file writes bypass event bus.
- Subset runs: ctx.active_runs tracks allowed nodes; graph worker skips edges/targets outside the subset. Resume logic prioritizes failed nodes when no explicit selection.
- Status lifecycle: statuses changed via /edit-status; node_ready emits when status set to run; RUN_COMPLETE when no nodes remain run/running for a run_id.
- Wrapper handling: wrapper strings should include "{}" placeholder; Runner falls back to appending command when placeholder absent.
- Registry hygiene: clean_registry removes dead servers based on port checks; background servers write registry entry with PID/port/created_at.
- Logs: node stdout/stderr captured and posted back; GUI log viewer relies on node log attribute.

## When contributing
- Prefer new tests near existing patterns in tests/test_runner.py for scheduler/run changes.
- Keep GraphML compatibility: convert positions to strings and use uuid4 ids for nodes/edges.
- Maintain Socket.IO event names/protocol for GUI compatibility; emit through EventBus rather than direct socket calls.
