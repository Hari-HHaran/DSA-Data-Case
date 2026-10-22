from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import SapRecordMapping, WorkflowEvent
from app.services.state_machine import can_transition
from conftest import new_item, upload

FUTURE = (date.today() + timedelta(days=365)).isoformat()


NAMES = {"E2E-001": ("Saliva Collection Kit", "Oralis Health"), "AUTH-001": ("Cuvette Rotor Disc", "Rotaflow Instruments"),
         "CHG-001": ("Blood Gas Cartridge", "Arterion Medical")}


def submitted_item(client, login, part):
    amy = login("amy")
    name, maker = NAMES[part]
    req = new_item(client, amy, manufacturer_part_no=part, item_name=name, manufacturer=maker, licence_number="LIC-9", licence_expiry=FUTURE)
    upload(client, amy, req["id"])
    r = client.post(f"/api/mdm/requests/{req['id']}/submit", headers=amy)
    assert r.status_code == 200, r.text
    return r.json()["request"]


def task(req, role, status="PENDING"):
    return next(t for t in req["tasks"] if t["role_code"] == role and t["status"] == status and t["cycle"] == req["cycle"])


def test_end_to_end_amy_item_to_mock_sap(client, login):
    req = submitted_item(client, login, "E2E-001")
    stages = {t["role_code"]: t for t in req["tasks"]}
    assert stages["QRA"]["stage"] == stages["BU_HEAD"]["stage"] == 1 and stages["BUSINESS_SUPPORT"]["stage"] == 2
    assert stages["BUSINESS_SUPPORT"]["status"] == "WAITING"

    # Stage 2 cannot be approved before stage 1 completes.
    assert client.post(f"/api/approvals/{stages['BUSINESS_SUPPORT']['id']}/approve", json={}, headers=login("kevin")).status_code == 409
    # Parallel: one approval is not enough.
    r = client.post(f"/api/approvals/{stages['QRA']['id']}/approve", json={"comment": "Licence OK"}, headers=login("siti")).json()
    assert r["request"]["status"] == "PENDING_APPROVAL"
    # Double submission of the same decision is rejected.
    assert client.post(f"/api/approvals/{stages['QRA']['id']}/approve", json={}, headers=login("siti")).status_code == 409
    client.post(f"/api/approvals/{stages['BU_HEAD']['id']}/approve", json={}, headers=login("daniel"))
    r = client.post(f"/api/approvals/{stages['BUSINESS_SUPPORT']['id']}/approve", json={}, headers=login("kevin")).json()
    assert r["request"]["status"] == "MDM_VERIFICATION"

    # SAP cannot be triggered before verification; only MDM can verify.
    assert client.post(f"/api/sap/sync/{req['id']}", headers=login("priya")).status_code == 409
    assert client.post(f"/api/mdm/requests/{req['id']}/verify", json={"action": "VERIFY"}, headers=login("daniel")).status_code == 403
    assert client.post(f"/api/mdm/requests/{req['id']}/verify", json={"action": "VERIFY"}, headers=login("priya")).json()["status"] == "SAP_PENDING"
    out = client.post(f"/api/sap/sync/{req['id']}", headers=login("priya")).json()["request"]
    assert out["status"] == "SAP_COMPLETED"
    assert out["sap"]["mapping"]["sap_key"].startswith("MOCK-") and out["sap"]["mapping"]["is_mock"]

    notes = client.get("/api/notifications", headers=login("amy")).json()["items"]
    assert any(n["event_type"] == "SAP_CREATED" and req["request_number"] in n["title"] for n in notes)
    timeline = client.get(f"/api/workflows/{req['id']}", headers=login("amy")).json()
    assert [s["state"] for s in timeline["stages"]][-1] == "current"
    events = [e for e in out["events"] if e["event_type"].startswith("TASK_")]
    assert events and all(e["actor"] and e["created_at"] for e in events)
    assert client.get("/api/audit-events/verify", headers=login("alex")).json()["valid"]


def test_only_authorised_approvers_can_decide(client, login):
    req = submitted_item(client, login, "AUTH-001")
    qra = task(req, "QRA")
    assert client.post(f"/api/approvals/{qra['id']}/approve", json={}, headers=login("weijie")).status_code == 403
    assert client.post(f"/api/approvals/{qra['id']}/approve", json={}, headers=login("amy")).status_code == 403
    assert client.post(f"/api/approvals/{qra['id']}/reject", json={"comment": ""}, headers=login("siti")).status_code == 422


