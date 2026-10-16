import pytest

import app.intel.feeds as feeds
from app.intel.feeds import FeedStore, advisory_id_for, page_text, parse_feed
from app.intel.feeds import http_fetch as real_http_fetch  # bound before the no-network fixture patches it
from app.storage import LocalJsonBackend
from test_transactions import client, store  # noqa: F401 (fixtures)

RSS = b"""<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>IC3.gov News</title>
<item><title>Scammers Use Gift Card Testing Against Retailers</title><link>https://www.ic3.gov/PSA/2026/PSA261016</link>
<pubDate>Fri, 16 Oct 2026 09:00:00 -04:00</pubDate><guid isPermaLink="false">261016</guid></item>
<item><title>FBI Cautions About Threats to Election Workers</title><link>https://www.ic3.gov/PSA/2026/PSA261015</link>
<pubDate>Thu, 15 Oct 2026 09:00:00 -04:00</pubDate><guid isPermaLink="false">261015</guid></item>
<item><title>Off-site link</title><link>https://evil.example/PSA/1</link><guid>x1</guid></item>
</channel></rss>"""
FRAUD_PAGE = (b"<html><body><nav>menu</nav><main><h1>Gift Card Testing</h1><script>track()</script>"
              b"<p>The FBI warns that criminals validate stolen card numbers with many small online payments, "
              b"often several per minute, and repeated declines before larger fraud follows. Retailers and banks "
              b"should watch for bursts of low-value card-not-present payments from new devices.</p></main></body></html>")
OTHER_PAGE = (b"<html><main><p>" + b"Election workers may face threats and harassment in the weeks before the vote. " * 4
              + b"</p></main></html>")


def fake_fetch(calls):
    def fetch(url):
        calls.append(url)
        return {feeds.IC3_FEED: RSS, "https://www.ic3.gov/PSA/2026/PSA261016": FRAUD_PAGE,
                "https://www.ic3.gov/PSA/2026/PSA261015": OTHER_PAGE}[url]
    return fetch


def test_feed_parsing_keeps_only_ic3_links_and_page_text_drops_markup():
    items = parse_feed(RSS)
    assert [item.link for item in items] == ["https://www.ic3.gov/PSA/2026/PSA261016", "https://www.ic3.gov/PSA/2026/PSA261015"]
    assert items[0].published == "2026-10-16" and advisory_id_for(items[0]) == "ic3-261016"
    text = page_text(FRAUD_PAGE)
    assert text.startswith("Gift Card Testing The FBI warns") and "menu" not in text and "track()" not in text


def test_refresh_stores_new_fraud_alerts_once_and_skips_others(tmp_path):
    calls = []
    fs = FeedStore(LocalJsonBackend(tmp_path))
    first = fs.refresh(fake_fetch(calls))
    assert first.new_advisories == ["ic3-261016"]
    assert first.skipped_not_fraud == ["FBI Cautions About Threats to Election Workers"]
    advisory = fs.advisories()["ic3-261016"]
    assert advisory.source_type == "government_psa" and "public domain" in advisory.rights_note
    second = fs.refresh(fake_fetch(calls))
    assert second.new_advisories == [] and fs.last_refresh().checked_at == second.checked_at


def test_refresh_reports_network_errors_without_raising(tmp_path):
    def broken(url):
        raise TimeoutError("timed out")
    result = FeedStore(LocalJsonBackend(tmp_path)).refresh(broken)
    assert result.new_advisories == [] and "TimeoutError" in result.errors[0]


def test_the_fetcher_refuses_urls_off_the_allowlist():
    with pytest.raises(ValueError, match="allowlist"):
        real_http_fetch("https://evil.example/PSA/1")
    with pytest.raises(ValueError, match="allowlist"):
        real_http_fetch("https://www.ic3.gov/other-page")


def test_ingestion_fetches_feeds_then_investigates_the_new_alert(client, store, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setenv("RULEPILOT_FEEDS_ENABLED", "true")
    monkeypatch.setenv("RULEPILOT_INGEST_TOKEN", "secret-token")
    monkeypatch.setattr(feeds, "http_fetch", fake_fetch(calls))
    # Curated advisories are already investigated, so the fetched alert is next in line.
    for advisory_id in ("jpm-card-testing", "fbi-ic3-sim-swap-2022"):
        client.post("/api/v1/investigations", json={"advisory_id": advisory_id})
    result = client.post("/api/v1/ingestion/run", headers={"X-RulePilot-Ingest-Token": "secret-token"}).json()
    assert result["feed_refresh"]["new_advisories"] == ["ic3-261016"]
    assert [item["advisory_id"] for item in result["investigated"]] == ["ic3-261016"]
    assert result["investigated"][0]["origin"] == "scheduled"
    listed = [item["advisory_id"] for item in client.get("/api/v1/advisories").json()["items"]]
    assert "ic3-261016" in listed
    status = client.get("/api/v1/feeds/status").json()
    assert status["enabled"] and status["fetched_advisories"] == 1


def test_manual_refresh_has_a_cooldown(client, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setenv("RULEPILOT_FEEDS_ENABLED", "true")
    monkeypatch.setattr(feeds, "http_fetch", fake_fetch(calls))
    first = client.post("/api/v1/feeds/refresh").json()
    count = len(calls)
    again = client.post("/api/v1/feeds/refresh").json()
    assert again["checked_at"] == first["checked_at"] and len(calls) == count
    monkeypatch.setenv("RULEPILOT_FEEDS_ENABLED", "false")
    assert client.post("/api/v1/feeds/refresh").status_code == 503
