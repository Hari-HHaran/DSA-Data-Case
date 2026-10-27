from datetime import date, timedelta

from conftest import new_item, upload

FUTURE = (date.today() + timedelta(days=365)).isoformat()


def test_incomplete_required_fields_block_submission(client, login):
    amy = login("amy")
    req = new_item(client, amy)
    r = client.post(f"/api/mdm/requests/{req['id']}/submit", headers=amy)
    assert r.status_code == 422
    errors = r.json()["readiness"]["errors"]
    # Class B makes licence fields and evidence conditionally mandatory.
    assert "licence_number" in errors and "licence_expiry" in errors
    assert "attachment:REGULATORY_LICENCE" in errors
    assert client.get(f"/api/mdm/requests/{req['id']}", headers=amy).json()["status"] == "DRAFT"


def test_backend_validation_cannot_be_bypassed_and_then_passes(client, login):
    amy = login("amy")
    req = new_item(client, amy, manufacturer_part_no="NSD-VTM-2", licence_number="LIC-1", licence_expiry="2001-01-01")
    v = client.post("/api/mdm/validate", json={"domain": "ITEM", "entity_code": "SPD", "country_code": "SG", "request_id": req["id"],
                                               "data": client.get(f"/api/mdm/requests/{req['id']}", headers=amy).json()["data"]}, headers=amy).json()
    assert v["state"] == "INCOMPLETE" and "licence_expiry" in v["field_errors"]  # expired licence
    assert any(s["role_code"] == "QRA" for s in v["route"])  # routing preview explains QRA sign-off
    client.patch(f"/api/mdm/requests/{req['id']}", json={"data": {"licence_expiry": FUTURE}}, headers=amy)
    upload(client, amy, req["id"])
    r = client.post(f"/api/mdm/requests/{req['id']}/submit", headers=amy)
    assert r.status_code == 200, r.text
    assert r.json()["request"]["status"] == "PENDING_APPROVAL"


def test_invalid_email_rejected(client, login):
    v = client.post("/api/mdm/validate", json={"domain": "CUSTOMER", "entity_code": "QTS", "country_code": "SG",
                                               "data": {"contact_email": "not-an-email"}}, headers=login("marcus")).json()
    assert "valid email" in v["field_errors"]["contact_email"]


def test_near_duplicate_produces_review_warning(client, login):
    r = client.post("/api/mdm/duplicate-check", json={"domain": "CUSTOMER", "country_code": "SG",
                                                      "data": {"legal_name": "National Univ. Hospital Pte Ltd", "business_reg_no": "ZZ999999"}},
                    headers=login("marcus")).json()
    top = r["candidates"][0]
    assert top["existing"]["name"] == "National University Hospital"
    assert top["band"] in ("LIKELY_DUPLICATE", "NEEDS_REVIEW") and not top["exact_identifier_match"]
    assert "name" in top["matched_fields"] and top["explanation"]


def test_exact_identifier_duplicate_blocks_and_cannot_continue(client, login):
    amy = login("amy")
    req = new_item(client, amy, item_name="Totally different name", manufacturer_part_no="MTB-VTM-3ML")
    r = client.post("/api/mdm/duplicate-check", json={"request_id": req["id"]}, headers=amy).json()
    assert r["status"] == "BLOCKED" and r["candidates"][0]["exact_identifier_match"]
    bad = client.post(f"/api/mdm/requests/{req['id']}/duplicate-review", json={"decision": "CONTINUE_WITH_JUSTIFICATION",
                                                                              "justification": "I really want a new one please"}, headers=amy)
    assert bad.status_code == 422
    ok = client.post(f"/api/mdm/requests/{req['id']}/duplicate-review", json={"decision": "REUSE_EXISTING"}, headers=amy).json()
    assert ok["status"] == "CANCELLED" and "Reused existing record" in ok["resolution"]


def test_drafts_persist_and_can_be_cloned(client, login):
    amy = login("amy")
    req = new_item(client, amy, item_name="Persisted draft item", manufacturer_part_no="PER-001")
    again = client.get(f"/api/mdm/requests/{req['id']}", headers=amy).json()
    assert again["data"]["item_name"] == "Persisted draft item" and again["status"] == "DRAFT"
    clone = client.post(f"/api/mdm/requests/{req['id']}/clone", headers=amy).json()
    assert clone["id"] != req["id"] and clone["data"]["item_name"] == "Persisted draft item"
    listed = client.get("/api/mdm/requests", params={"q": "Persisted draft"}, headers=amy).json()
    assert listed["total"] >= 2


def test_returned_request_can_be_corrected_and_resubmitted(client, login):
    amy = login("amy")
    returned = client.get("/api/mdm/requests", params={"status": "NEEDS_CHANGES"}, headers=amy).json()["items"]
    assert returned, "seed should include a request returned to Amy"
    rid = returned[0]["id"]
    r = client.patch(f"/api/mdm/requests/{rid}", json={"data": {"regulatory_class": "Class A"}}, headers=amy)
    assert r.status_code == 200
    s = client.post(f"/api/mdm/requests/{rid}/submit", headers=amy)
    assert s.status_code == 200, s.text
    body = s.json()["request"]
    assert body["cycle"] == 2 and body["status"] == "PENDING_APPROVAL"
    assert not any(t["role_code"] == "QRA" for t in body["tasks"] if t["cycle"] == 2)  # Class A no longer needs QRA


def test_other_users_cannot_edit_or_view_private_drafts(client, login):
    req = new_item(client, login("amy"), manufacturer_part_no="PRIV-1")
    assert client.patch(f"/api/mdm/requests/{req['id']}", json={"data": {"item_name": "x"}}, headers=login("marcus")).status_code == 403
    assert client.get(f"/api/mdm/requests/{req['id']}", headers=login("marcus")).status_code == 403


def test_sensitive_fields_masked_for_non_finance(client, login):
    reqs = client.get("/api/mdm/requests", params={"scope": "all", "domain": "VENDOR", "status": "PENDING_APPROVAL"}, headers=login("priya")).json()["items"]
    rid = reqs[0]["id"]
    fin = client.get(f"/api/mdm/requests/{rid}", headers=login("weijie")).json()
    bu = client.get(f"/api/mdm/requests/{rid}", headers=login("daniel")).json()
    assert "restricted" not in fin["data"]["bank_account_no"]
    assert "restricted" in bu["data"]["bank_account_no"] and "bank_account_no" in bu["masked_fields"]
