"""CricAPI HTTP client.

Handles raw HTTP requests to CricketData.org (CricAPI) endpoints
with caching and retry logic. No data transformation -- just fetch
and return JSON.

Rate limits:
- Free tier: 100 requests/day (tracked via hitsToday/hitsLimit)

Caching is aggressive to stay within daily rate limits:
- series_info: 8 hours (all matches for a series)
- series search: 24 hours (series lookup by name)
- match_info: 30 minutes (individual match details)
- currentMatches: 5 minutes (live/active matches)

Dependencies are injected via constructor:
- LeagueMappingSource: For league configuration lookup
- api_key: From database settings (passed by factory in providers/__init__.py)

This client has NO direct database access -- all config is injected.
"""

import logging
import threading
import time

import httpx

from teamarr.core import LeagueMappingSource
from teamarr.utilities.cache import TTLCache, make_cache_key

logger = logging.getLogger(__name__)

CRICAPI_BASE_URL = "https://api.cricapi.com/v1"

# Cache TTLs (seconds)
CRICAPI_CACHE_TTL_SERIES_INFO = 8 * 60 * 60  # 8 hours
CRICAPI_CACHE_TTL_SERIES_SEARCH = 24 * 60 * 60  # 24 hours
CRICAPI_CACHE_TTL_MATCH_INFO = 30 * 60  # 30 minutes
CRICAPI_CACHE_TTL_CURRENT_MATCHES = 5 * 60  # 5 minutes


