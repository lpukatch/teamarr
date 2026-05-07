"""Smoke tests for ChannelsDVRClient.

The Channels DVR REST API is unauthenticated by design on the local
network — no auth handling lives here. These tests pin URL building,
source-name encoding, and HTTP error mapping so a refactor can't
silently break the refresh hook.
"""

import httpx
import pytest

from teamarr.channelsdvr.client import ChannelsDVRClient


class TestUrlBuilding:
    def test_strips_trailing_slash(self):
        client = ChannelsDVRClient(base_url="http://channels:8089/")
        assert client.base_url == "http://channels:8089"

    def test_source_path_uses_source_name(self):
        client = ChannelsDVRClient(
            base_url="http://channels:8089", source_name="MyM3U"
        )
        assert client._source_path() == "/providers/m3u/sources/MyM3U"

    def test_source_path_url_encodes_special_chars(self):
        # Spaces and slashes in source names must be percent-encoded.
        client = ChannelsDVRClient(
            base_url="http://channels:8089", source_name="My Source/With Slash"
        )
        assert (
            client._source_path()
            == "/providers/m3u/sources/My%20Source%2FWith%20Slash"
        )


class TestTriggerRefreshGuards:
    def test_no_source_name_returns_failure(self):
        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.trigger_m3u_refresh()
        assert result["success"] is False
        assert "source name" in result["message"].lower()


class TestTriggerRefreshHTTP:
    def test_successful_refresh_returns_success(self, monkeypatch):
        captured: dict = {}

        def fake_put(url, **kwargs):
            captured["url"] = url
            req = httpx.Request("PUT", url)
            return httpx.Response(204, request=req)

        monkeypatch.setattr(httpx, "put", fake_put)

        client = ChannelsDVRClient(
            base_url="http://channels:8089", source_name="MyM3U"
        )
        result = client.trigger_m3u_refresh()

        assert result["success"] is True
        assert (
            captured["url"]
            == "http://channels:8089/providers/m3u/sources/MyM3U/refresh"
        )

    def test_404_returns_source_not_found(self, monkeypatch):
        def fake_put(url, **kwargs):
            req = httpx.Request("PUT", url)
            return httpx.Response(404, request=req)

        monkeypatch.setattr(httpx, "put", fake_put)

        client = ChannelsDVRClient(
            base_url="http://channels:8089", source_name="MyM3U"
        )
        result = client.trigger_m3u_refresh()

        assert result["success"] is False
        assert "not found" in result["message"].lower()


class TestTestConnection:
    def test_status_unreachable_returns_error(self, monkeypatch):
        def fake_get(url, **kwargs):
            raise httpx.ConnectError("conn refused")

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.test_connection()
        assert result["success"] is False
        assert "cannot connect" in result["error"].lower()

    def test_status_ok_no_source_returns_success(self, monkeypatch):
        def fake_get(url, **kwargs):
            req = httpx.Request("GET", url)
            return httpx.Response(200, json={"version": "2026.04.01"}, request=req)

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.test_connection()
        assert result["success"] is True
        assert result["server_version"] == "2026.04.01"

    def test_source_404_returns_failure(self, monkeypatch):
        calls: list[str] = []

        def fake_get(url, **kwargs):
            calls.append(url)
            req = httpx.Request("GET", url)
            if url.endswith("/status"):
                return httpx.Response(
                    200, json={"version": "2026.04.01"}, request=req
                )
            return httpx.Response(404, request=req)

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(
            base_url="http://channels:8089", source_name="missing"
        )
        result = client.test_connection()
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert any("/providers/m3u/sources/missing" in c for c in calls)


class TestListSources:
    def test_returns_names_from_dict_payload(self, monkeypatch):
        # Channels DVR returns PascalCase JSON — confirm we extract Name.
        def fake_get(url, **kwargs):
            req = httpx.Request("GET", url)
            payload = [
                {"Name": "MyM3U", "Source": "..."},
                {"Name": "OtherSource"},
            ]
            return httpx.Response(200, json=payload, request=req)

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.list_m3u_sources()

        assert result["success"] is True
        assert result["sources"] == ["MyM3U", "OtherSource"]

    def test_handles_lowercase_name_field(self, monkeypatch):
        # Defensive: some forks may use lowercase keys.
        def fake_get(url, **kwargs):
            req = httpx.Request("GET", url)
            return httpx.Response(200, json=[{"name": "alt"}], request=req)

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.list_m3u_sources()
        assert result["sources"] == ["alt"]

    def test_handles_string_array_payload(self, monkeypatch):
        def fake_get(url, **kwargs):
            req = httpx.Request("GET", url)
            return httpx.Response(200, json=["A", "B"], request=req)

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.list_m3u_sources()
        assert result["sources"] == ["A", "B"]

    def test_unreachable_returns_error(self, monkeypatch):
        def fake_get(url, **kwargs):
            raise httpx.ConnectError("conn refused")

        monkeypatch.setattr(httpx, "get", fake_get)

        client = ChannelsDVRClient(base_url="http://channels:8089")
        result = client.list_m3u_sources()
        assert result["success"] is False
        assert result["sources"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
