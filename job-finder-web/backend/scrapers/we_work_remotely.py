"""We Work Remotely adapter foundation.

Live navigation is intentionally policy-gated.  The parsing boundary accepts
page HTML so it can be covered with saved fixtures without browsing WWR or
depending on a logged-in account.
"""
import hashlib
import logging
import re
from html import unescape
from html.parser import HTMLParser
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse

from backend.scrapers.base import PlatformJob

logger = logging.getLogger(__name__)

WWR_BASE_URL = "https://weworkremotely.com"


def _clean(value: str) -> str:
    return " ".join(unescape(value).split())


class _JobCardParser(HTMLParser):
    """Tolerant parser for the public WWR job-card markup captured in fixtures."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict] = []
        self._card: Optional[dict] = None
        self._depth = 0
        self._field: Optional[str] = None
        self._field_depth = 0

    @staticmethod
    def _classes(attrs: dict) -> set[str]:
        return set(attrs.get("class", "").split())

    def handle_starttag(self, tag: str, attrs_list) -> None:
        attrs = dict(attrs_list)
        classes = self._classes(attrs)
        if self._card is None and tag in {"li", "article"} and ("feature" in classes or "job" in classes):
            self._card = {"title": [], "company": [], "region": [], "date": [], "url": "", "apply_url": ""}
            self._depth = 1
            return
        if self._card is None:
            return
        self._depth += 1
        if tag == "a" and attrs.get("href"):
            href = attrs["href"]
            if not self._card["url"]:
                self._card["url"] = href
            if "apply" in classes or "apply" in href.lower():
                self._card["apply_url"] = href
        field_by_class = {
            "title": "title", "company": "company", "region": "region", "location": "region",
            "date": "date", "time": "date",
        }
        for css_class, field in field_by_class.items():
            if css_class in classes:
                self._field = field
                self._field_depth = self._depth
                break

    def handle_data(self, data: str) -> None:
        if self._card is not None and self._field:
            self._card[self._field].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._card is None:
            return
        if self._field and self._depth == self._field_depth:
            self._field = None
        self._depth -= 1
        if self._depth == 0:
            self.cards.append(self._card)
            self._card = None


class WeWorkRemotelyScraper:
    """WWR adapter with an explicit policy boundary before live access."""

    platform = "we_work_remotely"

    @staticmethod
    def parse_search_page(html: str, *, max_jobs: int = 20) -> list[PlatformJob]:
        """Normalize saved WWR search-page markup; performs no network activity."""
        parser = _JobCardParser()
        parser.feed(html)
        jobs: list[PlatformJob] = []
        seen_urls: set[str] = set()
        for card in parser.cards:
            title = _clean(" ".join(card["title"]))
            company = _clean(" ".join(card["company"]))
            job_url = urljoin(WWR_BASE_URL, card["url"])
            if not title or not company or not job_url or job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            region = _clean(" ".join(card["region"])) or None
            posted_date = _clean(" ".join(card["date"])) or None
            identifier = WeWorkRemotelyScraper._job_id(job_url)
            jobs.append(PlatformJob(
                title=title, company=company, location=region or "Remote",
                posted_date=posted_date, job_url=job_url, platform_job_id=identifier,
                apply_url=urljoin(WWR_BASE_URL, card["apply_url"]) if card["apply_url"] else None,
                remote_eligibility=region, source_timestamp=posted_date,
            ))
            if len(jobs) >= max_jobs:
                break
        return jobs

    @staticmethod
    def _job_id(job_url: str) -> str:
        path = urlparse(job_url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1]
        match = re.match(r"(\d+)(?:-|$)", slug)
        return match.group(1) if match else hashlib.sha256(job_url.encode()).hexdigest()[:16]

    async def search_jobs(
        self,
        query: str,
        location: str = "",
        max_jobs: int = 20,
        cookies_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> list[PlatformJob]:
        """WWR live session navigation is not implemented yet."""
        raise NotImplementedError("WWR live session navigation is pending the R3 login-health workflow.")
