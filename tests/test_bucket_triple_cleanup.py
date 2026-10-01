"""The cleanup procedure must not revive the absolute 0.7 score gate."""

from bucket_triple_cleanup import self_check


def test_cleanup_has_no_absolute_score_gate():
    self_check()
