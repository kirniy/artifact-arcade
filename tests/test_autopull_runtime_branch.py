from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_autopuller_merges_release_into_machine_local_branch() -> None:
    script = (ROOT / "scripts" / "autopull.sh").read_text()

    assert "git pull --ff-only" not in script
    assert 'git merge-base --is-ancestor "$REMOTE" HEAD' in script
    assert 'merge --no-edit --no-ff -X ours "$remote_ref"' in script
    assert "git merge --abort" in script


def test_autopuller_never_overwrites_uncommitted_runtime_changes() -> None:
    script = (ROOT / "scripts" / "autopull.sh").read_text()

    assert "runtime_tree_is_safe_to_merge" in script
    assert "tracked on-site changes are not in the runtime branch" in script
    assert "upstream path collides with local untracked file" in script
    assert "git reset --hard" not in script
    assert "git stash" not in script


def test_autopuller_keeps_idle_gated_restart() -> None:
    script = (ROOT / "scripts" / "autopull.sh").read_text()

    assert script.count("restart-artifact-if-idle.sh") >= 2
    assert "ARTIFACT_MARK_RESTART_PENDING=1" in script
