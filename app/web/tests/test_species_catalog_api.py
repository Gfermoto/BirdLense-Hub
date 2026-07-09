"""GET /api/ui/species scope + meta (#catalog cards)."""

from __future__ import annotations


def test_species_allowlist_scope_returns_list(client):
    r = client.get(
        "/api/ui/species",
        query_string={"exclude_suspects": 1, "scope": "allowlist"},
    )
    assert r.status_code == 200
    assert isinstance(r.json, list)
    for item in r.json[:3]:
        assert "id" in item and "name" in item
        assert "catalog_card_incomplete" in item


def test_species_meta_payload(client):
    r = client.get(
        "/api/ui/species",
        query_string={"exclude_suspects": 1, "scope": "allowlist", "meta": 1},
    )
    assert r.status_code == 200
    body = r.json
    assert isinstance(body, dict)
    items = body.get("items")
    assert isinstance(items, list)
    meta = body.get("meta") or {}
    assert "allowlist_total" in meta
    assert "db_species_total" in meta
    if meta.get("allowlist_total"):
        assert len(items) <= int(meta["allowlist_total"])
        assert int(meta["listed_allowlist"]) == len(items)
