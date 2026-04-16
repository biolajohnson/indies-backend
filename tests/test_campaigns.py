from tests.conftest import make_filmmaker, auth_headers, make_active_campaign


class TestListCampaigns:
    def test_empty(self, client):
        res = client.get("/api/campaigns/")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_only_active_by_default(self, client):
        filmmaker, token = make_filmmaker(client)
        # draft (default on creation)
        client.post("/api/campaigns/", json={
            "title": "Draft",
            "description": "desc",
            "goal_amount": 5000,
        }, headers=auth_headers(token))
        # active
        make_active_campaign(client, token, filmmaker["id"], title="Active")

        res = client.get("/api/campaigns/")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Active"

    def test_filter_by_status(self, client):
        filmmaker, token = make_filmmaker(client)
        client.post("/api/campaigns/", json={
            "title": "Draft",
            "description": "desc",
            "goal_amount": 5000,
        }, headers=auth_headers(token))

        res = client.get("/api/campaigns/?status=draft")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Draft"

    def test_filter_by_genre(self, client):
        filmmaker, token = make_filmmaker(client)
        make_active_campaign(client, token, filmmaker["id"], title="Sci-Fi Film", genre="sci-fi")
        make_active_campaign(client, token, filmmaker["id"], title="Drama Film", genre="drama")

        res = client.get("/api/campaigns/?genre=sci-fi")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Sci-Fi Film"

    def test_filter_by_filmmaker_id(self, client):
        filmmaker1, token1 = make_filmmaker(client, name="Alice", email="alice@example.com")
        filmmaker2, token2 = make_filmmaker(client, name="Bob", email="bob@example.com")
        make_active_campaign(client, token1, filmmaker1["id"], title="Alice's Film")
        make_active_campaign(client, token2, filmmaker2["id"], title="Bob's Film")

        res = client.get(f"/api/campaigns/?filmmaker_id={filmmaker1['id']}")
        data = res.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Alice's Film"


class TestGetCampaign:
    def test_found(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.get(f"/api/campaigns/{campaign['id']}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["id"] == campaign["id"]
        assert "donations" in data
        assert "updates" in data

    def test_not_found(self, client):
        res = client.get("/api/campaigns/9999")
        assert res.status_code == 404

    def test_includes_filmmaker_info(self, client):
        filmmaker, token = make_filmmaker(client, name="Alice", email="alice@example.com")
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.get(f"/api/campaigns/{campaign['id']}")
        data = res.get_json()
        assert data["filmmaker_name"] == "Alice"


class TestCreateCampaign:
    def test_success(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "New Film",
            "description": "Great story",
            "goal_amount": 20000,
            "genre": "drama",
            "tags": ["indie", "drama"],
        }, headers=auth_headers(token))
        assert res.status_code == 201
        data = res.get_json()
        assert data["title"] == "New Film"
        assert data["status"] == "draft"
        assert data["goal_amount"] == 20000.0
        assert data["tags"] == ["indie", "drama"]

    def test_requires_auth(self, client):
        res = client.post("/api/campaigns/", json={
            "title": "New Film",
            "description": "desc",
            "goal_amount": 5000,
        })
        assert res.status_code == 401

    def test_missing_title(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "description": "desc",
            "goal_amount": 5000,
        }, headers=auth_headers(token))
        assert res.status_code == 400

    def test_missing_description(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "Film",
            "goal_amount": 5000,
        }, headers=auth_headers(token))
        assert res.status_code == 400

    def test_missing_goal_amount(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "Film",
            "description": "desc",
        }, headers=auth_headers(token))
        assert res.status_code == 400

    def test_invalid_goal_amount(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "Film",
            "description": "desc",
            "goal_amount": -100,
        }, headers=auth_headers(token))
        assert res.status_code == 400

    def test_invalid_deadline_format(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "Film",
            "description": "desc",
            "goal_amount": 5000,
            "deadline": "not-a-date",
        }, headers=auth_headers(token))
        assert res.status_code == 400

    def test_valid_deadline(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "Film",
            "description": "desc",
            "goal_amount": 5000,
            "deadline": "2027-12-31T00:00:00",
        }, headers=auth_headers(token))
        assert res.status_code == 201
        assert res.get_json()["deadline"] is not None


