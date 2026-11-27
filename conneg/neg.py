"""Content negotiation primitives.

The module turns an Accept header into an ordered list of media ranges, ranks
those ranges, matches them against the representations a server can produce and
negotiates one representation per request.
"""

from __future__ import annotations

__all__ = [
    "parse_accept",
    "parse_q",
    "sort_types",
    "match_type",
    "negotiate",
    "check_zero_weight",
    "validate_header",
    "conneg_batch",
]


def _split(media_range):
    """Split a media range into lower-case ``(type, subtype)`` parts."""

    text = str(media_range).strip().lower()
    if "/" not in text:
        return text, ""
    main, sub = text.split("/", 1)
    return main, sub


def _specificity(media_range):
    """Return 2 for concrete types, 1 for type wildcards, 0 for full wildcards."""

    main, sub = _split(media_range)
    if main == "*" and sub == "*":
        return 0
    if sub == "*":
        return 1
    return 2


def _is_wildcard(media_range):
    return _specificity(media_range) < 2


def _offered_list(offered):
    """Normalise the server's offered representations to lower-case strings."""

    if isinstance(offered, str):
        items = [offered]
    else:
        items = list(offered or [])
    result = []
    for item in items:
        text = str(item).strip().lower()
        if text:
            result.append(text)
    return result


def _default_result(policy, offered):
    """Return the policy default when it is actually offered, else a blank string."""

    policy = policy or {}
    default = policy.get("default")
    if not default:
        return ""
    default = str(default).strip().lower()
    if default in offered:
        return default
    return ""


def parse_q(value):
    """Parse a q parameter value into a float.

    A bare number is expected.  Anything that is not a number is rejected with
    ``ValueError``.
    """

    text = str(value).strip()
    if not text:
        raise ValueError("empty weight")
    try:
        return float(text)
    except ValueError:
        raise ValueError("invalid weight: %r" % (value,)) from None


def parse_accept(header):
    """Parse an Accept header into ``{"type", "q", "order"}`` mappings."""

    text = "" if header is None else str(header)
    entries = []
    for chunk in text.split(","):
        part = chunk.strip()
        if not part:
            continue
        segments = [segment.strip() for segment in part.split(";")]
        media = segments[0].lower()
        if not media or "/" not in media:
            continue
        weight = 1.0
        for segment in segments[1:]:
            if segment.lower().startswith("q="):
                weight = parse_q(segment[2:])
        entries.append({"type": media, "q": weight, "order": len(entries)})
    return entries


def sort_types(types):
    """Return a new list ordered by descending weight."""

    items = list(types or [])
    return sorted(items, key=lambda entry: -float(entry.get("q", 1.0)))


def match_type(candidate, offered):
    """Return whether a client media range can be satisfied by an offered type."""

    c_main, c_sub = _split(candidate)
    o_main, o_sub = _split(offered)
    if not c_main or not o_main:
        return False
    if c_main != "*" and o_main != "*" and c_main != o_main:
        return False
    if c_sub != "*" and o_sub != "*" and c_sub != o_sub:
        return False
    return True


def negotiate(accept, offered, policy=None):
    """Choose one of the offered representations for a single request."""

    parsed = parse_accept(accept)
    offers = _offered_list(offered)
    if not parsed or not offers:
        return _default_result(policy, offers)

    def pick(pool):
        for entry in pool:
            for offer in offers:
                if match_type(entry["type"], offer):
                    return entry["type"]
        return None

    chosen = pick([entry for entry in parsed if entry["q"] > 0.0])
    if chosen is None:
        chosen = pick(parsed)
    if chosen is None:
        return _default_result(policy, offers)
    return chosen


def check_zero_weight(types):
    """Return the media ranges that are explicitly rejected by weight."""

    rejected = []
    for item in types or []:
        weight = float(item.get("q", 1.0))
        if weight < 0.0:
            rejected.append(item.get("type", ""))
    return rejected


def validate_header(header):
    """Return a list of textual problems found in an Accept header."""

    problems = []
    text = "" if header is None else str(header)
    if not text.strip():
        return ["empty header"]
    seen = set()
    for chunk in text.split(","):
        part = chunk.strip()
        if not part:
            problems.append("empty media range")
            continue
        segments = [segment.strip() for segment in part.split(";")]
        media = segments[0].lower()
        if not media or "/" not in media:
            problems.append("invalid media range: %s" % segments[0])
            continue
        if media in seen:
            problems.append("duplicate media type: %s" % media)
        seen.add(media)
        for segment in segments[1:]:
            if not segment.lower().startswith("q="):
                continue
            raw = segment[2:].strip()
            try:
                float(raw)
            except ValueError:
                problems.append("invalid weight for %s: %s" % (media, raw))
    return problems


def conneg_batch(requests, offered, policy=None):
    """Negotiate a mapping of request name to Accept header."""

    results = {}
    first = None
    for key, header in _pairs(requests):
        if first is None:
            first = negotiate(header, offered, policy)
        results[key] = first
    return results


def _pairs(requests):
    if isinstance(requests, dict):
        return list(requests.items())
    return [(str(index), item) for index, item in enumerate(requests or [])]