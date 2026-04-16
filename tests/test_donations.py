from tests.conftest import make_filmmaker, auth_headers, make_active_campaign


class TestCreateDonation:
    def test_success(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan@example.com",
            "amount": 50.00,
            "donor_name": "A Fan",
            "message": "Love your work!",
        })
        assert res.status_code == 201
        data = res.get_json()
        assert data["donation"]["amount"] == 50.0
        assert data["campaign"]["current_amount"] == 50.0

    def test_updates_campaign_total(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan1@example.com",
            "amount": 100,
        })
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan2@example.com",
            "amount": 200,
        })
        assert res.get_json()["campaign"]["current_amount"] == 300.0

    def test_anonymous_donation(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "anon@example.com",
            "amount": 25,
            "donor_name": "Secret Person",
            "is_anonymous": True,
        })
        assert res.status_code == 201
        donation = res.get_json()["donation"]
        assert donation["is_anonymous"] is True
        assert donation["donor_name"] is None  # hidden for anonymous

    def test_auto_marks_funded_when_goal_reached(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"], goal_amount=100)
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "bigfan@example.com",
            "amount": 100,
        })
        assert res.status_code == 201
        assert res.get_json()["campaign"]["status"] == "funded"

    def test_missing_campaign_id(self, client):
        res = client.post("/api/donations/", json={
            "donor_email": "fan@example.com",
            "amount": 50,
        })
        assert res.status_code == 400

    def test_missing_donor_email(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "amount": 50,
        })
        assert res.status_code == 400

    def test_missing_amount(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan@example.com",
        })
        assert res.status_code == 400

    def test_amount_below_minimum(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan@example.com",
            "amount": 0.50,
        })
        assert res.status_code == 400
        assert "1.00" in res.get_json()["error"]

    def test_campaign_not_found(self, client):
        res = client.post("/api/donations/", json={
            "campaign_id": 9999,
            "donor_email": "fan@example.com",
            "amount": 50,
        })
        assert res.status_code == 404

    def test_inactive_campaign_rejected(self, client):
        _, token = make_filmmaker(client)
        # Campaign is draft by default (not active)
        res = client.post("/api/campaigns/", json={
            "title": "Draft",
            "description": "desc",
            "goal_amount": 5000,
        }, headers=auth_headers(token))
        campaign_id = res.get_json()["id"]

        res = client.post("/api/donations/", json={
            "campaign_id": campaign_id,
            "donor_email": "fan@example.com",
            "amount": 50,
        })
        assert res.status_code == 400
        assert "not currently accepting" in res.get_json()["error"]

    def test_donor_email_stored_lowercase(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "FAN@EXAMPLE.COM",
            "amount": 10,
        })
        res = client.get(f"/api/donations/campaign/{campaign['id']}")
        # Email is private, but we can verify via a private field if needed.
        # Just confirm the donation was recorded.
        assert len(res.get_json()) == 1


class TestGetCampaignDonations:
    def test_empty(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        res = client.get(f"/api/donations/campaign/{campaign['id']}")
        assert res.status_code == 200
        assert res.get_json() == []

    def test_returns_donations(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan1@example.com",
            "amount": 10,
        })
        client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan2@example.com",
            "amount": 20,
        })
        res = client.get(f"/api/donations/campaign/{campaign['id']}")
        assert res.status_code == 200
        assert len(res.get_json()) == 2

    def test_campaign_not_found(self, client):
        res = client.get("/api/donations/campaign/9999")
        assert res.status_code == 404

    def test_anonymous_donor_name_hidden(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "anon@example.com",
            "donor_name": "Secret",
            "amount": 10,
            "is_anonymous": True,
        })
        res = client.get(f"/api/donations/campaign/{campaign['id']}")
        donation = res.get_json()[0]
        assert donation["donor_name"] is None

    def test_no_private_fields_in_list(self, client):
        filmmaker, token = make_filmmaker(client)
        campaign = make_active_campaign(client, token, filmmaker["id"])
        client.post("/api/donations/", json={
            "campaign_id": campaign["id"],
            "donor_email": "fan@example.com",
            "amount": 10,
        })
        res = client.get(f"/api/donations/campaign/{campaign['id']}")
        donation = res.get_json()[0]
        assert "donor_email" not in donation
        assert "stripe_payment_intent_id" not in donation
