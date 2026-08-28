"""Shared HTTP session for all scrapers.

Provides a single requests.Session with a sensible User-Agent, per-domain
rate limiting, and retry/backoff handling for transient errors (including
429 Too Many Requests, honouring Retry-After when present).
"""
import time
import logging

import requests

log = logging.getLogger("scraping.http")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Minimum seconds between requests to the same domain
DOMAIN_DELAYS = {
    "fbref.com": 6.5,             # fbref rate limits aggressively
    "understat.com": 2.0,
    "www.football-data.co.uk": 1.0,
}
DEFAULT_DELAY = 2.0

_session = None
_last_request_at = {}


def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-GB,en;q=0.9",
        })
    return _session


def _domain(url):
    return url.split("/")[2] if "://" in url else url.split("/")[0]


def _respect_rate_limit(url):
    domain = _domain(url)
    delay = DOMAIN_DELAYS.get(domain, DEFAULT_DELAY)
    last = _last_request_at.get(domain)
    if last is not None:
        wait = delay - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[domain] = time.monotonic()


def fetch(url, *, timeout=20, retries=3, allow_404=False, headers=None):
    """GET a URL politely. Returns the Response, or None on persistent failure.

    - Waits between requests to the same domain.
    - Retries transient failures with exponential backoff.
    - On 429, honours the Retry-After header (capped at 120s).
    - On 403 (bot-blocked, e.g. fbref via Cloudflare) gives up immediately.
    """
    session = get_session()
    backoff = 5

    for attempt in range(1, retries + 1):
        _respect_rate_limit(url)
        try:
            response = session.get(url, timeout=timeout, headers=headers)
        except requests.RequestException as e:
            log.warning("Request error for %s (attempt %d/%d): %s", url, attempt, retries, e)
            if attempt == retries:
                return None
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code == 200:
            return response
        if response.status_code == 404:
            if not allow_404:
                log.warning("404 for %s", url)
            return None
        if response.status_code == 403:
            log.warning("403 (blocked) for %s - not retrying", url)
            return None
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                wait = min(int(retry_after), 120) if retry_after else backoff
            except ValueError:
                wait = backoff
            log.warning("429 for %s - waiting %ss", url, wait)
            time.sleep(wait)
            backoff *= 2
            continue

        log.warning("HTTP %s for %s (attempt %d/%d)", response.status_code, url, attempt, retries)
        if attempt == retries:
            return None
        time.sleep(backoff)
        backoff *= 2

    return None
