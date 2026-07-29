"""Robust, read-only client for the openFDA food enforcement endpoint."""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import TypeGuard
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from recallready.models import (
    FoodEnforcementRecord,
    JsonMapping,
    OpenFDAMetadata,
    SourceFoodEnforcementRecord,
)

ENDPOINT = "https://api.fda.gov/food/enforcement.json"
PAGE_SIZE = 1000
MAX_SKIP_RESULT_WINDOW = 26_000
DEFAULT_USER_AGENT = "RecallReady/0.1 (+https://github.com/recallready/recallready)"
_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class OpenFDAClientError(RuntimeError):
    """Base class for safe, actionable openFDA client errors."""


class OpenFDARequestError(OpenFDAClientError):
    """Raised after a non-retriable response or exhausted retries."""


class OpenFDAResponseError(OpenFDAClientError):
    """Raised when a response is malformed or has an unexpected schema."""


class OpenFDAPaginationError(OpenFDAClientError):
    """Raised when pagination cannot safely retrieve a complete result set."""


@dataclass(frozen=True, slots=True)
class OpenFDAClientOptions:
    """Safe operational limits for the openFDA client."""

    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_base_delay_seconds: float = 0.5


@dataclass(frozen=True, slots=True)
class _Page:
    """A validated API page and its continuation metadata."""

    records: tuple[SourceFoodEnforcementRecord, ...]
    metadata: OpenFDAMetadata | None
    next_url: str | None


