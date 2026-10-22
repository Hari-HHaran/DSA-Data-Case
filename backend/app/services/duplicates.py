"""Explainable hybrid duplicate detection.

1. Normalise (case, accents, punctuation, legal suffixes, common abbreviations).
2. Exact identifier match (registration no., manufacturer part no., cost-centre code) → likely duplicate.
3. Fuzzy name similarity (RapidFuzz token-based ratios, best of name and known aliases, plus acronyms).
4. Context: country, address similarity, manufacturer (items).
5. Weighted score in [0, 100] compared with configurable thresholds.

Nothing is ever merged automatically — results are review prompts with an explanation.
"""
import re
import unicodedata

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DuplicateCandidate, MasterRecord, MdmRequest
from . import settings_service
from .forms import DOMAIN_KEYS

LEGAL_SUFFIXES = {
    "pte", "ltd", "limited", "sdn", "bhd", "pt", "tbk", "co", "company", "inc", "llc", "plc", "corp",
    "corporation", "jsc", "public", "the", "s", "singapore",
}
ABBREVIATIONS = {
    "hosp": "hospital", "hsp": "hospital", "univ": "university", "uni": "university", "natl": "national",
    "nat": "national", "ntl": "national", "med": "medical", "ctr": "centre", "center": "centre", "cntr": "centre",
    "lab": "laboratory", "labs": "laboratories", "dx": "diagnostics", "diag": "diagnostics", "intl": "international",
    "gen": "general", "st": "saint", "sci": "scientific", "tech": "technologies", "mfg": "manufacturing",
    "&": "and", "dept": "department", "inst": "institute",
}
OPEN_STATUSES = ("SUBMITTED", "VALIDATION_COMPLETED", "PENDING_APPROVAL", "APPROVED", "MDM_VERIFICATION",
                 "SAP_PENDING", "SAP_FAILED", "NEEDS_CHANGES")


