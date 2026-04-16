import pytest
from app import create_app
from extensions import db as _db


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function", autouse=True)
def clean_db(app):
    """Roll back every table between tests."""
    with app.app_context():
        yield
        _db.session.remove()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


# --- Helpers ---

def make_filmmaker(client, name="Test Filmmaker", email="test@example.com", password="password123"):
    res = client.post("/api/auth/register", json={
        "name": name,
        "email": email,
        "password": password,
    })
    assert res.status_code == 201
    data = res.get_json()
    return data["filmmaker"], data["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_active_campaign(client, token, filmmaker_id, **overrides):
    payload = {
        "title": "Test Campaign",
        "description": "A great indie film",
        "goal_amount": 10000,
        **overrides,
    }
    res = client.post("/api/campaigns/", json=payload, headers=auth_headers(token))
    assert res.status_code == 201
    campaign = res.get_json()
    # Patch status to active so donations work
    res2 = client.patch(
        f"/api/campaigns/{campaign['id']}",
        json={"status": "active"},
        headers=auth_headers(token),
    )
    assert res2.status_code == 200
    return res2.get_json()
