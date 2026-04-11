"""Tests for the install flow with mocked marketplace resolution."""

from unittest.mock import MagicMock, patch

import pytest

from apm_cli.marketplace.resolver import parse_marketplace_ref


class TestInstallMarketplacePreParse:
    """The pre-parse intercept in _validate_and_add_packages_to_apm_yml."""

    def test_marketplace_ref_detected(self):
        """NAME@MARKETPLACE triggers marketplace resolution."""
        result = parse_marketplace_ref("security-checks@acme-tools")
        assert result == ("security-checks", "acme-tools", None)

    def test_owner_repo_not_intercepted(self):
        """owner/repo should NOT be intercepted."""
        result = parse_marketplace_ref("owner/repo")
        assert result is None

    def test_owner_repo_at_alias_not_intercepted(self):
        """owner/repo@alias should NOT be intercepted (has slash)."""
        result = parse_marketplace_ref("owner/repo@alias")
        assert result is None

    def test_bare_name_not_intercepted(self):
        """Just a name without @ should NOT be intercepted."""
        result = parse_marketplace_ref("just-a-name")
        assert result is None

    def test_ssh_not_intercepted(self):
        """SSH URLs should NOT be intercepted (has colon)."""
        result = parse_marketplace_ref("git@github.com:o/r")
        assert result is None


class TestValidationOutcomeProvenance:
    """Verify marketplace provenance is attached to ValidationOutcome."""

    def test_outcome_has_provenance_field(self):
        from apm_cli.core.command_logger import _ValidationOutcome

        outcome = _ValidationOutcome(
            valid=[("owner/repo", False)],
            invalid=[],
            marketplace_provenance={
                "owner/repo": {
                    "discovered_via": "acme-tools",
                    "marketplace_plugin_name": "security-checks",
                }
            },
        )
        assert outcome.marketplace_provenance is not None
        assert "owner/repo" in outcome.marketplace_provenance

    def test_outcome_no_provenance(self):
        from apm_cli.core.command_logger import _ValidationOutcome

        outcome = _ValidationOutcome(valid=[], invalid=[])
        assert outcome.marketplace_provenance is None
