"""Tests for version pin cache (immutability advisory).

Covers:
- Loading from missing / corrupt / valid pin files
- Recording and persisting pins
- Detecting ref changes (possible ref swap)
- Multi-plugin isolation
- Atomic write via os.replace
- Integration with resolve_marketplace_plugin (warning logged on ref change)
"""

import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.marketplace.version_pins import (
    _pin_key,
    _pins_path,
    check_version_pin,
    load_version_pins,
    record_version_pin,
    save_version_pins,
)


# ---------------------------------------------------------------------------
# Unit tests -- load / save
# ---------------------------------------------------------------------------


class TestLoadVersionPins:
    """Loading the pin file from disk."""

    def test_load_empty_no_file(self, tmp_path):
        """Missing file returns empty dict."""
        result = load_version_pins(pins_dir=str(tmp_path))
        assert result == {}

    def test_load_corrupt_json(self, tmp_path):
        """Corrupt JSON returns empty dict without raising."""
        path = tmp_path / "version-pins.json"
        path.write_text("{not valid json!!!")
        result = load_version_pins(pins_dir=str(tmp_path))
        assert result == {}

    def test_load_non_dict_json(self, tmp_path):
        """JSON that is not an object returns empty dict."""
        path = tmp_path / "version-pins.json"
        path.write_text('["a list", "not a dict"]')
        result = load_version_pins(pins_dir=str(tmp_path))
        assert result == {}

    def test_load_valid(self, tmp_path):
        """Valid JSON is returned as-is."""
        data = {"mkt/plug": {"1.0.0": "abc123"}}
        path = tmp_path / "version-pins.json"
        path.write_text(json.dumps(data))
        result = load_version_pins(pins_dir=str(tmp_path))
        assert result == data


class TestSaveVersionPins:
    """Saving the pin file to disk."""

    def test_save_creates_file(self, tmp_path):
        """Save creates the file if it does not exist."""
        pins = {"mkt/plug": {"1.0.0": "ref1"}}
        save_version_pins(pins, pins_dir=str(tmp_path))

        path = tmp_path / "version-pins.json"
        assert path.exists()
        assert json.loads(path.read_text()) == pins

    def test_save_creates_parent_dirs(self, tmp_path):
        """Save creates intermediate directories if needed."""
        nested = tmp_path / "a" / "b"
        pins = {"mkt/plug": {"2.0.0": "ref2"}}
        save_version_pins(pins, pins_dir=str(nested))

        path = nested / "version-pins.json"
        assert path.exists()
        assert json.loads(path.read_text()) == pins


# ---------------------------------------------------------------------------
# Unit tests -- record / check
# ---------------------------------------------------------------------------


class TestRecordAndCheck:
    """Recording pins and checking for ref changes."""

    def test_record_and_load(self, tmp_path):
        """Record a pin and verify it persists on disk."""
        record_version_pin("mkt", "plug", "1.0.0", "sha-aaa", pins_dir=str(tmp_path))
        pins = load_version_pins(pins_dir=str(tmp_path))
        assert pins["mkt/plug"]["1.0.0"] == "sha-aaa"

    def test_check_new_pin(self, tmp_path):
        """First time seeing a version returns None (no warning)."""
        result = check_version_pin("mkt", "plug", "1.0.0", "sha-aaa", pins_dir=str(tmp_path))
        assert result is None

    def test_check_matching_pin(self, tmp_path):
        """Same ref as previously recorded returns None."""
        record_version_pin("mkt", "plug", "1.0.0", "sha-aaa", pins_dir=str(tmp_path))
        result = check_version_pin("mkt", "plug", "1.0.0", "sha-aaa", pins_dir=str(tmp_path))
        assert result is None

    def test_check_changed_pin(self, tmp_path):
        """Different ref returns the previous (old) ref string."""
        record_version_pin("mkt", "plug", "1.0.0", "sha-aaa", pins_dir=str(tmp_path))
        result = check_version_pin("mkt", "plug", "1.0.0", "sha-bbb", pins_dir=str(tmp_path))
        assert result == "sha-aaa"

    def test_record_overwrites(self, tmp_path):
        """Recording the same version twice overwrites the old ref."""
        record_version_pin("mkt", "plug", "1.0.0", "sha-aaa", pins_dir=str(tmp_path))
        record_version_pin("mkt", "plug", "1.0.0", "sha-bbb", pins_dir=str(tmp_path))
        pins = load_version_pins(pins_dir=str(tmp_path))
        assert pins["mkt/plug"]["1.0.0"] == "sha-bbb"

    def test_multiple_plugins(self, tmp_path):
        """Different plugins do not interfere with each other."""
        record_version_pin("mkt", "alpha", "1.0.0", "ref-a", pins_dir=str(tmp_path))
        record_version_pin("mkt", "beta", "1.0.0", "ref-b", pins_dir=str(tmp_path))

        assert check_version_pin("mkt", "alpha", "1.0.0", "ref-a", pins_dir=str(tmp_path)) is None
        assert check_version_pin("mkt", "beta", "1.0.0", "ref-b", pins_dir=str(tmp_path)) is None
        # Alpha ref changed, beta unchanged
        assert check_version_pin("mkt", "alpha", "1.0.0", "ref-x", pins_dir=str(tmp_path)) == "ref-a"
        assert check_version_pin("mkt", "beta", "1.0.0", "ref-b", pins_dir=str(tmp_path)) is None

    def test_multiple_versions_same_plugin(self, tmp_path):
        """Different versions of the same plugin are tracked independently."""
        record_version_pin("mkt", "plug", "1.0.0", "ref-v1", pins_dir=str(tmp_path))
        record_version_pin("mkt", "plug", "2.0.0", "ref-v2", pins_dir=str(tmp_path))

        assert check_version_pin("mkt", "plug", "1.0.0", "ref-v1", pins_dir=str(tmp_path)) is None
        assert check_version_pin("mkt", "plug", "2.0.0", "ref-v2", pins_dir=str(tmp_path)) is None
        # Only v1 ref changed
        assert check_version_pin("mkt", "plug", "1.0.0", "ref-new", pins_dir=str(tmp_path)) == "ref-v1"
        assert check_version_pin("mkt", "plug", "2.0.0", "ref-v2", pins_dir=str(tmp_path)) is None


