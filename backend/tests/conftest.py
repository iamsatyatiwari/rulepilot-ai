import pytest

from app.data import create_synthetic_dataset


@pytest.fixture(scope="session")
def synthetic_transactions():
    return create_synthetic_dataset()


@pytest.fixture(autouse=True)
def no_network_feeds(monkeypatch):
    """Tests never fetch public feeds; feed tests enable them with a fake fetcher."""
    import app.intel.feeds as feeds

    def refuse(url):
        raise AssertionError(f"tests must not fetch {url}")

    monkeypatch.setenv("RULEPILOT_FEEDS_ENABLED", "false")
    monkeypatch.setattr(feeds, "http_fetch", refuse)
