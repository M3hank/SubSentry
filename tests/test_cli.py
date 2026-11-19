"""End-to-end CLI tests with the network layer replaced."""

import json

import pytest

from subsentry import cli


@pytest.fixture()
def fake_sources(monkeypatch):
    """Replace run_all_sources with a controllable fake."""

    state = {"results": {"a.example.com"}, "sources": ["fake"]}

    def fake_run(domain, **kwargs):
        return set(state["results"]), list(state["sources"]), {
            name: set(state["results"]) for name in state["sources"]
        }

    monkeypatch.setattr(cli, "run_all_sources", fake_run)
    return state


def _db_arg(tmp_path):
    return str(tmp_path / "cli.db")


def test_init_and_scan_flow(tmp_path, fake_sources, capsys):
    db = _db_arg(tmp_path)

    assert cli.main(["init", "example.com", "--db", db, "-q"]) == 0

    fake_sources["results"] = {"a.example.com", "new.example.com"}
    json_path = tmp_path / "scan.json"
    code = cli.main(
        ["scan", "example.com", "--db", db, "--json", str(json_path), "--fail-on-new", "-q"]
    )

    assert code == 2
    payload = json.loads(json_path.read_text())
    assert payload["domain"] == "example.com"
    assert payload["new"] == ["new.example.com"]
    assert payload["new_count"] == 1
    assert payload["sources"] == ["fake"]


def test_scan_without_baseline_fails(tmp_path, fake_sources):
    code = cli.main(["scan", "example.com", "--db", _db_arg(tmp_path), "-q"])
    assert code == 1


def test_scan_with_no_new_subdomains_returns_zero(tmp_path, fake_sources):
    db = _db_arg(tmp_path)
    assert cli.main(["init", "example.com", "--db", db, "-q"]) == 0
    assert cli.main(["scan", "example.com", "--db", db, "--fail-on-new", "-q"]) == 0


def test_list_json(tmp_path, fake_sources, capsys):
    db = _db_arg(tmp_path)
    cli.main(["init", "example.com", "--db", db, "-q"])
    capsys.readouterr()

    assert cli.main(["list", "example.com", "--db", db, "--json", "-q"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["subdomain"] == "a.example.com"


def test_export_and_import(tmp_path, fake_sources):
    db = _db_arg(tmp_path)
    cli.main(["init", "example.com", "--db", db, "-q"])

    out = tmp_path / "export.json"
    assert cli.main(["export", "example.com", "--db", db, "-o", str(out), "-q"]) == 0
    assert out.exists()

    other_db = str(tmp_path / "other.db")
    assert cli.main(["import", str(out), "--db", other_db, "-q"]) == 0
    assert cli.main(["list", "example.com", "--db", other_db, "--json", "-q"]) == 0


def test_monitor_stops_after_max_scans(tmp_path, fake_sources):
    db = _db_arg(tmp_path)
    cli.main(["init", "example.com", "--db", db, "-q"])

    snapshots = tmp_path / "snapshots"
    code = cli.main(
        ["monitor", "example.com", "--db", db, "-q", "-i", "30",
         "--max-scans", "1", "--json-dir", str(snapshots)]
    )
    assert code == 0
    assert len(list(snapshots.glob("*.json"))) == 1


def test_stats_requires_data(tmp_path):
    assert cli.main(["stats", "--db", _db_arg(tmp_path), "-q"]) == 1


def test_invalid_domain_exits_with_error(tmp_path):
    assert cli.main(["init", "not_a_domain", "--db", _db_arg(tmp_path), "-q"]) == 1


def test_version_flag():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
