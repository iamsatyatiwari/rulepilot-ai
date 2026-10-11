import pytest

from app.data import create_synthetic_dataset


@pytest.fixture(scope="session")
def synthetic_transactions():
    return create_synthetic_dataset()
