"""The cleanup procedure must not revive the absolute 0.7 score gate."""

from pathlib import Path

from bucket_triple_cleanup import self_check


def test_cleanup_has_no_absolute_score_gate():
    self_check()


def test_bucket_triple_cleanup_stays_off_locked_runner():
    """The locked Phase I runner must not import or call the cleanup path.

    An n=200 cleanup result is not a locked N=10000 cell and must not be
    reachable by omitting a flag on scripts/run_completion_measurements.py.
    """
    import ast

    from fhrr_protocol import run_trial, sample_codebook

    root = Path(__file__).resolve().parents[1]
    runner = (root / "scripts" / "run_completion_measurements.py").read_text(encoding="utf-8")
    protocol = (root / "core" / "fhrr_protocol.py").read_text(encoding="utf-8")
    tree = ast.parse(runner)
    imported = []
    run_cell_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if called == "run_cell":
                run_cell_calls.append(node)
    assert run_cell_calls, "locked runner no longer calls run_cell"
    for name in imported:
        assert "bucket_triple" not in name
    forbidden = (
        "bucket_triple",
        "bucket_triple_cleanup",
        "run_bucket_cleanup_trial",
        "phasor_cleanup_on_subcodebook",
        "PROCEDURE_ID",
    )
    for token in forbidden:
        assert token not in runner
    for call in run_cell_calls:
        keys = [kw.arg for kw in call.keywords]
        assert "variant" not in keys
        assert all(key is None or "bucket" not in key for key in keys)
    protocol_tree = ast.parse(protocol)
    protocol_imports = []
    for node in ast.walk(protocol_tree):
        if isinstance(node, ast.Import):
            protocol_imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                protocol_imports.append(node.module)
            protocol_imports.extend(alias.name for alias in node.names)
    for name in protocol_imports:
        assert "bucket_triple" not in name
    for token in ("bucket_triple", "run_bucket_cleanup_trial"):
        assert token not in protocol
    codebook = sample_codebook(4, 16, 1)
    rng = __import__("numpy").random.default_rng(0)
    try:
        run_trial(
            codebook, 2, 0.0, 1, rng, t_max=2, variant="bucket_triple_cleanup",
        )
    except ValueError as exc:
        assert "unknown resonator variant" in str(exc)
    else:
        raise AssertionError("locked run_trial accepted bucket_triple_cleanup")