class TestUpdateCampaign:
    def test_owner_can_update(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.patch(f"/api/campaigns/{campaign['id']}", json={
            "title": "Updated Title",
        }, headers=auth_headers(token))
        assert res.status_code == 200
        assert res.get_json()["title"] == "Updated Title"

    def test_non_owner_blocked(self, client):
        filmmaker1, token1 = make_filmmaker(client, name="Alice", email="alice@example.com")
        _, token2 = make_filmmaker(client, name="Bob", email="bob@example.com")
        campaign = make_active_campaign(client, token1, filmmaker1["id"])
        res = client.patch(f"/api/campaigns/{campaign['id']}", json={
            "title": "Hacked",
        }, headers=auth_headers(token2))
        assert res.status_code == 403

    def test_unauthenticated_blocked(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.patch(f"/api/campaigns/{campaign['id']}", json={"title": "x"})
        assert res.status_code == 401

    def test_invalid_status_rejected(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.patch(f"/api/campaigns/{campaign['id']}", json={
            "status": "unicorn",
        }, headers=auth_headers(token))
        assert res.status_code == 400

    def test_not_found(self, client):
        _, token = make_filmmaker(client)
        res = client.patch("/api/campaigns/9999", json={"title": "x"}, headers=auth_headers(token))
        assert res.status_code == 404


class TestDeleteCampaign:
    def test_owner_can_delete_draft(self, client):
        _, token = make_filmmaker(client)
        res = client.post("/api/campaigns/", json={
            "title": "Draft",
            "description": "desc",
            "goal_amount": 5000,
        }, headers=auth_headers(token))
        campaign_id = res.get_json()["id"]

        res = client.delete(f"/api/campaigns/{campaign_id}", headers=auth_headers(token))
        assert res.status_code == 200

        res = client.get(f"/api/campaigns/{campaign_id}")
        assert res.status_code == 404

    def test_cannot_delete_active_campaign(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.delete(f"/api/campaigns/{campaign['id']}", headers=auth_headers(token))
        assert res.status_code == 400

    def test_non_owner_blocked(self, client):
        filmmaker1, token1 = make_filmmaker(client, name="Alice", email="alice@example.com")
        _, token2 = make_filmmaker(client, name="Bob", email="bob@example.com")
        res = client.post("/api/campaigns/", json={
            "title": "Draft",
            "description": "desc",
            "goal_amount": 5000,
        }, headers=auth_headers(token1))
        campaign_id = res.get_json()["id"]

        res = client.delete(f"/api/campaigns/{campaign_id}", headers=auth_headers(token2))
        assert res.status_code == 403

    def test_not_found(self, client):
        _, token = make_filmmaker(client)
        res = client.delete("/api/campaigns/9999", headers=auth_headers(token))
        assert res.status_code == 404


class TestPostCampaignUpdate:
    def test_owner_can_post_update(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post(f"/api/campaigns/{campaign['id']}/updates", json={
            "title": "Week 1 update",
            "body": "Filming starts Monday!",
        }, headers=auth_headers(token))
        assert res.status_code == 201
        data = res.get_json()
        assert data["title"] == "Week 1 update"
        assert data["campaign_id"] == campaign["id"]

    def test_update_appears_in_campaign_detail(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        client.post(f"/api/campaigns/{campaign['id']}/updates", json={
            "title": "Update",
            "body": "Body text",
        }, headers=auth_headers(token))

        res = client.get(f"/api/campaigns/{campaign['id']}")
        updates = res.get_json()["updates"]
        assert len(updates) == 1
        assert updates[0]["title"] == "Update"

    def test_non_owner_blocked(self, client):
        filmmaker1, token1 = make_filmmaker(client, name="Alice", email="alice@example.com")
        _, token2 = make_filmmaker(client, name="Bob", email="bob@example.com")
        campaign = make_active_campaign(client, token1, filmmaker1["id"])
        res = client.post(f"/api/campaigns/{campaign['id']}/updates", json={
            "title": "x",
            "body": "y",
        }, headers=auth_headers(token2))
        assert res.status_code == 403

    def test_missing_title_or_body(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post(f"/api/campaigns/{campaign['id']}/updates", json={
            "title": "Only title",
        }, headers=auth_headers(token))
        assert res.status_code == 400
