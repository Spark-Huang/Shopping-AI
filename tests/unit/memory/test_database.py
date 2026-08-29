import importlib

from fastapi.testclient import TestClient


def test_cart_add_is_idempotent_for_same_user_and_item(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORY_DATABASE_URL", f"sqlite:///{tmp_path / 'context.db'}")
    module = importlib.import_module("memory.app.main")
    client = TestClient(module.app)
    payload = {
        "item": "Silk Dress",
        "amount": 1,
        "price": 49.99,
        "url": "",
        "idempotent": True,
    }

    assert client.post("/user/1/cart/add", json=payload).status_code == 200
    assert client.post("/user/1/cart/add", json=payload).status_code == 200

    cart = client.get("/user/1/cart").json()["cart"]
    assert cart == [
        {"item": "Silk Dress", "amount": 1, "price": 49.99, "url": None, "image": None}
    ]