# ---------------------------------------------------------------------------
# Unit tests -- key normalization
# ---------------------------------------------------------------------------


class TestPinKey:
    """Pin key construction and normalization."""

    def test_lowercase(self):
        assert _pin_key("MKT", "Plugin") == "mkt/plugin"

    def test_already_lower(self):
        assert _pin_key("mkt", "plugin") == "mkt/plugin"


# ---------------------------------------------------------------------------
# Unit tests -- pins_path
# ---------------------------------------------------------------------------


class TestPinsPath:
    """Path construction for the pins file."""

    def test_custom_dir(self, tmp_path):
        result = _pins_path(pins_dir=str(tmp_path))
        assert result == os.path.join(str(tmp_path), "version-pins.json")

    def test_default_dir(self):
        """Default path (no pins_dir) includes version-pins.json under CONFIG_DIR."""
        with patch("apm_cli.config.CONFIG_DIR", "/fake/.apm"):
            result = _pins_path(pins_dir=None)
        assert result == os.path.join("/fake/.apm", "cache", "marketplace", "version-pins.json")


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """Verify save uses atomic write pattern (tmp + os.replace)."""

    def test_atomic_write_uses_replace(self, tmp_path):
        """os.replace is called to atomically move the temp file."""
        pins = {"mkt/plug": {"1.0.0": "ref1"}}

        with patch("apm_cli.marketplace.version_pins.os.replace", wraps=os.replace) as mock_replace:
            save_version_pins(pins, pins_dir=str(tmp_path))
            mock_replace.assert_called_once()
            args = mock_replace.call_args[0]
            assert args[0].endswith(".tmp")
            assert args[1].endswith("version-pins.json")

    def test_no_tmp_file_remains(self, tmp_path):
        """After save, no .tmp file should remain on disk."""
        save_version_pins({"k": {"v": "r"}}, pins_dir=str(tmp_path))
        remaining = list(tmp_path.iterdir())
        assert all(not f.name.endswith(".tmp") for f in remaining)


# ---------------------------------------------------------------------------
# Fail-open behavior
# ---------------------------------------------------------------------------


class TestFailOpen:
    """Advisory system must never raise on I/O errors."""

    def test_save_to_readonly_dir_does_not_raise(self, tmp_path):
        """Save to an unwritable location logs and returns without error."""
        # Use a path that does not exist and cannot be created
        bad_dir = "/dev/null/impossible"
        # Should not raise
        save_version_pins({"k": {"v": "r"}}, pins_dir=bad_dir)

    def test_check_with_corrupt_file_returns_none(self, tmp_path):
        """check_version_pin with corrupt file returns None (no warning)."""
        path = tmp_path / "version-pins.json"
        path.write_text("CORRUPT!!!")
        result = check_version_pin("mkt", "plug", "1.0.0", "ref", pins_dir=str(tmp_path))
        assert result is None

    def test_check_with_non_dict_plugin_entry(self, tmp_path):
        """If the plugin entry is not a dict, return None gracefully."""
        data = {"mkt/plug": "not-a-dict"}
        path = tmp_path / "version-pins.json"
        path.write_text(json.dumps(data))
        result = check_version_pin("mkt", "plug", "1.0.0", "ref", pins_dir=str(tmp_path))
        assert result is None


