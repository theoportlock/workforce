from workforce.__main__ import _maybe_rewrite_bare_target_to_run


KNOWN_COMMANDS = {"gui", "web", "run", "server", "edit"}


def test_bare_path_rewrites_to_run():
    argv = ["workforce", "./workflow.graphml"]
    assert _maybe_rewrite_bare_target_to_run(argv, KNOWN_COMMANDS) == [
        "workforce",
        "run",
        "./workflow.graphml",
    ]


def test_known_subcommand_not_rewritten():
    argv = ["workforce", "run", "./workflow.graphml"]
    assert _maybe_rewrite_bare_target_to_run(argv, KNOWN_COMMANDS) == argv


def test_flags_not_rewritten():
    argv = ["workforce", "--version"]
    assert _maybe_rewrite_bare_target_to_run(argv, KNOWN_COMMANDS) == argv
