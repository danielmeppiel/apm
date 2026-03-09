"""Tests for helper utility functions."""

import json
import unittest
import sys
from pathlib import Path
from apm_cli.utils.helpers import is_tool_available, detect_platform, get_available_package_managers, find_plugin_json


class TestHelpers(unittest.TestCase):
    """Test cases for helper utility functions."""
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Force garbage collection to release file handles
        import gc
        gc.collect()
        # Small delay to allow Windows to release locks
        import time
        time.sleep(0.1)
    
    def test_is_tool_available(self):
        """Test is_tool_available function with known commands."""
        # Python should always be available in the test environment
        self.assertTrue(is_tool_available('python'))
        
        # Test a command that almost certainly doesn't exist
        self.assertFalse(is_tool_available('this_command_does_not_exist_12345'))
    
    def test_detect_platform(self):
        """Test detect_platform function."""
        platform = detect_platform()
        self.assertIn(platform, ['macos', 'linux', 'windows', 'unknown'])
    
    def test_get_available_package_managers(self):
        """Test get_available_package_managers function."""
        managers = get_available_package_managers()
        self.assertIsInstance(managers, dict)
        
        # The function should return a valid dict
        # If any managers are found, they should have valid string values
        for name, path in managers.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(path, str)
            self.assertTrue(len(name) > 0)
            self.assertTrue(len(path) > 0)
        
        # On most Unix systems, at least one package manager should be available
        # This is a reasonable expectation but not guaranteed on minimal systems
        import sys
        if sys.platform != 'win32':
            # Skip this assertion on Windows since it might not have any
            # On Unix systems, we expect at least one package manager
            self.assertGreater(len(managers), 0, 
                             "Expected at least one package manager on Unix systems")


class TestFindPluginJson(unittest.TestCase):
    """Test cases for find_plugin_json deterministic location check."""

    def test_finds_root_plugin_json(self, tmp_path=None):
        """Root plugin.json is returned when present."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pj = root / "plugin.json"
            pj.write_text(json.dumps({"name": "test"}))
            assert find_plugin_json(root) == pj

    def test_finds_github_plugin_json(self):
        """plugin.json under .github/plugin/ is found."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / ".github" / "plugin" / "plugin.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"name": "gh"}))
            assert find_plugin_json(root) == target

    def test_finds_claude_plugin_json(self):
        """plugin.json under .claude-plugin/ is found."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / ".claude-plugin" / "plugin.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"name": "claude"}))
            assert find_plugin_json(root) == target

    def test_priority_order(self):
        """Root wins over .github/plugin/ which wins over .claude-plugin/."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for sub in ["plugin.json", ".github/plugin/plugin.json", ".claude-plugin/plugin.json"]:
                p = root / sub
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({"name": sub}))
            assert find_plugin_json(root) == root / "plugin.json"

    def test_ignores_unrelated_locations(self):
        """plugin.json buried in node_modules or other dirs is NOT found."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            hidden = root / "node_modules" / "evil" / "plugin.json"
            hidden.parent.mkdir(parents=True)
            hidden.write_text(json.dumps({"name": "evil"}))
            assert find_plugin_json(root) is None

    def test_returns_none_when_absent(self):
        """None is returned when no plugin.json exists anywhere."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            assert find_plugin_json(Path(d)) is None


if __name__ == '__main__':
    unittest.main()