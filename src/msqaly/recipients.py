"""Resolve recipient identity without conflating organizations that share a name."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlsplit

RecipientKey = tuple[str, str]


def recipient_key(recipient: dict) -> RecipientKey:
    """Stable (public name, website) identity from the verbatim gift snapshot.

    Scheme, a leading www., and a final slash do not distinguish websites.
    Paths and queries remain significant. A snapshot recipient without a
    website keeps an empty website component; the index still rejects collisions.
    """
    name, link = recipient.get("name"), recipient.get("link")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("recipient needs a nonempty name")
    if link in (None, ""):
        return name.strip(), ""
    if not isinstance(link, str):
        raise ValueError(f"recipient {name!r} needs a string link")
    if not link.strip():
        return name.strip(), ""
    url = urlsplit(link.strip() if "://" in link else "https://" + link.strip())
    host = url.netloc.lower().removeprefix("www.")
    if not host:
        raise ValueError(f"invalid recipient link: {link!r}")
    website = host + url.path.rstrip("/")
    if url.query:
        website += "?" + url.query
    return name.strip(), website


class RecipientIndex:
    """Resolve legacy unique-name rows and require a website for namesakes."""

    def __init__(self, organizations: list[dict]):
        self.by_key: dict[RecipientKey, dict] = {}
        self.by_name: dict[str, list[RecipientKey]] = defaultdict(list)
        for org in organizations:
            key = recipient_key(org)
            if key in self.by_key:
                raise ValueError(f"duplicate recipient identity: {key!r}")
            self.by_key[key] = org
            self.by_name[key[0]].append(key)

    def resolve(self, record: dict) -> RecipientKey:
        """Reject unknown, ambiguous, or mismatched identities."""
        if "link" in record:
            key = recipient_key(record)
            if key not in self.by_key:
                raise ValueError(f"unknown recipient identity: {key!r}")
            return key
        name = record.get("name")
        candidates = self.by_name.get(name, [])
        if not candidates:
            raise ValueError(f"unknown recipient name: {name!r}")
        if len(candidates) != 1:
            raise ValueError(f"ambiguous recipient name {name!r}; include link")
        return candidates[0]

    def records(self, rows: list[dict], *, label: str) -> dict[RecipientKey, dict]:
        """Index one layer of records; duplicate identities are always errors."""
        result = {}
        for row in rows:
            key = self.resolve(row)
            if key in result:
                raise ValueError(f"duplicate {label} recipient identity: {key!r}")
            result[key] = row
        return result
