"""Mocked contract tests for openFDA pagination, retries, and source preservation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import httpx
import pytest

from recallready.data.openfda_client import (
    ENDPOINT,
    OpenFDAClient,
    OpenFDAClientOptions,
    OpenFDAPaginationError,
    OpenFDAResponseError,
)


def _payload(
    records: list[dict[str, object]], *, total: int | None = None, last_updated: str = "2026-07-29"
) -> dict[str, object]:
    metadata: dict[str, object] = {"last_updated": last_updated}
    if total is not None:
        metadata["results"] = {"total": total}
    return {"meta": metadata, "results": records}


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "recall_number": "F-001-2020",
        "event_id": "12345",
        "product_description": "Example food",
        "reason_for_recall": "Example reason",
        "report_date": "20200101",
        "classification": "Class II",
    }
    record.update(overrides)
    return record


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    api_key: str | None = None,
    sleeps: list[float] | None = None,
) -> OpenFDAClient:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenFDAClient(
        api_key=api_key,
        client=http_client,
        options=OpenFDAClientOptions(max_retries=2, retry_base_delay_seconds=0.5),
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
        random_value=lambda: 0.0,
    )


def test_single_page_success_preserves_raw_record_and_metadata() -> None:
    """A single response retains source fields and safe metadata."""
    source = _record(extra_future_field="retained")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(f"{ENDPOINT}?limit=1000&sort=report_date%3Aasc")
        assert request.headers["User-Agent"].startswith("RecallReady/")
        return httpx.Response(200, json=_payload([source], total=1), request=request)

    client = _client(handler)
    records = list(client.iter_records())

    assert records[0].raw == source
    assert records[0].parsed.recall_number == "F-001-2020"
    assert records[0].parsed.model_extra == {"extra_future_field": "retained"}
    assert client.last_metadata is not None
    assert client.last_metadata.total_matches == 1
    assert client.last_metadata.last_updated == "2026-07-29"


def test_multi_page_search_after_success() -> None:
    """The preferred Link/search-after flow returns all pages in deterministic order."""
    next_url = f"{ENDPOINT}?limit=1000&sort=report_date%3Aasc&search_after=token"

    def handler(request: httpx.Request) -> httpx.Response:
        if "search_after" not in request.url.params:
            return httpx.Response(
                200,
                json=_payload([_record(recall_number="F-001")], total=2),
                headers={"Link": f'<{next_url}>; rel="next"'},
                request=request,
            )
        return httpx.Response(
            200, json=_payload([_record(recall_number="F-002")], total=2), request=request
        )

    records = list(_client(handler).iter_records())

    assert [record.parsed.recall_number for record in records] == ["F-001", "F-002"]


def test_date_partition_fallback_when_search_after_is_unavailable() -> None:
    """A no-Link initial response restarts via a bounded report-date partition."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "search" not in request.url.params:
            return httpx.Response(200, json=_payload([_record()], total=2), request=request)
        return httpx.Response(
            200,
            json=_payload(
                [_record(recall_number="F-PART-1"), _record(recall_number="F-PART-2")], total=2
            ),
            request=request,
        )

    records = list(
        _client(handler).iter_records(
            earliest_report_date=date(2004, 1, 1), latest_report_date=date(2004, 12, 31)
        )
    )

    assert [record.parsed.recall_number for record in records] == ["F-PART-1", "F-PART-2"]
    assert any("search" in request.url.params for request in requests)


def test_retry_after_is_respected_for_rate_limit() -> None:
    """429 responses use the supplied Retry-After duration without body logging."""
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, request=request)
        return httpx.Response(200, json=_payload([_record()], total=1), request=request)

    records = list(_client(handler, sleeps=sleeps).iter_records())

    assert len(records) == 1
    assert sleeps == [2.0]


def test_transient_500_retries_with_exponential_backoff() -> None:
    """A transient server error retries then succeeds with deterministic test jitter."""
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, request=request)
        return httpx.Response(200, json=_payload([_record()], total=1), request=request)

    assert len(list(_client(handler, sleeps=sleeps).iter_records())) == 1
    assert sleeps == [0.5]


def test_malformed_response_is_rejected() -> None:
    """Invalid JSON cannot become silently incomplete data."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not-json", request=request)

    with pytest.raises(OpenFDAResponseError, match="malformed JSON"):
        list(_client(handler).iter_records())


def test_repeated_pagination_link_is_rejected() -> None:
    """Repeated next URLs fail before an unbounded client loop can occur."""
    next_url = f"{ENDPOINT}?limit=1000&sort=report_date%3Aasc&search_after=same"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_payload(
                [_record(recall_number=f"F-{request.url.params.get('search_after', 'first')}")],
                total=3,
            ),
            headers={"Link": f'<{next_url}>; rel="next"'},
            request=request,
        )

    with pytest.raises(OpenFDAPaginationError, match="repeated pagination link"):
        list(_client(handler).iter_records())


def test_pre_2012_missing_fields_are_preserved_as_none() -> None:
    """Historical sparse records keep absent fields null rather than invented."""
    legacy = {"recall_number": "F-LEGACY", "report_date": "20050101"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload([legacy], total=1), request=request)

    record = next(_client(handler).iter_records())

    assert record.parsed.product_description is None
    assert record.parsed.center_classification_date is None
    assert record.parsed.event_id is None
    assert record.raw == legacy


@pytest.mark.parametrize("api_key", [None, "test-key"])
def test_api_key_is_optional_and_sent_only_when_configured(api_key: str | None) -> None:
    """The optional key is present in requests only when configuration supplies it."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("api_key") == api_key
        return httpx.Response(200, json=_payload([_record()], total=1), request=request)

    assert len(list(_client(handler, api_key=api_key).iter_records())) == 1
