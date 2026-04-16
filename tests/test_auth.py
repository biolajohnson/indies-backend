from tests.conftest import make_filmmaker, auth_headers


class TestRegister:
    def test_success(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "secret123",
        })
        assert res.status_code == 201
        data = res.get_json()
        assert "access_token" in data
        assert data["filmmaker"]["email"] == "jane@example.com"
        assert data["filmmaker"]["name"] == "Jane Doe"
        assert "password_hash" not in data["filmmaker"]

    def test_missing_name(self, client):
        res = client.post("/api/auth/register", json={
            "email": "jane@example.com",
            "password": "secret123",
        })
        assert res.status_code == 400
        assert "name" in res.get_json()["error"]

    def test_missing_email(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Jane",
            "password": "secret123",
        })
        assert res.status_code == 400

    def test_missing_password(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Jane",
            "email": "jane@example.com",
        })
        assert res.status_code == 400

    def test_duplicate_email(self, client):
        make_filmmaker(client)
        res = client.post("/api/auth/register", json={
            "name": "Other Person",
            "email": "test@example.com",
            "password": "abc123",
        })
        assert res.status_code == 409
        assert "already exists" in res.get_json()["error"]

    def test_email_stored_lowercase(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Jane",
            "email": "JANE@EXAMPLE.COM",
            "password": "secret",
        })
        assert res.status_code == 201
        assert res.get_json()["filmmaker"]["email"] == "jane@example.com"

    def test_optional_fields_saved(self, client):
        res = client.post("/api/auth/register", json={
            "name": "Jane",
            "email": "jane@example.com",
            "password": "secret",
            "bio": "Director",
            "nationality": "Nigerian",
            "website": "https://jane.com",
            "social_links": {"instagram": "@jane"},
        })
        data = res.get_json()["filmmaker"]
        assert data["bio"] == "Director"
        assert data["nationality"] == "Nigerian"
        assert data["social_links"]["instagram"] == "@jane"


class TestLogin:
    def test_success(self, client):
        make_filmmaker(client)
        res = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert res.status_code == 200
        assert "access_token" in res.get_json()

    def test_wrong_password(self, client):
        make_filmmaker(client)
        res = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert res.status_code == 401

    def test_unknown_email(self, client):
        res = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "password123",
        })
        assert res.status_code == 401

    def test_missing_fields(self, client):
        res = client.post("/api/auth/login", json={"email": "test@example.com"})
        assert res.status_code == 400

    def test_case_insensitive_email(self, client):
        make_filmmaker(client, email="test@example.com")
        res = client.post("/api/auth/login", json={
            "email": "TEST@EXAMPLE.COM",
            "password": "password123",
        })
        assert res.status_code == 200


class TestMe:
    def test_get_profile(self, client):
        filmmaker, token = make_filmmaker(client)
        res = client.get("/api/auth/me", headers=auth_headers(token))
        assert res.status_code == 200
        data = res.get_json()
        assert data["id"] == filmmaker["id"]
        assert "email" in data  # private field included for own profile

    def test_unauthenticated(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_update_profile(self, client):
        _, token = make_filmmaker(client)
        res = client.patch("/api/auth/me", json={"bio": "Updated bio"}, headers=auth_headers(token))
        assert res.status_code == 200
        assert res.get_json()["bio"] == "Updated bio"

    def test_update_profile_unauthenticated(self, client):
        res = client.patch("/api/auth/me", json={"bio": "x"})
        assert res.status_code == 401

    def test_update_ignores_disallowed_fields(self, client):
        filmmaker, token = make_filmmaker(client)
        original_email = filmmaker["email"]
        res = client.patch("/api/auth/me", json={"email": "hacked@evil.com"}, headers=auth_headers(token))
        # email is not in allowed_fields, so it should be silently ignored
        assert res.status_code == 200
        assert res.get_json()["email"] == original_email