class OpenFDAClient:
    """Iterate public food enforcement records without writing local state."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        options: OpenFDAClientOptions | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        logger: logging.Logger | None = None,
    ) -> None:
        """Create a client; injected clients and clocks make network behavior testable."""
        self._api_key = api_key
        self._options = options or OpenFDAClientOptions()
        self._sleep = sleep
        self._random_value = random_value
        self._logger = logger or logging.getLogger("recallready.openfda")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(
                connect=self._options.connect_timeout_seconds,
                read=self._options.read_timeout_seconds,
                write=self._options.connect_timeout_seconds,
                pool=self._options.connect_timeout_seconds,
            ),
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
        )
        self._client.headers["User-Agent"] = DEFAULT_USER_AGENT
        self._client.headers["Accept"] = "application/json"
        self.last_metadata: OpenFDAMetadata | None = None

    def __enter__(self) -> OpenFDAClient:
        """Return this client as a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close only an HTTP client owned by this instance."""
        self.close()

    def close(self) -> None:
        """Close the internally-created HTTP client."""
        if self._owns_client:
            self._client.close()

    def iter_records(
        self,
        *,
        sample_size: int | None = None,
        earliest_report_date: date = date(2004, 1, 1),
        latest_report_date: date | None = None,
    ) -> Iterator[SourceFoodEnforcementRecord]:
        """Yield source records using search-after, then bounded date partitions if needed."""
        if sample_size is not None and sample_size < 1:
            raise ValueError("sample_size must be greater than zero when provided")

        end_date = latest_report_date or date.today()
        if earliest_report_date > end_date:
            raise ValueError("earliest_report_date must be on or before latest_report_date")

        yielded = 0
        for record in self._iter_preferred_or_fallback(earliest_report_date, end_date):
            yield record
            yielded += 1
            if sample_size is not None and yielded >= sample_size:
                return

    def _iter_preferred_or_fallback(
        self, earliest_report_date: date, latest_report_date: date
    ) -> Iterator[SourceFoodEnforcementRecord]:
        first_page = self._fetch_page(self._initial_params())
        if first_page.next_url is None and _requires_more_pages(first_page):
            self._logger.info("openfda_pagination_fallback mode=date_partition")
            yield from self._iter_date_partitions(earliest_report_date, latest_report_date)
            return

        yield from self._iter_linked_pages(first_page)

    def _initial_params(self) -> dict[str, str | int]:
        params: dict[str, str | int] = {"limit": PAGE_SIZE, "sort": "report_date:asc"}
        if self._api_key is not None:
            params["api_key"] = self._api_key
        return params

    def _iter_linked_pages(self, first_page: _Page) -> Iterator[SourceFoodEnforcementRecord]:
        page = first_page
        observed = 0
        seen_next_urls: set[str] = set()

        while True:
            yield from page.records
            observed += len(page.records)
            next_url = page.next_url
            if next_url is None:
                total = page.metadata.total_matches if page.metadata is not None else None
                if total is not None and observed < total:
                    raise OpenFDAPaginationError(
                        "openFDA ended search-after pagination before its reported total"
                    )
                return
            if next_url in seen_next_urls:
                raise OpenFDAPaginationError("openFDA returned a repeated pagination link")
            seen_next_urls.add(next_url)
            page = self._fetch_page(next_url)

    def _iter_date_partitions(
        self, earliest_report_date: date, latest_report_date: date
    ) -> Iterator[SourceFoodEnforcementRecord]:
        partition_start = earliest_report_date
        while partition_start <= latest_report_date:
            partition_end = min(date(partition_start.year, 12, 31), latest_report_date)
            yield from self._iter_partition(partition_start, partition_end)
            partition_start = partition_end + timedelta(days=1)

    def _iter_partition(self, start: date, end: date) -> Iterator[SourceFoodEnforcementRecord]:
        first_page = self._fetch_page(self._partition_params(start, end))
        total = first_page.metadata.total_matches if first_page.metadata is not None else None
        if total is not None and total > MAX_SKIP_RESULT_WINDOW and first_page.next_url is None:
            if start == end:
                raise OpenFDAPaginationError(
                    "a one-day date partition exceeds the supported skip result window"
                )
            midpoint = start + timedelta(days=(end - start).days // 2)
            yield from self._iter_partition(start, midpoint)
            yield from self._iter_partition(midpoint + timedelta(days=1), end)
            return

        if first_page.next_url is not None:
            yield from self._iter_linked_pages(first_page)
            return

        yield from first_page.records
        yield from self._iter_skip_pages(start, end, first_page, total)

    def _iter_skip_pages(
        self, start: date, end: date, first_page: _Page, total: int | None
    ) -> Iterator[SourceFoodEnforcementRecord]:
        offset = len(first_page.records)
        while len(first_page.records) == PAGE_SIZE and (total is None or offset < total):
            if offset >= MAX_SKIP_RESULT_WINDOW:
                raise OpenFDAPaginationError(
                    "openFDA date partition reached the supported skip result window"
                )
            page = self._fetch_page(self._partition_params(start, end, skip=offset))
            yield from page.records
            if not page.records:
                return
            offset += len(page.records)
            if len(page.records) < PAGE_SIZE:
                return

    def _partition_params(
        self, start: date, end: date, *, skip: int | None = None
    ) -> dict[str, str | int]:
        params = self._initial_params()
        params["search"] = f"report_date:[{start:%Y%m%d}+TO+{end:%Y%m%d}]"
        if skip is not None:
            params["skip"] = skip
        return params

    def _fetch_page(self, request: str | Mapping[str, str | int]) -> _Page:
        response = self._request(request)
        try:
            payload = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OpenFDAResponseError("openFDA returned malformed JSON") from error

        if not isinstance(payload, dict):
            raise OpenFDAResponseError("openFDA response must be a JSON object")
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise OpenFDAResponseError("openFDA response is missing a results list")

        raw_metadata = payload.get("meta")
        if raw_metadata is not None and not isinstance(raw_metadata, dict):
            raise OpenFDAResponseError("openFDA response meta must be an object when present")
        try:
            metadata = OpenFDAMetadata.model_validate(raw_metadata) if raw_metadata else None
        except ValidationError as error:
            message = "openFDA response metadata has an unexpected schema"
            raise OpenFDAResponseError(message) from error

        records: list[SourceFoodEnforcementRecord] = []
        for raw_record in raw_results:
            if not _is_json_mapping(raw_record):
                raise OpenFDAResponseError("openFDA results must contain JSON objects")
            try:
                parsed = FoodEnforcementRecord.model_validate(raw_record)
            except ValidationError as error:
                raise OpenFDAResponseError("openFDA record has an unexpected schema") from error
            records.append(SourceFoodEnforcementRecord(parsed=parsed, raw=dict(raw_record)))

        if self.last_metadata is None and metadata is not None:
            self.last_metadata = metadata
        return _Page(
            records=tuple(records),
            metadata=metadata,
            next_url=_next_link(response.headers.get("Link")),
        )

    def _request(self, request: str | Mapping[str, str | int]) -> httpx.Response:
        for attempt in range(self._options.max_retries + 1):
            try:
                if isinstance(request, Mapping):
                    response = self._client.get(ENDPOINT, params=request)
                else:
                    response = self._client.get(request)
            except httpx.TransportError as error:
                if attempt == self._options.max_retries:
                    raise OpenFDARequestError("openFDA request failed after retries") from error
                self._sleep(self._retry_delay_seconds(attempt, retry_after=None))
                continue

            if response.status_code in _TRANSIENT_STATUS_CODES:
                if attempt == self._options.max_retries:
                    raise OpenFDARequestError(
                        f"openFDA returned transient HTTP {response.status_code} after retries"
                    )
                self._logger.warning(
                    "openfda_retry status_code=%s attempt=%s", response.status_code, attempt + 1
                )
                self._sleep(
                    self._retry_delay_seconds(attempt, response.headers.get("Retry-After"))
                )
                continue
            if response.is_error:
                message = f"openFDA returned non-retriable HTTP {response.status_code}"
                raise OpenFDARequestError(message)
            return response

        raise AssertionError("unreachable retry state")

    def _retry_delay_seconds(self, attempt: int, retry_after: str | None) -> float:
        parsed_retry_after = _parse_retry_after(retry_after)
        if parsed_retry_after is not None:
            return parsed_retry_after
        backoff = self._options.retry_base_delay_seconds * (2**attempt)
        jitter: float = self._random_value() * self._options.retry_base_delay_seconds
        return backoff + jitter


def _requires_more_pages(page: _Page) -> bool:
    """Determine whether an initial no-link response needs bounded fallback pagination."""
    total = page.metadata.total_matches if page.metadata is not None else None
    return (total is not None and total > len(page.records)) or len(page.records) == PAGE_SIZE


def _next_link(link_header: str | None) -> str | None:
    """Extract and validate the trusted `rel=next` URL from an HTTP Link header."""
    if link_header is None:
        return None
    for part in link_header.split(","):
        pieces = [piece.strip() for piece in part.split(";")]
        if len(pieces) < 2 or not pieces[0].startswith("<") or not pieces[0].endswith(">"):
            continue
        if any(piece.casefold() in {"rel=next", 'rel="next"'} for piece in pieces[1:]):
            next_url = pieces[0][1:-1]
            parsed = urlparse(next_url)
            if parsed.scheme != "https" or parsed.netloc != "api.fda.gov":
                raise OpenFDAPaginationError("openFDA returned an untrusted pagination link")
            return next_url
    return None


def _parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After seconds or HTTP date, retaining only non-negative delays."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            parsed_date = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed_date, datetime):
            return None
        return max(0.0, (parsed_date - datetime.now(parsed_date.tzinfo)).total_seconds())
    return max(0.0, seconds)


def _is_json_mapping(value: object) -> TypeGuard[JsonMapping]:
    """Narrow decoded JSON values to mapping objects with string keys."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return False
    return all(_is_json_value(item) for item in value.values())


def _is_json_value(value: object) -> bool:
    """Check whether a decoded value can be preserved in a JSON source mapping."""
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    return _is_json_mapping(value)
