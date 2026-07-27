from __future__ import annotations

import json
from pathlib import Path

from merox.git_out import GitOutput, commit_if_changed, ensure_repo
from merox.normalize import dumps, normalize, slugify


def test_slugify_strips_unsafe():
    assert slugify('Site A/B: "core"') == "Site_A_B___core"
    assert slugify("") == "unnamed"


def test_normalize_sorts_keys():
    data = {"b": 1, "a": {"z": 2, "y": 3}}
    assert normalize(data) == {"a": {"y": 3, "z": 2}, "b": 1}


def test_dumps_stable():
    text = dumps({"b": 1, "a": [2, 1]})
    assert text == '{\n  "a": [\n    2,\n    1\n  ],\n  "b": 1\n}\n'
    assert json.loads(text)["a"] == [2, 1]


def test_commit_skipped_when_unchanged(tmp_path: Path):
    repo = tmp_path / "configs"
    git_out = GitOutput(repo=repo, user="merox", email="merox@test")
    ensure_repo(git_out)

    sample = repo / "orgs" / "demo" / "settings.json"
    sample.parent.mkdir(parents=True)
    sample.write_text('{"ok": true}\n', encoding="utf-8")
    assert commit_if_changed(git_out, "merox: first") is True
    assert commit_if_changed(git_out, "merox: again") is False

    sample.write_text('{"ok": false}\n', encoding="utf-8")
    assert commit_if_changed(git_out, "merox: changed") is True
