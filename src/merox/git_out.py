"""Git working-tree output with commit-on-change."""

from __future__ import annotations

import subprocess
from pathlib import Path

from merox.config import GitOutput


class GitError(RuntimeError):
    pass


def _run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise GitError(f"git {' '.join(args)} failed: {detail}")
    return result


def ensure_repo(git_out: GitOutput) -> Path:
    """Ensure a non-bare Git repo exists at git_out.repo (working tree)."""
    repo = git_out.repo
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        _run(repo, "init")
        _run(repo, "config", "user.name", git_out.user)
        _run(repo, "config", "user.email", git_out.email)
        readme = repo / "README.md"
        if not readme.exists():
            readme.write_text(
                "# merox backups\n\nManaged by [merox](https://github.com/borealis-ops/merox).\n",
                encoding="utf-8",
            )
            _run(repo, "add", "README.md")
            _run(repo, "commit", "-m", "merox: initialize backup repository")
    else:
        # Keep identity in sync with config for commits from this tool.
        _run(repo, "config", "user.name", git_out.user)
        _run(repo, "config", "user.email", git_out.email)
    return repo


def working_tree_root(git_out: GitOutput) -> Path:
    return ensure_repo(git_out)


def commit_if_changed(git_out: GitOutput, message: str) -> bool:
    """Stage all changes and commit if the index differs. Returns True if committed."""
    repo = ensure_repo(git_out)
    _run(repo, "add", "-A")
    status = _run(repo, "status", "--porcelain")
    if not status.stdout.strip():
        return False
    _run(repo, "commit", "-m", message)
    return True
