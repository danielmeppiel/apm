"""Tests for URL-based marketplace source and Agent Skills index parser.

Covers Step 1 (MarketplaceSource URL extension) and Step 4
(parse_agent_skills_index) from the issue #676 implementation plan.
"""

import pytest

from apm_cli.marketplace.models import (
    MarketplaceSource,
    parse_agent_skills_index,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_VALID_DIGEST = "sha256:" + "a" * 64
_KNOWN_SCHEMA = "https://schemas.agentskills.io/discovery/0.2.0/schema.json"

_SINGLE_SKILL_INDEX = {
    "$schema": _KNOWN_SCHEMA,
    "skills": [
        {
            "name": "code-review",
            "type": "skill-md",
            "description": "Code review helper",
            "url": "/.well-known/agent-skills/code-review/SKILL.md",
            "digest": _VALID_DIGEST,
        }
    ],
}


# ---------------------------------------------------------------------------
# MarketplaceSource — URL extension (Step 1)
# ---------------------------------------------------------------------------


class TestMarketplaceSourceURL:
    """MarketplaceSource extended with source_type='url'."""

    def test_url_source_creation(self):
        src = MarketplaceSource(
            name="example-skills",
            source_type="url",
            url="https://example.com/.well-known/agent-skills/index.json",
        )
        assert src.source_type == "url"
        assert src.url == "https://example.com/.well-known/agent-skills/index.json"
        assert src.owner == ""
        assert src.repo == ""

    def test_github_source_type_default(self):
        """Existing GitHub sources default to source_type='github'."""
        src = MarketplaceSource(name="acme", owner="acme-org", repo="plugins")
        assert src.source_type == "github"

    def test_url_source_frozen(self):
        src = MarketplaceSource(
            name="x", source_type="url", url="https://example.com"
        )
        with pytest.raises(AttributeError):
            src.url = "https://other.com"

    def test_is_url_source_true(self):
        src = MarketplaceSource(
            name="x", source_type="url", url="https://example.com"
        )
        assert src.is_url_source is True

    def test_is_url_source_false_for_github(self):
        src = MarketplaceSource(name="x", owner="o", repo="r")
        assert src.is_url_source is False

    # --- to_dict ---

    def test_url_source_to_dict_contains_source_type_and_url(self):
        src = MarketplaceSource(
            name="example-skills",
            source_type="url",
            url="https://example.com/.well-known/agent-skills/index.json",
        )
        d = src.to_dict()
        assert d["source_type"] == "url"
        assert d["url"] == "https://example.com/.well-known/agent-skills/index.json"

    def test_url_source_to_dict_omits_owner_and_repo(self):
        src = MarketplaceSource(
            name="example-skills",
            source_type="url",
            url="https://example.com/.well-known/agent-skills/index.json",
        )
        d = src.to_dict()
        assert "owner" not in d
        assert "repo" not in d

    def test_github_source_to_dict_omits_source_type(self):
        """GitHub sources must not add source_type to preserve backward compat."""
        src = MarketplaceSource(name="acme", owner="acme-org", repo="plugins")
        d = src.to_dict()
        assert "source_type" not in d

    # --- from_dict ---

    def test_url_source_from_dict(self):
        d = {
            "name": "example-skills",
            "source_type": "url",
            "url": "https://example.com/.well-known/agent-skills/index.json",
        }
        src = MarketplaceSource.from_dict(d)
        assert src.source_type == "url"
        assert src.url == "https://example.com/.well-known/agent-skills/index.json"
        assert src.owner == ""
        assert src.repo == ""

    def test_github_from_dict_backward_compat_no_source_type(self):
        """Old dicts without source_type field deserialize as 'github'."""
        d = {"name": "acme", "owner": "acme-org", "repo": "plugins"}
        src = MarketplaceSource.from_dict(d)
        assert src.source_type == "github"

    # --- roundtrip ---

    def test_url_source_roundtrip(self):
        original = MarketplaceSource(
            name="example-skills",
            source_type="url",
            url="https://example.com/.well-known/agent-skills/index.json",
        )
        restored = MarketplaceSource.from_dict(original.to_dict())
        assert restored == original

    def test_github_source_roundtrip_unchanged(self):
        """Existing GitHub roundtrip still works after model changes."""
        original = MarketplaceSource(
            name="acme",
            owner="acme-org",
            repo="plugins",
            host="ghe.corp.com",
            branch="release",
        )
        restored = MarketplaceSource.from_dict(original.to_dict())
        assert restored == original


# ---------------------------------------------------------------------------
# parse_agent_skills_index (Step 4)
# ---------------------------------------------------------------------------


class TestParseAgentSkillsIndex:
    """Parser for Agent Skills Discovery RFC v0.2.0 index format."""

    # --- happy path ---

    def test_basic_parse_returns_manifest(self):
        manifest = parse_agent_skills_index(_SINGLE_SKILL_INDEX, "example-skills")
        assert manifest.name == "example-skills"
        assert len(manifest.plugins) == 1

    def test_skill_entry_fields(self):
        manifest = parse_agent_skills_index(_SINGLE_SKILL_INDEX, "test")
        p = manifest.plugins[0]
        assert p.name == "code-review"
        assert p.description == "Code review helper"
        assert p.source_marketplace == "test"

    def test_skill_source_contains_url_digest_and_type(self):
        manifest = parse_agent_skills_index(_SINGLE_SKILL_INDEX, "test")
        s = manifest.plugins[0].source
        assert isinstance(s, dict)
        assert s["url"] == "/.well-known/agent-skills/code-review/SKILL.md"
        assert s["digest"] == _VALID_DIGEST
        assert s["type"] == "skill-md"

    def test_archive_type_entry(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {
                    "name": "my-toolset",
                    "type": "archive",
                    "description": "A set of tools",
                    "url": "/.well-known/agent-skills/my-toolset.tar.gz",
                    "digest": _VALID_DIGEST,
                }
            ],
        }
        manifest = parse_agent_skills_index(data, "test")
        assert len(manifest.plugins) == 1
        assert manifest.plugins[0].source["type"] == "archive"

    def test_multiple_skills(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {
                    "name": "skill-one",
                    "type": "skill-md",
                    "description": "First",
                    "url": "/a/SKILL.md",
                    "digest": _VALID_DIGEST,
                },
                {
                    "name": "skill-two",
                    "type": "archive",
                    "description": "Second",
                    "url": "/b.tar.gz",
                    "digest": _VALID_DIGEST,
                },
            ],
        }
        manifest = parse_agent_skills_index(data, "multi")
        assert len(manifest.plugins) == 2
        assert manifest.find_plugin("skill-one") is not None
        assert manifest.find_plugin("skill-two") is not None

    def test_empty_skills_list(self):
        data = {"$schema": _KNOWN_SCHEMA, "skills": []}
        manifest = parse_agent_skills_index(data, "test")
        assert len(manifest.plugins) == 0

    # --- $schema enforcement ---

    def test_known_schema_accepted(self):
        manifest = parse_agent_skills_index(_SINGLE_SKILL_INDEX, "test")
        assert len(manifest.plugins) == 1

    def test_unknown_schema_version_raises(self):
        data = {
            "$schema": "https://schemas.agentskills.io/discovery/9.9.9/schema.json",
            "skills": [],
        }
        with pytest.raises(ValueError, match="schema"):
            parse_agent_skills_index(data, "test")

    def test_missing_schema_raises(self):
        with pytest.raises(ValueError, match="schema"):
            parse_agent_skills_index({"skills": []}, "test")

    def test_non_string_schema_raises(self):
        with pytest.raises(ValueError, match="schema"):
            parse_agent_skills_index({"$schema": 42, "skills": []}, "test")

    # --- skill name validation (RFC: 1-64 chars, lowercase alnum + hyphens) ---

    def test_valid_name_simple(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "my-skill", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 1

    def test_valid_name_with_numbers(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "skill-v2-final", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 1

    def test_invalid_name_uppercase_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "MySkill", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    def test_invalid_name_spaces_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "bad name", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    def test_invalid_name_leading_hyphen_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "-bad", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    def test_invalid_name_trailing_hyphen_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "bad-", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    def test_invalid_name_consecutive_hyphens_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "bad--name", "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    def test_invalid_name_too_long_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "a" * 65, "type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    def test_missing_name_skipped(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"type": "skill-md", "url": "/x", "digest": _VALID_DIGEST}
            ],
        }
        assert len(parse_agent_skills_index(data, "t").plugins) == 0

    # --- mixed valid/invalid entries ---

    def test_only_valid_entries_returned(self):
        data = {
            "$schema": _KNOWN_SCHEMA,
            "skills": [
                {"name": "good-skill", "type": "skill-md", "url": "/a", "digest": _VALID_DIGEST},
                {"name": "Bad Skill!", "type": "skill-md", "url": "/b", "digest": _VALID_DIGEST},
                {"type": "skill-md", "url": "/c", "digest": _VALID_DIGEST},  # no name
            ],
        }
        manifest = parse_agent_skills_index(data, "test")
        assert len(manifest.plugins) == 1
        assert manifest.plugins[0].name == "good-skill"
