"""Tests for marketplace client -- HTTP mock, caching, TTL, auth, auto-detection."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from apm_cli.marketplace.errors import MarketplaceFetchError
from apm_cli.marketplace.models import MarketplaceSource
from apm_cli.marketplace import client as client_mod


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Point cache and config to temp directories."""
    config_dir = str(tmp_path / ".apm")
    monkeypatch.setattr("apm_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("apm_cli.config.CONFIG_FILE", str(tmp_path / ".apm" / "config.json"))
    monkeypatch.setattr("apm_cli.config._config_cache", None)
    monkeypatch.setattr("apm_cli.marketplace.registry._registry_cache", None)
    yield


def _make_source(name="acme"):
    return MarketplaceSource(name=name, owner="acme-org", repo="plugins")


class TestCache:
    """Cache read/write with TTL."""

    def test_write_and_read(self, tmp_path):
        data = {"name": "Test", "plugins": []}
        client_mod._write_cache("test-mkt", data)

        cached = client_mod._read_cache("test-mkt")
        assert cached is not None
        assert cached["name"] == "Test"

    def test_expired_cache(self, tmp_path, monkeypatch):
        data = {"name": "Test", "plugins": []}
        client_mod._write_cache("test-mkt", data)

        # Make the cache appear old
        meta_path = client_mod._cache_meta_path("test-mkt")
        with open(meta_path, "w") as f:
            json.dump({"fetched_at": time.time() - 7200, "ttl_seconds": 3600}, f)

        assert client_mod._read_cache("test-mkt") is None

    def test_stale_cache_still_readable(self, tmp_path):
        data = {"name": "Stale", "plugins": []}
        client_mod._write_cache("test-mkt", data)

        # Make the cache appear old
        meta_path = client_mod._cache_meta_path("test-mkt")
        with open(meta_path, "w") as f:
            json.dump({"fetched_at": time.time() - 7200, "ttl_seconds": 3600}, f)

        stale = client_mod._read_stale_cache("test-mkt")
        assert stale is not None
        assert stale["name"] == "Stale"

    def test_clear_cache(self, tmp_path):
        data = {"name": "Test", "plugins": []}
        client_mod._write_cache("test-mkt", data)
        client_mod._clear_cache("test-mkt")
        assert client_mod._read_cache("test-mkt") is None

    def test_nonexistent_cache(self):
        assert client_mod._read_cache("nonexistent") is None
        assert client_mod._read_stale_cache("nonexistent") is None


class TestFetchMarketplace:
    """fetch_marketplace with mocked HTTP."""

    def test_fetch_from_network(self, tmp_path):
        source = _make_source()
        raw_data = {
            "name": "Acme Plugins",
            "plugins": [
                {"name": "tool-a", "repository": "acme-org/tool-a"},
            ],
        }
        mock_resolver = MagicMock()
        mock_resolver.try_with_fallback.return_value = raw_data
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        manifest = client_mod.fetch_marketplace(
            source, force_refresh=True, auth_resolver=mock_resolver
        )
        assert manifest.name == "Acme Plugins"
        assert len(manifest.plugins) == 1

    def test_serves_from_cache(self, tmp_path):
        source = _make_source()
        raw_data = {
            "name": "Cached",
            "plugins": [{"name": "cached-tool", "repository": "o/r"}],
        }
        client_mod._write_cache(source.name, raw_data)

        # Should not hit network
        manifest = client_mod.fetch_marketplace(source)
        assert manifest.name == "Cached"
        assert len(manifest.plugins) == 1

    def test_force_refresh_bypasses_cache(self, tmp_path):
        source = _make_source()
        client_mod._write_cache(source.name, {"name": "Old", "plugins": []})

        new_data = {"name": "Fresh", "plugins": [{"name": "new", "repository": "o/r"}]}
        mock_resolver = MagicMock()
        mock_resolver.try_with_fallback.return_value = new_data
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        manifest = client_mod.fetch_marketplace(
            source, force_refresh=True, auth_resolver=mock_resolver
        )
        assert manifest.name == "Fresh"

    def test_stale_while_revalidate(self, tmp_path):
        source = _make_source()
        stale_data = {"name": "Stale", "plugins": []}
        client_mod._write_cache(source.name, stale_data)

        # Expire the cache
        meta_path = client_mod._cache_meta_path(source.name)
        with open(meta_path, "w") as f:
            json.dump({"fetched_at": time.time() - 7200, "ttl_seconds": 3600}, f)

        # Network fetch will fail
        mock_resolver = MagicMock()
        mock_resolver.try_with_fallback.side_effect = Exception("Network error")
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        manifest = client_mod.fetch_marketplace(
            source, auth_resolver=mock_resolver
        )
        assert manifest.name == "Stale"  # Falls back to stale cache

    def test_no_cache_no_network_raises(self, tmp_path):
        source = _make_source()
        mock_resolver = MagicMock()
        mock_resolver.try_with_fallback.side_effect = Exception("Network error")
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        with pytest.raises(MarketplaceFetchError):
            client_mod.fetch_marketplace(
                source, force_refresh=True, auth_resolver=mock_resolver
            )


class TestAutoDetectPath:
    """Auto-detect marketplace.json location in a repo."""

    def test_found_at_root(self, tmp_path):
        source = _make_source()
        mock_resolver = MagicMock()

        def mock_fetch(host, op, org=None, unauth_first=False):
            # First probe: marketplace.json at root -- found
            return {"name": "Test", "plugins": []}

        mock_resolver.try_with_fallback.side_effect = mock_fetch
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        path = client_mod._auto_detect_path(source, auth_resolver=mock_resolver)
        assert path == "marketplace.json"

    def test_found_at_github_plugin(self, tmp_path):
        source = _make_source()
        mock_resolver = MagicMock()
        call_count = [0]

        def mock_fetch(host, op, org=None, unauth_first=False):
            call_count[0] += 1
            if call_count[0] == 1:
                # First probe: root -- not found (404)
                return None
            # Second probe: .github/plugin/ -- found
            return {"name": "Test", "plugins": []}

        mock_resolver.try_with_fallback.side_effect = mock_fetch
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        path = client_mod._auto_detect_path(source, auth_resolver=mock_resolver)
        assert path == ".github/plugin/marketplace.json"

    def test_not_found_anywhere(self, tmp_path):
        source = _make_source()
        mock_resolver = MagicMock()
        mock_resolver.try_with_fallback.return_value = None
        mock_resolver.classify_host.return_value = MagicMock(api_base="https://api.github.com")

        path = client_mod._auto_detect_path(source, auth_resolver=mock_resolver)
        assert path is None
