"""Public acceptance tests for content negotiation."""

from __future__ import annotations

import pytest

from conneg import conneg_batch, negotiate, parse_accept, parse_q, sort_types


def test_parse_accept_reports_declared_ranges():
    parsed = parse_accept("text/html;q=0.5, text/html;q=0.9, application/json;q=0.2")

    assert len(parsed) == 2
    assert [entry["type"] for entry in parsed] == ["text/html", "application/json"]
    assert [entry["q"] for entry in parsed] == [0.5, 0.2]


def test_parse_q_accepts_fraction_and_rejects_overflow():
    assert parse_q("0.25") == 0.25
    with pytest.raises(ValueError):
        parse_q("1.25")


def test_sort_types_prefers_specific_range_on_equal_weight():
    types = [
        {"type": "text/*", "q": 0.4, "order": 0},
        {"type": "application/json", "q": 0.4, "order": 1},
    ]

    assert [entry["type"] for entry in sort_types(types)] == [
        "application/json",
        "text/*",
    ]


def test_negotiate_picks_highest_weight():
    header = "application/json;q=0.1, text/html;q=0.8"

    assert negotiate(header, ["text/html", "application/json"]) == "text/html"


def test_batch_negotiates_each_request_independently():
    requests = {"left": "text/html", "right": "application/json"}

    results = conneg_batch(requests, ["text/html", "application/json"])

    assert results == {"left": "text/html", "right": "application/json"}