def normalise(text: str | None, drop_legal: bool = True) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " & ")
    text = re.sub(r"[^\w&\s]", " ", text)
    tokens = [ABBREVIATIONS.get(t, t) for t in text.split()]
    if drop_legal:
        tokens = [t for t in tokens if t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def normalise_identifier(value: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def acronym(text: str) -> str:
    return "".join(t[0] for t in normalise(text).split() if t not in {"and", "of"})


def name_similarity(a: str, b: str) -> tuple[float, str]:
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0, ""
    sort = fuzz.token_sort_ratio(na, nb)
    subset = fuzz.token_set_ratio(na, nb) * 0.95  # subset matches are strong but not exact
    score, how = (sort, "token similarity") if sort >= subset else (subset, "one name contains the other")
    compact_a, compact_b = na.replace(" ", ""), nb.replace(" ", "")
    for short, long_ in ((compact_a, b), (compact_b, a)):
        if 2 <= len(short) <= 6 and short == acronym(long_) and score < 90:
            score, how = 90.0, "acronym of the full name"
    return round(score, 1), how


def _band(score: float, likely: float, review: float) -> str | None:
    if score >= likely:
        return "LIKELY_DUPLICATE"
    if score >= review:
        return "NEEDS_REVIEW"
    return None


def score_pair(domain: str, req: dict, cand: dict, cand_aliases: list[str]) -> dict:
    keys = DOMAIN_KEYS[domain]
    matched, notes = [], []
    req_name = req.get(keys["name"]) or ""
    names = [cand.get("name") or ""] + cand_aliases
    best, how, best_name = 0.0, "", names[0]
    for n in names:
        alt_names = [req_name] + ([req.get(keys["alt_name"])] if keys.get("alt_name") and req.get(keys["alt_name"]) else [])
        for rn in alt_names:
            s, h = name_similarity(rn, n)
            if s > best:
                best, how, best_name = s, h, n
    if best >= 60:
        matched.append("name")
        via = " (known alias)" if best_name != names[0] else ""
        notes.append(f"Name '{req_name}' ≈ '{best_name}'{via}: {best:.0f}% ({how}, after normalising case, punctuation and abbreviations)")

    rid, cid = normalise_identifier(req.get(keys["identifier"])), normalise_identifier(cand.get("identifier"))
    exact_id = bool(rid and cid and rid == cid)
    if exact_id:
        matched.append("identifier")
        notes.append(f"Identifier {req.get(keys['identifier'])} exactly matches the existing record")
    elif rid and cid:
        notes.append("Identifiers differ")

    if domain == "ITEM":
        rm, cm = normalise(req.get("manufacturer")), normalise(cand.get("manufacturer"))
        manu = fuzz.token_sort_ratio(rm, cm) if rm and cm else 0
        uom_same = bool(req.get("unit_of_measure")) and req.get("unit_of_measure") == cand.get("unit_of_measure")
        if manu >= 85:
            matched.append("manufacturer")
            notes.append(f"Same manufacturer ({cand.get('manufacturer')})")
        if uom_same:
            matched.append("unit_of_measure")
        score = 0.6 * best + 0.3 * manu + 0.1 * (100 if uom_same else 0)
    else:
        same_country = bool(req.get("country_code")) and req.get("country_code") == cand.get("country_code")
        if same_country:
            matched.append("country")
            notes.append(f"Same country ({cand.get('country_code')})")
        elif cand.get("country_code"):
            notes.append(f"Different country ({cand.get('country_code')})")
        addr_key = keys.get("address")
        ra, ca = normalise(req.get(addr_key) if addr_key else None, False), normalise(cand.get("address"), False)
        if ra and ca:
            addr = fuzz.token_set_ratio(ra, ca)
            if addr >= 80:
                matched.append("address")
                notes.append(f"Address similarity {addr:.0f}%")
            score = 0.65 * best + 0.15 * (100 if same_country else 0) + 0.20 * addr
        else:
            score = 0.8 * best + 0.2 * (100 if same_country else 0)
    if exact_id:
        score = max(score, 99.0)
    return {"score": round(score, 1), "exact_identifier_match": exact_id, "matched_fields": matched, "explanation": "; ".join(notes)}


def _record_view(mr: MasterRecord) -> dict:
    attrs = mr.attributes or {}
    return {"name": mr.name, "identifier": mr.identifier, "country_code": mr.country_code,
            "address": attrs.get("address"), "manufacturer": attrs.get("manufacturer"),
            "unit_of_measure": attrs.get("unit_of_measure")}


def find_candidates(db: Session, domain: str, req_values: dict, exclude_request_id: int | None = None, limit: int = 5) -> list[dict]:
    likely = float(settings_service.get(db, "duplicate.likely_threshold"))
    review = float(settings_service.get(db, "duplicate.review_threshold"))
    keys = DOMAIN_KEYS[domain]
    results = []
    records = db.execute(select(MasterRecord).where(MasterRecord.domain == domain, MasterRecord.status == "ACTIVE")).scalars()
    for mr in records:
        r = score_pair(domain, req_values, _record_view(mr), [a.alias_name for a in mr.aliases])
        band = _band(r["score"], likely, review)
        if band or r["exact_identifier_match"]:
            results.append({**r, "band": band or "LIKELY_DUPLICATE", "master_record_id": mr.id, "other_request_id": None,
                            "existing": {"type": "MASTER_RECORD", "code": mr.record_code, "name": mr.name,
                                         "country_code": mr.country_code, "identifier": mr.identifier,
                                         "sap_code": mr.sap_code, "aliases": [a.alias_name for a in mr.aliases]}})
    # In-flight requests: two people asking for the same record at the same time.
    q = select(MdmRequest).where(MdmRequest.domain == domain, MdmRequest.status.in_(OPEN_STATUSES))
    if exclude_request_id:
        q = q.where(MdmRequest.id != exclude_request_id)
    for other in db.execute(q).scalars():
        d = other.data
        view = {"name": d.get(keys["name"]), "identifier": d.get(keys["identifier"]), "country_code": other.country_code,
                "address": d.get(keys.get("address", "")), "manufacturer": d.get("manufacturer"), "unit_of_measure": d.get("unit_of_measure")}
        r = score_pair(domain, req_values, view, [])
        band = _band(r["score"], likely, review)
        if band or r["exact_identifier_match"]:
            r["explanation"] = f"In-flight request {other.request_number} ({other.status.replace('_', ' ').lower()}). " + r["explanation"]
            results.append({**r, "band": band or "LIKELY_DUPLICATE", "master_record_id": None, "other_request_id": other.id,
                            "existing": {"type": "OPEN_REQUEST", "code": other.request_number, "name": view["name"],
                                         "country_code": other.country_code, "identifier": view["identifier"], "status": other.status}})
    results.sort(key=lambda r: (-r["exact_identifier_match"], -r["score"]))
    return results[:limit]


def suggested_action(c: dict) -> str:
    if c["exact_identifier_match"]:
        return "Reuse the existing record, or correct the identifier if it was entered by mistake."
    if c["band"] == "LIKELY_DUPLICATE":
        return "Check the existing record first. Continue only with a documented justification."
    return "Review the similar record; confirm it is a different entity before continuing."


def run_check(db: Session, req: MdmRequest) -> list[DuplicateCandidate]:
    db.query(DuplicateCandidate).filter(DuplicateCandidate.request_id == req.id).delete()
    values = dict(req.data)
    values["country_code"] = req.country_code
    found = find_candidates(db, req.domain, values, exclude_request_id=req.id)
    rows = []
    for c in found:
        row = DuplicateCandidate(request_id=req.id, master_record_id=c["master_record_id"], other_request_id=c["other_request_id"],
                                 score=c["score"], band=c["band"], exact_identifier_match=c["exact_identifier_match"],
                                 matched_fields=c["matched_fields"], explanation=c["explanation"])
        db.add(row)
        rows.append(row)
    if not found:
        req.duplicate_check_status = "CLEAR"
    elif any(c["exact_identifier_match"] for c in found):
        req.duplicate_check_status = "BLOCKED"
    else:
        req.duplicate_check_status = "REVIEW_REQUIRED"
    db.flush()
    return rows


def identity_keys(domain: str) -> set[str]:
    k = DOMAIN_KEYS[domain]
    return {v for v in k.values()} | {"unit_of_measure"}
