"""
Schemas para API v2.
"""
from app.schemas.v2.serper import SerperRequest, SerperResponse
from app.schemas.v2.discovery import DiscoveryRequest, DiscoveryResponse
from app.schemas.v2.scrape import ScrapeRequest, ScrapeResponse
from app.schemas.v2.profile import ProfileRequest, ProfileResponse

__all__ = [
    "SerperRequest",
    "SerperResponse",
    "DiscoveryRequest",
    "DiscoveryResponse",
    "ScrapeRequest",
    "ScrapeResponse",
    "ProfileRequest",
    "ProfileResponse",
]

