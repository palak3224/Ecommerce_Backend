# services/music/providers.py
"""Where songs come from.

Every catalogue is reached through the same small interface, so swapping Pixabay
for a label deal is one new class and a config change — nothing in the reel code,
the picker API or the mobile app moves.

That is not speculative future-proofing. It is already necessary: **Pixabay has no
music API.** Their REST API covers images and videos only, so their (genuinely
free, commercial-use) music has to be brought in as files. Meanwhile a real label
deal usually arrives as an S3 drop or an FTP dump, not an API either. So the
manual path is not a fallback — for most catalogues it is *the* path, and the API
adapters are the special case.
"""
from abc import ABC, abstractmethod

import requests
from flask import current_app


class ProviderError(Exception):
    """The catalogue could not be reached or understood."""


class MusicProvider(ABC):
    """One catalogue.

    `fetch` returns plain dicts rather than Song rows so a provider can be tested
    without a database, and so ingest owns all the persistence rules.
    """

    name = "base"

    @abstractmethod
    def fetch(self, query=None, limit=50, page=1):
        """Return a list of normalised track dicts.

        Required keys: provider_track_id, title, audio_url, duration_ms.
        Optional: artist, artwork_url, tags, language, licence_name, licence_url,
        attribution_required, attribution_text.
        """


class ManualProvider(MusicProvider):
    """Songs an admin uploads, one at a time or as a batch.

    Covers Pixabay (download from the site, upload here), a label's file delivery,
    and anything else without an API. The uploader is responsible for the rights —
    which is why this path is admin-only and never exposed to merchants.
    """

    name = "manual"

    def fetch(self, query=None, limit=50, page=1):
        # Nothing to poll: rows arrive through the admin upload endpoint.
        return []


class JamendoProvider(MusicProvider):
    """Jamendo's public API — hundreds of thousands of Creative Commons tracks.

    Useful for filling a development catalogue quickly. Note their free tier is
    licensed for **non-commercial** applications, so this is a way to exercise the
    pipeline with real audio, not a catalogue to launch on. Swap the adapter, keep
    everything else.
    """

    name = "jamendo"
    BASE = "https://api.jamendo.com/v3.0"

    def __init__(self, client_id=None):
        self.client_id = client_id or current_app.config.get("JAMENDO_CLIENT_ID")

    def fetch(self, query=None, limit=50, page=1):
        if not self.client_id:
            raise ProviderError("JAMENDO_CLIENT_ID is not configured.")

        params = {
            "client_id": self.client_id,
            "format": "json",
            "limit": min(int(limit), 200),
            "offset": (max(1, int(page)) - 1) * int(limit),
            "include": "musicinfo",
            "audioformat": "mp32",
        }
        if query:
            params["search"] = query
        else:
            params["order"] = "popularity_total"

        try:
            resp = requests.get(f"{self.BASE}/tracks/", params=params, timeout=20)
        except requests.RequestException as e:
            raise ProviderError(f"Jamendo unreachable: {e}")

        if resp.status_code != 200:
            raise ProviderError(f"Jamendo returned {resp.status_code}")

        try:
            results = resp.json().get("results", [])
        except ValueError as e:
            raise ProviderError(f"Jamendo sent an unreadable payload: {e}")

        return [self._normalise(t) for t in results if t.get("audio")]

    @staticmethod
    def _normalise(track):
        info = track.get("musicinfo") or {}
        tags = (info.get("tags") or {}).get("genres") or []
        return {
            "provider_track_id": str(track.get("id")),
            "title": track.get("name") or "Untitled",
            "artist": track.get("artist_name"),
            "artwork_url": track.get("album_image") or track.get("image"),
            # Jamendo reports whole seconds.
            "duration_ms": int(track.get("duration") or 0) * 1000,
            "audio_url": track.get("audio"),
            "preview_url": track.get("audio"),
            "tags": ",".join(t.lower() for t in tags)[:500],
            "licence_name": track.get("license_ccurl") and "Creative Commons",
            "licence_url": track.get("license_ccurl"),
            "attribution_required": True,
            "attribution_text": f"{track.get('name')} by {track.get('artist_name')} (Jamendo)",
        }


_REGISTRY = {
    ManualProvider.name: ManualProvider,
    JamendoProvider.name: JamendoProvider,
}


def get_provider(name):
    """Look a provider up by name. Adding a catalogue means adding to _REGISTRY."""
    cls = _REGISTRY.get((name or "").lower())
    if cls is None:
        raise ProviderError(
            f"Unknown music provider {name!r}. Known: {', '.join(sorted(_REGISTRY))}"
        )
    return cls()


def available_providers():
    return sorted(_REGISTRY)
