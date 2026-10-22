import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="lives_one_test_"))
os.environ["LIVES_DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["LIVES_UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["LIVES_SLA_SWEEP_SECONDS"] = "0"
os.environ["LIVES_DEMO_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed.__main__ import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded():
    seed(quiet=True)
    yield


@pytest.fixture(scope="session")
def client(seeded):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def login(client):
    cache = {}

    def _login(username: str) -> dict:
        if username not in cache:
            r = client.post("/api/auth/demo-login", json={"username": username})
            assert r.status_code == 200, r.text
            cache[username] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return cache[username]
    return _login


PDF = b"%PDF-1.4\n%synthetic test document\n%%EOF"


def new_item(client, headers, **overrides):
    data = {"item_name": "Viral Transport Medium, 1 mL tube", "item_description": "Test item", "product_family": "Product A",
            "item_category": "Consumable", "unit_of_measure": "BOX", "manufacturer": "Northstar Diagnostics", "manufacturer_part_no": "NSD-VTM-1",
            "regulatory_class": "Class B", "storage_condition": "Ambient", "stock_managed": "Yes"}
    data.update(overrides)
    r = client.post("/api/mdm/requests", json={"domain": "ITEM", "entity_code": "SPD", "country_code": "SG", "data": data}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def upload(client, headers, req_id, category="REGULATORY_LICENCE"):
    r = client.post(f"/api/mdm/requests/{req_id}/attachments", data={"category": category},
                    files={"file": ("licence.pdf", PDF, "application/pdf")}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