class CricAPIClient:
    """Low-level CricAPI HTTP client with caching and retry logic.

    API key resolution:
    1. Explicit api_key parameter (from database via factory)
    2. No fallback -- must be configured via Settings UI

    Free tier: 100 requests/day. Caching is aggressive to conserve quota.
    Rate limit tracking via hitsToday/hitsLimit from API responses.

    League mappings provided via LeagueMappingSource (no direct database access).
    """

    def __init__(
        self,
        league_mapping_source: LeagueMappingSource | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ):
        self._league_mapping_source = league_mapping_source
        self._api_key = api_key
        self._timeout = timeout
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()
        self._cache = TTLCache()

        # Rate limit tracking from API responses
        self._hits_today: int = 0
        self._hits_limit: int = 100
        self._hits_lock = threading.Lock()

    @property
    def api_key(self) -> str | None:
        """Return configured API key."""
        return self._api_key

    @property
    def hits_today(self) -> int:
        """Return current daily API hit count."""
        with self._hits_lock:
            return self._hits_today

    @property
    def hits_limit(self) -> int:
        """Return daily API hit limit."""
        with self._hits_lock:
            return self._hits_limit

    @property
    def hits_remaining(self) -> int:
        """Return remaining daily API hits."""
        with self._hits_lock:
            return max(0, self._hits_limit - self._hits_today)

    def _get_client(self) -> httpx.Client:
        """Get or create the HTTP client (thread-safe, lazy init)."""
        if self._client is None:
            with self._client_lock:
                # Double-check after acquiring lock
                if self._client is None:
                    self._client = httpx.Client(
                        timeout=self._timeout,
                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    )
        return self._client

    def _update_rate_limit_info(self, response_data: dict | None) -> None:
        """Extract and store rate limit info from API response.

        CricAPI returns rate limit info in the 'info' field:
        {"hitsToday": 7, "hitsLimit": 100, "totalRows": 74, "queryTime": 10}
        """
        if not response_data:
            return

        info = response_data.get("info")
        if not info:
            return

        with self._hits_lock:
            if "hitsToday" in info:
                self._hits_today = int(info["hitsToday"])
            if "hitsLimit" in info:
                self._hits_limit = int(info["hitsLimit"])

    def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make HTTP request with retry logic.

        Retries up to retry_count times on transient errors (5xx, network).
        Updates rate limit tracking from every response.

        Args:
            endpoint: API endpoint path (e.g., 'series_info')
            params: Query parameters (apikey added automatically)

        Returns:
            Parsed JSON response or None on failure
        """
        if not self._api_key:
            logger.warning("[CRAPI] No API key configured, skipping request to %s", endpoint)
            return None

        url = f"{CRICAPI_BASE_URL}/{endpoint}"

        # Build params with apikey
        request_params = dict(params) if params else {}
        request_params["apikey"] = self._api_key

        for attempt in range(self._retry_count):
            try:
                client = self._get_client()
                response = client.get(url, params=request_params)

                response.raise_for_status()

                result = response.json()

                # Track rate limit info from response
                self._update_rate_limit_info(result)

                # Check for API-level errors
                status = result.get("status", "")
                if status == "error":
                    logger.warning(
                        "[CRAPI] API error for %s: %s",
                        endpoint,
                        result.get("msg", "unknown"),
                    )
                    return None

                return result

            except httpx.HTTPStatusError as e:
                logger.warning(
                    "[CRAPI] HTTP %d for %s",
                    e.response.status_code,
                    url,
                )
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                    continue
                return None

            except (httpx.RequestError, RuntimeError, OSError) as e:
                logger.warning("[CRAPI] Request failed for %s: %s", url, e)
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                    continue
                return None

        return None

    def supports_league(self, league: str) -> bool:
        """Check if we have mapping for this league."""
        if not self._league_mapping_source:
            return False
        return self._league_mapping_source.supports_league(league, "cricapi")

    def get_provider_league_id(self, league: str) -> str | None:
        """Get CricAPI series GUID for a league code.

        This is the provider_league_id from league mappings (the series GUID).
        """
        if not self._league_mapping_source:
            return None
        mapping = self._league_mapping_source.get_mapping(league, "cricapi")
        return mapping.provider_league_id if mapping else None

    def get_sport(self, league: str) -> str:
        """Get canonical sport code for a league (lowercase)."""
        if not self._league_mapping_source:
            return "cricket"
        mapping = self._league_mapping_source.get_mapping(league, "cricapi")
        if mapping and mapping.sport:
            return mapping.sport
        return "cricket"

    def get_series_info(self, series_id: str) -> dict | None:
        """Fetch all matches for a series.

        Uses series_info endpoint with the series GUID.

        Args:
            series_id: CricAPI series GUID

        Returns:
            Raw API response with info and matchList, or None
        """
        cache_key = make_cache_key("cricapi", "series_info", series_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("[CRAPI] Cache hit: %s", cache_key)
            return cached

        result = self._request("series_info", {"id": series_id})
        if result:
            self._cache.set(cache_key, result, CRICAPI_CACHE_TTL_SERIES_INFO)
            logger.debug(
                "[CRAPI] Cached series_info for %s (%dh TTL)",
                series_id,
                CRICAPI_CACHE_TTL_SERIES_INFO // 3600,
            )
        return result

    def search_series(self, name: str) -> dict | None:
        """Search for series by name.

        Args:
            name: Search term (e.g., "Indian Premier League")

        Returns:
            Raw API response with list of matching series, or None
        """
        cache_key = make_cache_key("cricapi", "series_search", name.lower())
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("[CRAPI] Cache hit: %s", cache_key)
            return cached

        result = self._request("series", {"search": name})
        if result:
            self._cache.set(cache_key, result, CRICAPI_CACHE_TTL_SERIES_SEARCH)
            logger.debug(
                "[CRAPI] Cached series search for %s (%dh TTL)",
                name,
                CRICAPI_CACHE_TTL_SERIES_SEARCH // 3600,
            )
        return result

    def get_match_info(self, match_id: str) -> dict | None:
        """Fetch single match details with scores.

        Args:
            match_id: CricAPI match GUID

        Returns:
            Raw API response with match data, or None
        """
        cache_key = make_cache_key("cricapi", "match_info", match_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("[CRAPI] Cache hit: %s", cache_key)
            return cached

        result = self._request("match_info", {"id": match_id})
        if result:
            self._cache.set(cache_key, result, CRICAPI_CACHE_TTL_MATCH_INFO)
            logger.debug(
                "[CRAPI] Cached match_info for %s (%dm TTL)",
                match_id,
                CRICAPI_CACHE_TTL_MATCH_INFO // 60,
            )
        return result

    def get_current_matches(self, offset: int = 0) -> dict | None:
        """Fetch currently active matches.

        Args:
            offset: Pagination offset

        Returns:
            Raw API response with current match list, or None
        """
        cache_key = make_cache_key("cricapi", "current_matches", str(offset))
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("[CRAPI] Cache hit: %s", cache_key)
            return cached

        result = self._request("currentMatches", {"offset": str(offset)})
        if result:
            self._cache.set(cache_key, result, CRICAPI_CACHE_TTL_CURRENT_MATCHES)
            logger.debug(
                "[CRAPI] Cached currentMatches (%dm TTL)",
                CRICAPI_CACHE_TTL_CURRENT_MATCHES // 60,
            )
        return result

    def cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.stats()

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()

    def rate_limit_stats(self) -> dict:
        """Get rate limit statistics for UI feedback.

        Returns dict with:
        - hits_today: Current daily API hit count
        - hits_limit: Daily API hit limit
        - hits_remaining: Remaining daily hits
        """
        with self._hits_lock:
            return {
                "hits_today": self._hits_today,
                "hits_limit": self._hits_limit,
                "hits_remaining": max(0, self._hits_limit - self._hits_today),
            }

    def close(self) -> None:
        """Close the HTTP client."""
        with self._client_lock:
            if self._client:
                try:
                    self._client.close()
                except Exception as e:
                    logger.debug("[CRAPI] Error closing HTTP client: %s", e)
                self._client = None
