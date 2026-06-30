from __future__ import annotations


def test_collect_descendants_bfs() -> None:
    from apeiria.utils.restart import _collect_descendants

    tree = {1: [2, 3], 2: [4], 4: [5], 3: []}
    assert sorted(_collect_descendants(tree, 1)) == [2, 3, 4, 5]
    assert sorted(_collect_descendants(tree, 2)) == [4, 5]
    assert _collect_descendants(tree, 5) == []


def test_collect_descendants_cycle_terminates() -> None:
    from apeiria.utils.restart import _collect_descendants

    tree = {1: [2], 2: [1]}
    result = _collect_descendants(tree, 1)
    assert set(result) <= {1, 2}


def test_descendant_pids_bogus_pid_empty() -> None:
    from apeiria.utils.restart import descendant_pids

    assert descendant_pids(999999999) == []
