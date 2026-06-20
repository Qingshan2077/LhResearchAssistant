"""Provider settings endpoint integration tests."""

from tests.factories import make_llm_provider


BASE_URL = "/api/v1/settings/providers"


def test_list_providers_is_empty(client):
    response = client.get(BASE_URL)
    assert response.status_code == 200
    assert response.json() == []


def test_create_provider(client):
    response = client.post(BASE_URL, json={
        "name": "deepseek", "display_name": "DeepSeek Test", "api_key": "sk-test",
        "base_url": "https://api.deepseek.com", "default_model": "deepseek-chat",
        "is_active": True, "priority": 1, "max_tokens": 4096,
    })
    assert response.status_code == 200
    assert response.json()["name"] == "deepseek"
    assert response.json()["id"]


def test_list_providers_after_insert(client, db_session):
    provider = make_llm_provider(display_name="My Provider")
    db_session.add(provider)
    db_session.commit()
    response = client.get(BASE_URL)
    assert response.status_code == 200
    assert response.json()[0]["display_name"] == "My Provider"


def test_update_provider_persists(client, db_session):
    provider = make_llm_provider(default_model="old-model")
    db_session.add(provider)
    db_session.commit()
    response = client.patch(f"{BASE_URL}/{provider.id}", json={
        "default_model": "new-model", "max_tokens": 16384,
    })
    assert response.status_code == 200
    db_session.refresh(provider)
    assert provider.default_model == "new-model"
    assert provider.max_tokens == 16384


def test_semantic_scholar_api_key_persists_encrypted(client, db_session):
    from app.database.sqlite import AppSetting

    response = client.put(
        "/api/v1/settings/semantic-scholar",
        json={"api_key": "s2-test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"api_key": "s2-test-key"}
    assert client.get("/api/v1/settings/semantic-scholar").json() == response.json()

    setting = db_session.get(AppSetting, "semantic_scholar_api_key")
    assert setting is not None
    assert setting.value != "s2-test-key"
    client.put("/api/v1/settings/semantic-scholar", json={"api_key": ""})