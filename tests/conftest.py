import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database as db
from app import app as flask_app


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Every test gets its own fresh SQLite database in a temp directory."""
    db_path = str(tmp_path / "test_pharmacy.db")
    monkeypatch.setattr(db, "DATABASE", db_path)
    db.init_db()
    yield db_path


@pytest.fixture()
def app():
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_customer():
    """Create and return a sample customer dict."""
    cid = db.add_customer("John Doe", phone="555-0100", credit_limit=1000.00)
    return db.get_customer(cid)


@pytest.fixture()
def sample_product():
    pid = db.add_product("Aspirin", 9.99, category="Pain Relief")
    return db.get_product(pid)


@pytest.fixture()
def sample_user():
    uid = db.add_user("testclerk", "password123", "Test Clerk", "clerk")
    return db.get_user(uid)


@pytest.fixture()
def customer_with_debt(sample_customer):
    """Customer who already owes $25.98 (2 items)."""
    items = [
        {"product_name": "Ibuprofen", "price": 12.99, "quantity": 1},
        {"product_name": "Bandages", "price": 12.99, "quantity": 1},
    ]
    db.add_debt(sample_customer["id"], items)
    return db.get_customer(sample_customer["id"])


@pytest.fixture()
def sample_donation():
    did = db.add_donation(500.00, donor_name="Charity Fund", notes="Monthly donation")
    return db.get_donation(did)