# ---------------------------------------------------------------------------
# Integration -- resolver emits warning on ref change
# ---------------------------------------------------------------------------


class TestResolverIntegration:
    """Verify resolve_marketplace_plugin logs a warning when a version ref changes."""

    def _make_source(self):
        from apm_cli.marketplace.models import MarketplaceSource

        return MarketplaceSource(name="test-mkt", owner="acme-org", repo="marketplace")

    def _make_manifest(self, plugin):
        from apm_cli.marketplace.models import MarketplaceManifest

        return MarketplaceManifest(
            name="test-mkt",
            plugins=(plugin,),
            plugin_root="",
        )

    def _make_plugin(self, ref="sha-original"):
        from apm_cli.marketplace.models import MarketplacePlugin, VersionEntry

        return MarketplacePlugin(
            name="my-plugin",
            source={"type": "github", "repo": "acme-org/my-plugin", "ref": "main"},
            versions=(VersionEntry(version="2.0.0", ref=ref),),
            source_marketplace="test-mkt",
        )

    def test_no_warning_on_first_install(self, tmp_path, caplog):
        """First install of a version should not log a warning."""
        from apm_cli.marketplace.resolver import resolve_marketplace_plugin

        plugin = self._make_plugin(ref="sha-original")
        source = self._make_source()
        manifest = self._make_manifest(plugin)

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
            patch(
                "apm_cli.marketplace.version_pins.load_version_pins",
                return_value={},
            ),
            patch(
                "apm_cli.marketplace.version_pins.save_version_pins",
            ),
        ):
            with caplog.at_level(logging.WARNING, logger="apm_cli.marketplace.resolver"):
                resolve_marketplace_plugin(
                    "my-plugin", "test-mkt", version_spec="2.0.0"
                )
            assert "ref changed" not in caplog.text

    def test_warning_on_ref_change(self, tmp_path, caplog):
        """When a known version ref changes, a warning is logged."""
        from apm_cli.marketplace.resolver import resolve_marketplace_plugin

        plugin = self._make_plugin(ref="sha-evil")
        source = self._make_source()
        manifest = self._make_manifest(plugin)

        # Simulate a previously recorded pin with a different ref
        existing_pins = {"test-mkt/my-plugin": {"2.0.0": "sha-original"}}

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
            patch(
                "apm_cli.marketplace.version_pins.load_version_pins",
                return_value=existing_pins,
            ),
            patch(
                "apm_cli.marketplace.version_pins.save_version_pins",
            ),
        ):
            with caplog.at_level(logging.WARNING, logger="apm_cli.marketplace.resolver"):
                resolve_marketplace_plugin(
                    "my-plugin", "test-mkt", version_spec="2.0.0"
                )
            assert "ref changed" in caplog.text
            assert "sha-original" in caplog.text
            assert "sha-evil" in caplog.text
            assert "ref swap attack" in caplog.text

    def test_no_warning_when_ref_matches(self, tmp_path, caplog):
        """Same ref as previously pinned produces no warning."""
        from apm_cli.marketplace.resolver import resolve_marketplace_plugin

        plugin = self._make_plugin(ref="sha-original")
        source = self._make_source()
        manifest = self._make_manifest(plugin)

        existing_pins = {"test-mkt/my-plugin": {"2.0.0": "sha-original"}}

        with (
            patch(
                "apm_cli.marketplace.resolver.get_marketplace_by_name",
                return_value=source,
            ),
            patch(
                "apm_cli.marketplace.resolver.fetch_or_cache",
                return_value=manifest,
            ),
            patch(
                "apm_cli.marketplace.version_pins.load_version_pins",
                return_value=existing_pins,
            ),
            patch(
                "apm_cli.marketplace.version_pins.save_version_pins",
            ),
        ):
            with caplog.at_level(logging.WARNING, logger="apm_cli.marketplace.resolver"):
                resolve_marketplace_plugin(
                    "my-plugin", "test-mkt", version_spec="2.0.0"
                )
            assert "ref changed" not in caplog.text
