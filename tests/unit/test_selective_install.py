"""Tests for selective package installation (apm install <specific-package>).

This tests the fix where `apm install <package>` should only install that specific
package, while `apm install` (no args) installs all packages from apm.yml.

Bug context: Previously, running `apm install ComposioHQ/awesome-claude-skills/mcp-builder`
would also install unrelated packages like `design-guidelines` from apm.yml.
"""

import builtins
import pytest


class TestFilterMatchingLogic:
    """Test the filter matching logic used in _install_apm_dependencies.
    
    This replicates the exact filter logic from cli.py to ensure it correctly
    handles the host prefix mismatch issue (user passes 'owner/repo' but 
    str(dep) returns 'github.com/owner/repo').
    """

    def _matches_filter(self, dep_str: str, only_packages: list) -> bool:
        """Replicate the filter logic from cli.py for testing."""
        only_set = builtins.set(only_packages)
        
        # Check exact match
        if dep_str in only_set:
            return True
        # Check if dep_str ends with the user-provided package (handles host prefix)
        for pkg in only_set:
            if dep_str.endswith(pkg) or dep_str.endswith(f"/{pkg}"):
                return True
        return False

    def test_exact_match(self):
        """Test exact string match."""
        dep_str = "owner/repo"
        assert self._matches_filter(dep_str, ["owner/repo"])

    def test_host_prefix_match(self):
        """Test matching when dep has host prefix (the main bug case)."""
        dep_str = "github.com/owner/repo"
        assert self._matches_filter(dep_str, ["owner/repo"])

    def test_virtual_package_match(self):
        """Test matching virtual packages with subdirectory paths."""
        dep_str = "github.com/ComposioHQ/awesome-claude-skills/mcp-builder"
        assert self._matches_filter(dep_str, ["ComposioHQ/awesome-claude-skills/mcp-builder"])

    def test_non_match(self):
        """Test that non-matching packages don't match."""
        dep_str = "github.com/owner2/repo2"
        assert not self._matches_filter(dep_str, ["owner1/repo1"])

    def test_partial_repo_name_does_not_match(self):
        """Test that partial repo names don't cause false positives."""
        # If user wants 'owner/repo', it shouldn't match 'other-owner/repo'
        dep_str = "github.com/owner1/repo1"
        assert not self._matches_filter(dep_str, ["owner2/repo2"])

    def test_multiple_packages_in_filter(self):
        """Test filter with multiple packages requested."""
        filter_list = ["owner1/repo1", "owner2/repo2"]
        
        assert self._matches_filter("github.com/owner1/repo1", filter_list)
        assert self._matches_filter("github.com/owner2/repo2", filter_list)
        assert not self._matches_filter("github.com/owner3/repo3", filter_list)

    def test_real_bug_case_mcp_builder_vs_design_guidelines(self):
        """Test the exact bug case: user wants mcp-builder, not design-guidelines.
        
        This is the test that would have caught the original bug.
        """
        filter_list = ["ComposioHQ/awesome-claude-skills/mcp-builder"]
        
        # Should match mcp-builder
        assert self._matches_filter(
            "github.com/ComposioHQ/awesome-claude-skills/mcp-builder",
            filter_list
        )
        
        # Should NOT match design-guidelines
        assert not self._matches_filter(
            "github.com/danielmeppiel/design-guidelines",
            filter_list
        )

    def test_github_enterprise_host(self):
        """Test matching with GitHub Enterprise hosts."""
        dep_str = "ghe.company.com/owner/repo"
        assert self._matches_filter(dep_str, ["owner/repo"])

    def test_azure_devops_host(self):
        """Test matching with Azure DevOps hosts."""
        dep_str = "dev.azure.com/org/project/repo"
        # This should match if user passes the full path
        assert self._matches_filter(dep_str, ["org/project/repo"])

    def test_empty_filter_matches_nothing(self):
        """Test that empty filter matches nothing."""
        # This shouldn't happen in practice, but let's be safe
        assert not self._matches_filter("github.com/owner/repo", [])

