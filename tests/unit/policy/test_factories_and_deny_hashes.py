"""Policy keys for agent factories and content-hash revocation (#3231).

* ``factories`` (allow / require_signed / signers): parsed, validated,
  merged tighten-only, cached, and exposed via ``apm policy status --json``.
  APM does not enforce it; receipt verifiers such as apmx do.
* ``security.integrity.deny_hashes``: enforced fail-closed by APM through the
  ``install/integrity.py`` owner, in install and ``apm audit --ci``.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from apm_cli.commands.policy import _count_rules, _summarize_rules
from apm_cli.commands.policy import policy as policy_group
from apm_cli.deps.lockfile import LockedDependency, LockFile
from apm_cli.install.integrity import (
    denied_hash_matches,
    enforce_deny_hashes,
    enforce_installed_deny_hashes,
)
from apm_cli.policy import discovery
from apm_cli.policy.inheritance import merge_policies
from apm_cli.policy.parser import PolicyValidationError, load_policy
from apm_cli.policy.policy_checks import (
    FAIL_CLOSED_POLICY_CHECKS,
    _check_content_hash_denylist,
)
from apm_cli.policy.schema import (
    ApmPolicy,
    FactoriesPolicy,
    FactorySigner,
    IntegrityPolicy,
    SecurityPolicy,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
WORKFLOW_A = "acme/factories/.github/workflows/run.yml"
WORKFLOW_B = "acme/other/.github/workflows/sign.yaml@refs/heads/main"

FULL_POLICY = textwrap.dedent(
    f"""\
    name: org
    security:
      integrity:
        deny_hashes: ["{DIGEST_A}"]
    factories:
      allow:
        - "acme/checkout-factory@{DIGEST_B}"
        - "acme/*"
      require_signed: true
      signers:
        - workflow: {WORKFLOW_A}
        - workflow: {WORKFLOW_B}
    """
)


def _policy(**kwargs) -> ApmPolicy:
    factories = kwargs.pop("factories", FactoriesPolicy())
    deny = kwargs.pop("deny_hashes", ())
    return ApmPolicy(
        factories=factories,
        security=SecurityPolicy(integrity=IntegrityPolicy(deny_hashes=deny)),
    )


# -- Parsing and validation ----------------------------------------


class TestParsing:
    def test_full_policy_parses_without_unknown_key_warnings(self):
        policy, warnings = load_policy(FULL_POLICY)
        assert warnings == []
        assert policy.security.integrity.deny_hashes == (DIGEST_A,)
        assert policy.factories.allow == (f"acme/checkout-factory@{DIGEST_B}", "acme/*")
        assert policy.factories.require_signed is True
        assert policy.factories.signers == (
            FactorySigner(workflow=WORKFLOW_A),
            FactorySigner(workflow=WORKFLOW_B),
        )

    def test_defaults_when_absent(self):
        policy, _ = load_policy("name: p\n")
        assert policy.security.integrity.deny_hashes == ()
        assert policy.factories == FactoriesPolicy()
        assert policy.factories.allow is None
        assert policy.factories.signers is None

    def test_explicit_empty_lists_are_not_no_opinion(self):
        policy, _ = load_policy("factories:\n  allow: []\n  signers: []\n")
        assert policy.factories.allow == ()
        assert policy.factories.signers == ()

    def test_unknown_nested_keys_warn(self):
        _, warnings = load_policy(
            f"factories:\n  future: 1\n  signers:\n    - workflow: {WORKFLOW_A}\n      issuer: x\n"
        )
        assert "Unknown factories policy key: 'future'" in warnings
        assert "Unknown factories.signers[0] key: 'issuer'" in warnings

    @pytest.mark.parametrize(
        ("yaml_text", "fragment"),
        [
            ("security:\n  integrity:\n    deny_hashes: abc\n", "deny_hashes must be a YAML list"),
            (
                "security:\n  integrity:\n    deny_hashes: ['sha256:abc']\n",
                "deny_hashes entries",
            ),
            (
                "security:\n  integrity:\n    deny_hashes: ['" + "a" * 64 + "']\n",
                "deny_hashes entries",
            ),
            ("factories: [x]\n", "factories must be a YAML mapping"),
            ("factories:\n  allow: x\n", "factories.allow must be a YAML list"),
            ("factories:\n  allow: ['a/b@sha256:12']\n", "factories.allow entries"),
            ("factories:\n  allow: ['a b']\n", "factories.allow entries"),
            ("factories:\n  require_signed: maybe\n", "factories.require_signed"),
            ("factories:\n  signers: x\n", "factories.signers must be a YAML list"),
            ("factories:\n  signers: [x]\n", "factories.signers[0] must be a mapping"),
            (
                "factories:\n  signers:\n    - workflow: acme/run.yml\n",
                "factories.signers[0].workflow",
            ),
            ("factories:\n  signers:\n    - {}\n", "factories.signers[0].workflow"),
        ],
    )
    def test_malformed_values_are_rejected(self, yaml_text, fragment):
        with pytest.raises(PolicyValidationError) as exc:
            load_policy(yaml_text)
        assert any(fragment in err for err in exc.value.errors), exc.value.errors


# -- Inheritance ---------------------------------------------------


class TestMerge:
    def test_deny_hashes_union(self):
        merged = merge_policies(_policy(deny_hashes=(DIGEST_A,)), _policy(deny_hashes=(DIGEST_B,)))
        assert merged.security.integrity.deny_hashes == (DIGEST_A, DIGEST_B)

    def test_child_cannot_drop_parent_deny_hashes(self):
        merged = merge_policies(_policy(deny_hashes=(DIGEST_A,)), _policy())
        assert merged.security.integrity.deny_hashes == (DIGEST_A,)

    def test_allow_intersects_and_none_is_transparent(self):
        parent = _policy(factories=FactoriesPolicy(allow=("acme/*", "other/x")))
        child = _policy(factories=FactoriesPolicy(allow=("acme/*",)))
        assert merge_policies(parent, child).factories.allow == ("acme/*",)
        assert merge_policies(parent, _policy()).factories.allow == ("acme/*", "other/x")
        assert merge_policies(_policy(), child).factories.allow == ("acme/*",)

    def test_require_signed_is_logical_or(self):
        signed = _policy(factories=FactoriesPolicy(require_signed=True))
        assert merge_policies(signed, _policy()).factories.require_signed is True
        assert merge_policies(_policy(), signed).factories.require_signed is True

    def test_signers_intersect_by_identity(self):
        a, b = FactorySigner(WORKFLOW_A), FactorySigner(WORKFLOW_B)
        parent = _policy(factories=FactoriesPolicy(signers=(a, b)))
        child = _policy(factories=FactoriesPolicy(signers=(b,)))
        assert merge_policies(parent, child).factories.signers == (b,)
        assert merge_policies(parent, _policy()).factories.signers == (a, b)
        assert merge_policies(_policy(), child).factories.signers == (b,)
        empty = _policy(factories=FactoriesPolicy(signers=()))
        assert merge_policies(parent, empty).factories.signers == ()


# -- Cache round-trip and emptiness --------------------------------


class TestSerialization:
    def test_cache_round_trip_preserves_new_keys(self):
        policy, _ = load_policy(FULL_POLICY)
        reparsed, warnings = load_policy(discovery._serialize_policy(policy))
        assert warnings == []
        assert reparsed.factories == policy.factories
        assert reparsed.security.integrity == policy.security.integrity

    def test_round_trip_keeps_no_opinion_distinct(self):
        policy, _ = load_policy("name: p\n")
        reparsed, _ = load_policy(discovery._serialize_policy(policy))
        assert reparsed.factories.allow is None
        assert reparsed.factories.signers is None

    @pytest.mark.parametrize(
        "yaml_text",
        [
            f"security:\n  integrity:\n    deny_hashes: ['{DIGEST_A}']\n",
            "factories:\n  allow: []\n",
            "factories:\n  require_signed: true\n",
            f"factories:\n  signers:\n    - workflow: {WORKFLOW_A}\n",
        ],
    )
    def test_new_keys_make_policy_non_empty(self, yaml_text):
        policy, _ = load_policy(yaml_text)
        assert discovery._is_policy_empty(policy) is False


# -- Consumer surface: apm policy status ---------------------------


class TestPolicyStatusSurface:
    def test_rule_counts_and_summary(self):
        policy, _ = load_policy(FULL_POLICY)
        counts = _count_rules(policy)
        assert counts["integrity_deny_hashes"] == 1
        assert counts["factories_allow"] == 2
        assert counts["factories_signers"] == 2
        assert _count_rules(ApmPolicy())["factories_allow"] == -1
        summary = _summarize_rules(counts)
        assert "1 revoked content hashes" in summary
        assert "2 factory signers" in summary

    def test_status_json_exposes_effective_policy(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        policy_file = tmp_path / "apm-policy.yml"
        policy_file.write_text(FULL_POLICY, encoding="utf-8")
        result = CliRunner().invoke(
            policy_group, ["status", "--policy-source", str(policy_file), "--json"]
        )
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["outcome"] == "found"
        effective = report["effective_policy"]
        assert effective["security"]["integrity"]["deny_hashes"] == [DIGEST_A]
        assert effective["factories"] == {
            "allow": [f"acme/checkout-factory@{DIGEST_B}", "acme/*"],
            "require_signed": True,
            "signers": [{"workflow": WORKFLOW_A}, {"workflow": WORKFLOW_B}],
        }

    def test_status_json_effective_policy_null_without_policy(self, tmp_path: Path):
        absent = discovery.PolicyFetchResult(outcome="absent")
        with patch("apm_cli.commands.policy.discover_policy_with_chain", return_value=absent):
            result = CliRunner().invoke(policy_group, ["status", "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["effective_policy"] is None


# -- Enforcement owner: install/integrity.py -----------------------


def _dep(name: str, content_hash=None, files=None, local_path=None) -> LockedDependency:
    return LockedDependency(
        repo_url=f"https://example.com/{name}.git",
        resolved_commit="a" * 40,
        content_hash=content_hash,
        deployed_file_hashes=files or {},
        local_path=local_path,
    )


class TestDenyHashOwner:
    def test_no_deny_list_is_noop(self):
        enforce_deny_hashes([_dep("a", DIGEST_A)], IntegrityPolicy())
        enforce_deny_hashes([_dep("a", DIGEST_A)], None)

    def test_package_content_hash_match_fails_closed(self):
        with pytest.raises(RuntimeError, match="deny_hashes"):
            enforce_deny_hashes([_dep("a", DIGEST_A)], IntegrityPolicy(deny_hashes=(DIGEST_A,)))

    def test_deployed_file_hash_match_is_case_insensitive(self):
        dep = _dep("a", DIGEST_B, files={".github/skills/x/SKILL.md": DIGEST_A})
        matches = denied_hash_matches([dep], ("sha256:" + "A" * 64,))
        assert matches == [f"https://example.com/a.git: .github/skills/x/SKILL.md ({DIGEST_A})"]

    def test_project_local_content_is_covered(self):
        dep = _dep("self", files={".github/agents/a.md": DIGEST_C}, local_path=".")
        assert denied_hash_matches([dep], (DIGEST_C,)) == [
            f"<project>: .github/agents/a.md ({DIGEST_C})"
        ]

    def test_clean_lockfile_passes(self):
        dep = _dep("a", DIGEST_B, files={"f.md": DIGEST_C})
        enforce_deny_hashes([dep], IntegrityPolicy(deny_hashes=(DIGEST_A,)))


def _gate_ctx(apm_dir: Path, deny_hashes: tuple[str, ...], no_policy: bool = False):
    integrity = IntegrityPolicy(deny_hashes=deny_hashes)
    policy = SimpleNamespace(security=SimpleNamespace(integrity=integrity))
    return SimpleNamespace(
        no_policy=no_policy,
        policy_fetch=SimpleNamespace(policy=policy),
        apm_dir=apm_dir,
    )


def _write_lock(path: Path, dep: LockedDependency) -> None:
    lock = LockFile()
    lock.add_dependency(dep)
    lock.write(path / "apm.lock.yaml")


class TestInstallGate:
    def test_revoked_hash_fails_install(self, tmp_path: Path):
        from apm_cli.install.phases.policy_gate import PolicyViolationError

        _write_lock(tmp_path, _dep("a", DIGEST_A))
        with pytest.raises(PolicyViolationError, match="deny_hashes"):
            enforce_installed_deny_hashes(_gate_ctx(tmp_path, (DIGEST_A,)))

    def test_clean_lockfile_passes_install(self, tmp_path: Path):
        _write_lock(tmp_path, _dep("a", DIGEST_B))
        enforce_installed_deny_hashes(_gate_ctx(tmp_path, (DIGEST_A,)))

    def test_unreadable_lockfile_fails_closed(self, tmp_path: Path):
        from apm_cli.install.phases.policy_gate import PolicyViolationError

        with pytest.raises(PolicyViolationError, match="could not be read"):
            enforce_installed_deny_hashes(_gate_ctx(tmp_path, (DIGEST_A,)))

    def test_no_policy_and_empty_deny_list_skip(self, tmp_path: Path):
        enforce_installed_deny_hashes(_gate_ctx(tmp_path, (DIGEST_A,), no_policy=True))
        enforce_installed_deny_hashes(_gate_ctx(tmp_path, ()))

    def test_pipeline_routes_through_owner(self):
        from apm_cli.install import pipeline

        assert pipeline._enforce_deny_hashes is enforce_installed_deny_hashes


# -- apm audit --ci check adapter ----------------------------------


class TestAuditCheck:
    def test_check_is_fail_closed(self):
        assert "content-hash-denylist" in FAIL_CLOSED_POLICY_CHECKS

    def test_check_fails_on_revoked_hash(self):
        lock = LockFile()
        lock.add_dependency(_dep("a", DIGEST_A))
        check = _check_content_hash_denylist(lock, IntegrityPolicy(deny_hashes=(DIGEST_A,)))
        assert check.name == "content-hash-denylist"
        assert check.passed is False
        assert "example.com/a.git" in check.details[0]

    def test_check_passes_without_lockfile_or_match(self):
        policy = IntegrityPolicy(deny_hashes=(DIGEST_A,))
        assert _check_content_hash_denylist(None, policy).passed is True
        lock = LockFile()
        lock.add_dependency(_dep("a", DIGEST_B))
        assert _check_content_hash_denylist(lock, policy).passed is True
