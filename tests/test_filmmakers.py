from tests.conftest import make_filmmaker


class TestListFilmmakers:
    def test_empty(self, client):
        res = client.get("/api/filmmakers/")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_returns_all(self, client):
        make_filmmaker(client, name="Alice", email="alice@example.com")
        make_filmmaker(client, name="Bob", email="bob@example.com")
        res = client.get("/api/filmmakers/")
        assert res.status_code == 200
        data = res.get_json()
        assert len(data) == 2
        names = {f["name"] for f in data}
        assert names == {"Alice", "Bob"}

    def test_no_private_fields(self, client):
        make_filmmaker(client)
        res = client.get("/api/filmmakers/")
        filmmaker = res.get_json()[0]
        assert "email" not in filmmaker
        assert "stripe_account_id" not in filmmaker
        assert "password_hash" not in filmmaker


class TestGetFilmmaker:
    def test_found(self, client):
        filmmaker, _ = make_filmmaker(client, name="Alice", email="alice@example.com")
        res = client.get(f"/api/filmmakers/{filmmaker['id']}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["name"] == "Alice"
        assert "campaigns" in data

    def test_not_found(self, client):
        res = client.get("/api/filmmakers/9999")
        assert res.status_code == 404
        assert "error" in res.get_json()

    def test_no_private_fields(self, client):
        filmmaker, _ = make_filmmaker(client)
        res = client.get(f"/api/filmmakers/{filmmaker['id']}")
        data = res.get_json()
        assert "email" not in data
        assert "stripe_account_id" not in data
