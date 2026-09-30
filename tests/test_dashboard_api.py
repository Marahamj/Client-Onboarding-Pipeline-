def test_dashboard_endpoints(client, sample_payload):
    client.post("/webhooks/crm-deal-won", json=sample_payload)

    onboardings = client.get("/onboardings").json()
    assert isinstance(onboardings, list), onboardings
    # assert len(onboardings) == 1
    # assert len(onboardings[0]["steps"]) == 7

    assert client.get("/dlq").json() == []