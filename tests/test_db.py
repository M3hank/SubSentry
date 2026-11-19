"""Database regression tests."""

import json

from subsentry.db import Database


def test_add_subdomains_reports_new_only_once(db, domain):
    """Regression: the old timestamp comparison double-reported within a second."""
    db.add_domain(domain)
    first = db.add_subdomains(domain, {"a.example.com", "b.example.com"})
    assert first == {"a.example.com", "b.example.com"}

    second = db.add_subdomains(domain, {"a.example.com", "b.example.com"})
    assert second == set()

    third = db.add_subdomains(domain, {"a.example.com", "c.example.com"})
    assert third == {"c.example.com"}
    assert db.get_baseline(domain) == {"a.example.com", "b.example.com", "c.example.com"}


def test_add_subdomains_normalises_and_deduplicates(db, domain):
    db.add_domain(domain)
    new = db.add_subdomains(domain, {"A.Example.com", " a.example.com ", ""})
    assert new == {"a.example.com"}
    assert db.get_baseline(domain) == {"a.example.com"}


def test_add_subdomains_creates_missing_domain(db):
    """A subdomain insert must not create an orphan row."""
    db.add_subdomains("orphan.test", {"x.orphan.test"})
    assert [d["domain"] for d in db.get_domains()] == ["orphan.test"]


def test_scan_history_and_stats(db, domain):
    db.add_domain(domain)
    db.add_subdomains(domain, {"a.example.com", "b.example.com"})
    db.add_scan_record(domain, total_found=2, new_found=2, sources_used=["crt.sh", "subfinder"])
    db.add_scan_record(domain, total_found=3, new_found=1, sources_used=["crt.sh"])

    history = db.get_scan_history(domain)
    assert len(history) == 2
    assert history[0]["sources_used"] == "crt.sh"

    stats = db.get_stats()
    assert stats[0]["domain"] == domain
    assert stats[0]["subdomains"] == 2


def test_export_import_roundtrip(db, domain, tmp_path):
    db.add_domain(domain)
    db.add_subdomains(domain, {"a.example.com"}, source="crt.sh")
    db.add_scan_record(domain, 1, 1, ["crt.sh"])

    payload = db.export_domain(domain)
    assert payload["domain"]["domain"] == domain
    assert payload["subdomains"][0]["subdomain"] == "a.example.com"
    original_first_seen = payload["subdomains"][0]["first_seen"]

    target = Database(tmp_path / "restored.db")
    added, skipped = target.import_domain(payload)

    assert added == 1
    assert skipped == 0
    restored = target.get_subdomains_detail(domain)[0]
    # Metadata must survive a snapshot restore.
    assert restored["source"] == "crt.sh"
    assert restored["first_seen"] == original_first_seen
    assert target.get_baseline(domain) == {"a.example.com"}
    assert len(target.get_scan_history(domain)) == 1


def test_import_does_not_overwrite_existing_metadata(db, domain, tmp_path):
    db.add_domain(domain)
    db.add_subdomains(domain, {"a.example.com"}, source="original")
    payload = {
        "domain": {"domain": domain},
        "subdomains": [{"subdomain": "a.example.com", "source": "snapshot",
                        "first_seen": "2000-01-01T00:00:00+00:00"}],
        "history": [],
    }

    added, skipped = db.import_domain(payload)
    assert (added, skipped) == (0, 1)
    assert db.get_subdomains_detail(domain)[0]["source"] == "original"


def test_export_unknown_domain_returns_none(db):
    assert db.export_domain("nope.test") is None


def test_delete_domain_removes_everything(db, domain):
    db.add_domain(domain)
    db.add_subdomains(domain, {"a.example.com"})
    db.add_scan_record(domain, 1, 1, ["crt.sh"])

    assert db.delete_domain(domain) is True
    assert db.get_baseline(domain) == set()
    assert db.get_scan_history(domain) == []
    assert db.delete_domain(domain) is False


def test_to_json_writes_all_domains(db, domain, tmp_path):
    db.add_domain(domain)
    db.add_subdomains(domain, {"a.example.com"})
    out = tmp_path / "dump.json"

    assert db.to_json(out) == 1
    data = json.loads(out.read_text())
    assert data[0]["domain"]["domain"] == domain
