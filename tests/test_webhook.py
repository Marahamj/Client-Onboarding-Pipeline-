

def test_webhook_creates_onboarding(client,sample_payload):
    response = client.post("/webhooks/crm-deal-won", json=sample_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["current_step"] == "contract"
    assert data["crm_deal_id"] == "DEAL-TEST-001"


def test_webhook_prevents_duplicate(client,sample_payload):
    first = client.post("/webhooks/crm-deal-won", json=sample_payload)
    second = client.post("/webhooks/crm-deal-won", json=sample_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["onboarding_id"] == second.json()["onboarding_id"]