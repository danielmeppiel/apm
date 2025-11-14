"""Tests for APM configuration management."""

import pytest
import tempfile
import os
import json
from pathlib import Path

from apm_cli.config import (
    get_auto_integrate,
    set_auto_integrate,
    get_config,
)


class TestAutoIntegrateConfig:
    """Test auto-integrate configuration management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Use temporary config directory
        self.temp_dir = tempfile.mkdtemp()
        # Monkey patch CONFIG_DIR and CONFIG_FILE
        import apm_cli.config
        self.original_config_dir = apm_cli.config.CONFIG_DIR
        self.original_config_file = apm_cli.config.CONFIG_FILE
        apm_cli.config.CONFIG_DIR = self.temp_dir
        apm_cli.config.CONFIG_FILE = os.path.join(self.temp_dir, "config.json")
    
    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        import apm_cli.config
        # Restore original values
        apm_cli.config.CONFIG_DIR = self.original_config_dir
        apm_cli.config.CONFIG_FILE = self.original_config_file
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_auto_integrate_is_true(self):
        """Test that auto_integrate defaults to True."""
        assert get_auto_integrate() == True
    
    def test_set_auto_integrate_false(self):
        """Test setting auto_integrate to False."""
        set_auto_integrate(False)
        assert get_auto_integrate() == False
    
    def test_set_auto_integrate_true(self):
        """Test setting auto_integrate to True."""
        set_auto_integrate(True)
        assert get_auto_integrate() == True
    
    def test_auto_integrate_persists(self):
        """Test that auto_integrate setting persists."""
        set_auto_integrate(False)
        # Read from file directly
        config = get_config()
        assert config["auto_integrate"] == False