def test_request_changes_cancels_parallel_tasks(client, login):
    req = submitted_item(client, login, "CHG-001")
    r = client.post(f"/api/approvals/{task(req, 'BU_HEAD')['id']}/request-changes", json={"comment": "Please add supplier lead time"},
                    headers=login("daniel")).json()["request"]
    assert r["status"] == "NEEDS_CHANGES"
    assert all(t["status"] in ("CHANGES_REQUESTED", "CANCELLED") for t in r["tasks"] if t["cycle"] == r["cycle"])


def test_failed_sap_is_not_completed_and_retry_is_idempotent(client, login):
    priya = login("priya")
    queue = client.get("/api/mdm/requests", params={"scope": "all", "status": "MDM_VERIFICATION"}, headers=priya).json()["items"]
    rid = queue[0]["id"]
    client.post(f"/api/mdm/requests/{rid}/verify", json={"action": "VERIFY"}, headers=priya)
    client.put("/api/sap/mock-failure", json={"value": 1}, headers=priya)
    failed = client.post(f"/api/sap/sync/{rid}", headers=priya).json()["request"]
    assert failed["status"] == "SAP_FAILED" and failed["completed_at"] is None and failed["sap"]["mapping"] is None
    ok = client.post(f"/api/sap/sync/{rid}", headers=priya).json()["request"]
    assert ok["status"] == "SAP_COMPLETED" and ok["sap"]["jobs"][-1]["attempts"] == 2
    again = client.post(f"/api/sap/sync/{rid}", headers=priya)
    assert again.status_code == 200
    with SessionLocal() as db:
        assert len(db.execute(select(SapRecordMapping).where(SapRecordMapping.request_id == rid)).scalars().all()) == 1


def test_audit_log_is_append_only():
    with SessionLocal() as db:
        ev = db.execute(select(WorkflowEvent).limit(1)).scalar_one()
        ev.comment = "tampered"
        with pytest.raises(PermissionError):
            db.flush()
        db.rollback()
        with pytest.raises(PermissionError):
            db.delete(db.execute(select(WorkflowEvent).limit(1)).scalar_one())
            db.flush()


def test_state_machine_rejects_invalid_transitions():
    assert can_transition("DRAFT", "SUBMITTED")
    assert not can_transition("DRAFT", "SAP_COMPLETED")
    assert not can_transition("PENDING_APPROVAL", "SAP_PENDING")
    assert not can_transition("SAP_COMPLETED", "DRAFT")
    assert can_transition("SAP_FAILED", "SAP_PENDING")


def test_workflow_configuration_validation_and_effect(client, login):
    alex = login("alex")
    wf = next(w for w in client.get("/api/config/workflows", headers=alex).json() if w["domain"] == "ITEM")
    steps = [{k: s[k] for k in ("id", "step_key", "name", "role_code", "stage_order", "condition", "description", "sla_days", "is_active")} for s in wf["steps"]]
    bad = client.put(f"/api/config/workflows/{wf['id']}", json={"steps": steps + [{"step_key": "bad", "name": "Bad", "role_code": "SALES",
                                                                                     "stage_order": 3, "sla_days": 1}]}, headers=alex)
    assert bad.status_code == 422 and any("not an approver role" in p for p in bad.json()["problems"])
    assert client.put(f"/api/config/workflows/{wf['id']}", json={"steps": steps}, headers=login("amy")).status_code == 403
    cold = {"step_key": "cold_chain", "name": "Cold-chain regulatory review", "role_code": "QRA", "stage_order": 3, "sla_days": 1,
            "condition": {"all": [{"field": "storage_condition", "op": "eq", "value": "Frozen (−20°C)"}]}}
    ok = client.put(f"/api/config/workflows/{wf['id']}", json={"steps": steps + [cold]}, headers=alex)
    assert ok.status_code == 200
    v = client.post("/api/mdm/validate", json={"domain": "ITEM", "entity_code": "SPD", "country_code": "SG",
                                               "data": {"storage_condition": "Frozen (−20°C)", "regulatory_class": "Class A", "stock_managed": "No"}},
                    headers=login("amy")).json()
    assert any(s["name"] == "Cold-chain regulatory review" for s in v["route"])
    client.put(f"/api/config/workflows/{wf['id']}", json={"steps": steps}, headers=alex)  # restore


def test_sla_checks_are_idempotent(client, login):
    first = client.post("/api/workflows/sla/run", headers=login("alex")).json()
    second = client.post("/api/workflows/sla/run", headers=login("alex")).json()
    assert second["reminders_sent"] == 0 and second["escalations"] == 0 and first["checked"] >= 1
