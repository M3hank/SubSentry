"""Source runner tests using in-memory fake sources."""

from subsentry.sources import _run_one, run_all_sources


class FakeSource:
    description = "fake"
    url = ""

    def __init__(self, name, results):
        self.name = name
        self.results = results
        self.calls = 0

    def is_available(self):
        return True

    def enumerate(self, domain):
        self.calls += 1
        return set(self.results)


class FlakySource(FakeSource):
    def enumerate(self, domain):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return set(self.results)


def test_run_one_retries_then_succeeds():
    source = FlakySource("flaky", {"a.test"})
    results, error, _, attempts = _run_one(source, "test", retries=1, backoff=0)
    assert error is None
    assert results == {"a.test"}
    assert attempts == 2


def test_run_one_gives_up_after_retries():
    source = FakeSource("broken", set())

    def explode(_domain):
        raise RuntimeError("nope")

    source.enumerate = explode
    results, error, _, attempts = _run_one(source, "test", retries=2, backoff=0)
    assert results == set()
    assert isinstance(error, RuntimeError)
    assert attempts == 3


def test_run_all_sources_aggregates_and_sorts():
    a = FakeSource("zeta", {"a.test", "b.test"})
    b = FakeSource("alpha", {"b.test", "c.test"})
    aggregated, used, per_source = run_all_sources(
        "test", sources=[a, b], workers=2, retries=0, backoff=0
    )
    assert aggregated == {"a.test", "b.test", "c.test"}
    assert used == ["alpha", "zeta"]
    assert per_source["zeta"] == {"a.test", "b.test"}


def test_failed_source_does_not_kill_the_run():
    good = FakeSource("good", {"a.test"})
    bad = FakeSource("bad", set())
    bad.enumerate = lambda _d: (_ for _ in ()).throw(RuntimeError("boom"))

    aggregated, used, per_source = run_all_sources(
        "test", sources=[good, bad], workers=2, retries=0, backoff=0
    )
    assert aggregated == {"a.test"}
    assert used == ["good"]
    assert per_source["bad"] == set()


def test_run_all_sources_without_sources_returns_empty():
    assert run_all_sources("test", sources=[]) == (set(), [], {})
