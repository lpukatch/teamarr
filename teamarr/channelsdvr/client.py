"""Channels DVR Server client for triggering M3U source refresh.

Channels DVR exposes an unauthenticated REST API on port 8089
(see https://getchannels.com/docs/server-api/introduction/). The API
requires requests to originate from the same local network — Teamarr
deployments live next to the DVR, so no auth handling is needed here.

The refresh endpoint is fire-and-forget: ``POST /providers/m3u/sources/
<source_name>/refresh`` returns ``200 OK`` with body ``true`` as soon
as the request is accepted, while the server runs the refresh task in
the background. There is no completion event or task-id to poll, so
this client only reports whether the request was accepted.
"""

import logging
import time
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class ChannelsDVRClient:
    """Client for Channels DVR Server API."""

    SERVER_LABEL: str = "CHANNELSDVR"

    def __init__(
        self,
        base_url: str,
        source_name: str = "",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.source_name = source_name
        self.timeout = timeout

    def _source_path(self) -> str:
        return f"/providers/m3u/sources/{quote(self.source_name, safe='')}"

    def list_m3u_sources(self) -> dict:
        """Fetch the list of M3U sources configured on the server.

        Channels DVR has no list endpoint at /providers/m3u/sources; instead
        every tuner and provider surfaces under /devices, and M3U sources are
        the entries with Provider == "m3u". The FriendlyName field is the
        source name used in /providers/m3u/sources/<name>/refresh.

        Returns:
            dict with success, sources (list of source names), error
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/devices",
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.ConnectError:
            return {
                "success": False,
                "sources": [],
                "error": f"Cannot connect to {self.base_url}",
            }
        except httpx.HTTPError as e:
            return {"success": False, "sources": [], "error": str(e)}

        try:
            data = resp.json()
        except ValueError:
            return {
                "success": False,
                "sources": [],
                "error": "Devices endpoint did not return JSON",
            }

        sources: list[str] = []
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                provider = item.get("Provider") or item.get("provider") or ""
                if str(provider).lower() != "m3u":
                    continue
                name = (
                    item.get("FriendlyName")
                    or item.get("friendlyName")
                    or item.get("Name")
                    or item.get("name")
                )
                if name:
                    sources.append(str(name))

        return {"success": True, "sources": sources}

    def test_connection(self) -> dict:
        """Verify connectivity, version, and that the source exists.

        Returns:
            dict with success, server_version, source_name, error
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/status",
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Cannot connect to {self.base_url}",
            }
        except httpx.HTTPError as e:
            return {"success": False, "error": str(e)}

        server_version: str | None = None
        try:
            data = resp.json()
            server_version = data.get("version") if isinstance(data, dict) else None
        except ValueError:
            # /status returned non-JSON — still treat as reachable
            pass

        if not self.source_name:
            return {
                "success": True,
                "server_version": server_version,
                "source_name": None,
            }

        try:
            src_resp = httpx.get(
                f"{self.base_url}{self._source_path()}",
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            return {
                "success": False,
                "server_version": server_version,
                "error": f"Failed to verify source: {e}",
            }

        if src_resp.status_code == 404:
            return {
                "success": False,
                "server_version": server_version,
                "error": f"Source '{self.source_name}' not found on Channels DVR",
            }
        if src_resp.status_code >= 400:
            return {
                "success": False,
                "server_version": server_version,
                "error": f"Source check returned HTTP {src_resp.status_code}",
            }

        return {
            "success": True,
            "server_version": server_version,
            "source_name": self.source_name,
        }

    def trigger_m3u_refresh(self, timeout: int = 60) -> dict:
        """Trigger an M3U source refresh on the Channels DVR server.

        The endpoint returns immediately — Channels DVR runs the refresh
        in the background, so this method does not poll for completion.

        Returns:
            dict with success, message, duration
        """
        if not self.source_name:
            return {
                "success": False,
                "message": "No source name configured",
                "duration": 0,
            }

        start = time.monotonic()
        try:
            resp = httpx.post(
                f"{self.base_url}{self._source_path()}/refresh",
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            duration = time.monotonic() - start
            if e.response.status_code == 404:
                msg = f"Source '{self.source_name}' not found"
            else:
                msg = f"Refresh failed: HTTP {e.response.status_code}"
            return {"success": False, "message": msg, "duration": duration}
        except httpx.HTTPError as e:
            return {
                "success": False,
                "message": f"Refresh failed: {e}",
                "duration": time.monotonic() - start,
            }

        duration = time.monotonic() - start
        logger.info(
            "[%s] Triggered refresh for source '%s' in %.2fs",
            self.SERVER_LABEL,
            self.source_name,
            duration,
        )
        return {
            "success": True,
            "message": f"Refresh triggered for source '{self.source_name}'",
            "duration": duration,
        }
