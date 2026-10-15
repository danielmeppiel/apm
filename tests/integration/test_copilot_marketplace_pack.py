"""Exercise real pack/config/builder/mapping with a hermetic Git transport."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from click.testing import CliRunner
from jsonschema import Draft7Validator

from apm_cli.commands.pack import pack_cmd
from apm_cli.marketplace.ref_resolver import RefResolver, RemoteRef
from apm_cli.utils import git_env
from apm_cli.utils.yaml_io import dump_yaml

pytestmark = pytest.mark.component
DEFAULT_OUTPUT = ".github/plugin/marketplace.json"


def _manifest(root: Path, **marketplace: Any) -> None:
    config = {
        "name": "copilot-catalog",
        "version": "1.0.0",
        "description": "Catalog",
        "marketplace": {
            "owner": {"name": "Acme", "email": "plugins@acme.test"},
            "outputs": {"copilot": {}},
            "packages": [
                {
                    "name": "demo",
                    "source": "./plugins/demo",
                    "description": "Demo",
                    "version": "1.0.0",
                }
            ],
            **marketplace,
        },
    }
    if config["marketplace"]["outputs"] is None:
        del config["marketplace"]["outputs"]
    dump_yaml(config, root / "apm.yml")
    plugin = root / "plugins" / "demo"
    plugin.mkdir(parents=True, exist_ok=True)
    dump_yaml({"name": "demo", "version": "1.0.0", "description": "Demo"}, plugin / "apm.yml")


def _read_output(root: Path, path: str = DEFAULT_OUTPUT) -> dict:
    doc = json.loads((root / path).read_text(encoding="utf-8"))
    schema = (
        Path(__file__).parents[1]
        / "fixtures"
        / "schemas"
        / "copilot-marketplace-source.schema.json"
    )
    validator = Draft7Validator(json.loads(schema.read_text(encoding="utf-8")))
    for plugin in doc["plugins"]:
        validator.validate(plugin["source"])
    return doc


@pytest.mark.parametrize(
    ("outputs", "sibling", "override", "expected"),
    [
        ({"copilot": {}}, None, None, DEFAULT_OUTPUT),
        ({"copilot": {"path": "dist/from-map.json"}}, None, None, "dist/from-map.json"),
        (
            {"copilot": {"path": "dist/from-map.json"}},
            "dist/from-sibling.json",
            None,
            "dist/from-sibling.json",
        ),
        (
            {"copilot": {"path": "dist/from-map.json"}},
            "dist/from-sibling.json",
            "dist/from-cli.json",
            "dist/from-cli.json",
        ),
    ],
)
def test_pack_copilot_output_path_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outputs: dict,
    sibling: str | None,
    override: str | None,
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APM_MARKETPLACE_COPILOT_PATH", "reserved-not-consumed.json")
    extra = {"copilot": {"output": sibling}} if sibling else {}
    _manifest(tmp_path, outputs=outputs, **extra)
    args = ["--json"]
    if override:
        args += ["--marketplace-path", f"copilot={override}"]
    result = CliRunner().invoke(pack_cmd, args)
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["ok"] is True
    doc = _read_output(tmp_path, expected)
    assert doc["metadata"] == {"description": "Catalog", "version": "1.0.0"}
    assert doc["owner"] == {"name": "Acme", "email": "plugins@acme.test"}
    assert "description" not in doc and "version" not in doc
    assert doc["plugins"][0]["source"] == "./plugins/demo"
    assert not (tmp_path / "reserved-not-consumed.json").exists()


def test_pack_still_defaults_to_claude_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _manifest(tmp_path, outputs=None)
    result = CliRunner().invoke(pack_cmd, ["--json"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".claude-plugin/marketplace.json").is_file()
    assert not (tmp_path / DEFAULT_OUTPUT).exists()
    selected = CliRunner().invoke(pack_cmd, ["--marketplace=copilot", "--json"])
    assert selected.exit_code == 0, selected.output
    assert _read_output(tmp_path)["plugins"][0]["source"] == "./plugins/demo"


def test_pack_copilot_and_existing_outputs_remain_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _manifest(
        tmp_path,
        outputs={"claude": {}, "copilot": {}, "codex": {}},
        packages=[{"name": "demo", "source": "./plugins/demo", "category": "testing"}],
    )
    result = CliRunner().invoke(pack_cmd, ["--json"])
    assert result.exit_code == 0, result.output
    copilot = _read_output(tmp_path)
    claude = json.loads((tmp_path / ".claude-plugin/marketplace.json").read_text())
    codex = json.loads((tmp_path / ".agents/plugins/marketplace.json").read_text())
    assert copilot["plugins"][0]["source"] == "./plugins/demo"
    assert copilot["plugins"][0]["description"] == "Demo"
    assert copilot["plugins"][0]["version"] == "1.0.0"
    assert claude["plugins"][0]["source"] == "./plugins/demo"
    assert codex["plugins"][0]["source"] == {"source": "local", "path": "./plugins/demo"}
    assert "category" not in copilot["plugins"][0]
    assert codex["plugins"][0]["category"] == "testing"


@pytest.fixture
def git_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    repo = tmp_path / "remote"
    repo.mkdir()
    git = git_env.get_git_executable()

    def run(*args: str) -> str:
        return subprocess.run(
            [
                git,
                "-C",
                str(repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.test",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "tag.gpgsign=false",
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    run("init", "--initial-branch=main")
    (repo / "plugin.json").write_text('{"name":"demo","version":"1.0.0"}\n', encoding="utf-8")
    run("add", "plugin.json")
    run("commit", "-m", "Fixture")
    run("tag", "-a", "v1.0.0", "-m", "Annotated release")
    run("tag", "lightweight")
    commit, tag_object = run("rev-parse", "HEAD"), run("rev-parse", "v1.0.0")
    real_ls_remote = git_env.git_remote_refs

    def local_transport(url: str, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        return real_ls_remote(str(repo), *args, **kwargs)

    monkeypatch.setattr(git_env, "git_remote_refs", local_transport)
    return commit, tag_object


@pytest.mark.parametrize(
    "source", ["acme/demo", "ghe.example.com/acme/demo", "https://gitlab.example.com/team/demo.git"]
)
@pytest.mark.parametrize(
    "ref", ["v1.0.0", "refs/tags/v1.0.0", "lightweight", "main", "commit", None]
)
@pytest.mark.parametrize("subdir", [None, "plugins/demo"])
def test_pack_remote_sources_preserve_commit_not_tag_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    git_remote: tuple[str, str],
    source: str,
    ref: str | None,
    subdir: str | None,
) -> None:
    commit, tag_object = git_remote
    monkeypatch.chdir(tmp_path)
    package = {
        "name": "demo",
        "source": source,
        "version": "1.0.0",
        "description": "Demo",
    }
    if subdir:
        package["subdir"] = subdir
    if ref:
        package["ref"] = commit if ref == "commit" else ref
    _manifest(tmp_path, outputs={"copilot": {}, "claude": {}}, packages=[package])
    result = CliRunner().invoke(pack_cmd, ["--json"])
    if ref == "main":
        assert result.exit_code != 0
        assert "branch/HEAD ref" in result.output
        assert not (tmp_path / DEFAULT_OUTPUT).exists()
        return
    assert result.exit_code == 0, result.output
    emitted = _read_output(tmp_path)["plugins"][0]["source"]
    if subdir:
        assert emitted["path"] == subdir
    else:
        assert "path" not in emitted
    assert emitted["sha"] == commit
    assert emitted["sha"] != tag_object
    if ref == "commit":
        assert "ref" not in emitted
    else:
        assert emitted["ref"] == (ref.removeprefix("refs/tags/") if ref else "v1.0.0")
    if source == "acme/demo":
        assert emitted["source"] == "github"
        assert emitted["repo"] == "acme/demo"
    else:
        assert emitted["source"] == "url"
        parsed = urlparse(emitted["url"])
        expected = urlparse(source if source.startswith("https://") else f"https://{source}")
        assert (parsed.scheme, parsed.hostname, parsed.path) == (
            expected.scheme,
            expected.hostname,
            expected.path,
        )
    # Annotated-tag handling must not change the existing Claude schema/pin.
    if ref in ("v1.0.0", "refs/tags/v1.0.0", None):
        claude = json.loads((tmp_path / ".claude-plugin/marketplace.json").read_text())
        assert claude["plugins"][0]["source"]["sha"] == tag_object
    stable = (tmp_path / DEFAULT_OUTPUT).read_bytes()
    check = CliRunner().invoke(pack_cmd, ["--json", "--check-clean"])
    assert check.exit_code == 0, check.output
    assert (tmp_path / DEFAULT_OUTPUT).read_bytes() == stable


def test_pack_rejects_unrepresentable_commit_without_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _manifest(
        tmp_path,
        packages=[
            {
                "name": "demo",
                "source": "acme/demo",
                "ref": "v1.0.0",
                "version": "1.0.0",
                "description": "Demo",
            }
        ],
    )
    monkeypatch.setattr(
        RefResolver,
        "list_remote_refs",
        lambda *a, **kw: [RemoteRef("refs/tags/v1.0.0", "short-sha")],
    )
    result = CliRunner().invoke(pack_cmd, ["--json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert any("full 40-character commit SHA" in error["message"] for error in payload["errors"])
    assert not (tmp_path / DEFAULT_OUTPUT).exists()
