"""CricAPI data provider package."""

from teamarr.providers.cricapi.client import CricAPIClient
from teamarr.providers.cricapi.provider import CricAPIProvider

__all__ = ["CricAPIClient", "CricAPIProvider"]
