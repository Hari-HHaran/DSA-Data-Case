"""SAP Business One integration adapter.

The prototype ships `MockSapB1Adapter`, which returns clearly labelled simulated confirmations.
`ServiceLayerSapB1Adapter` documents the shape of a future real integration; it is deliberately not
implemented because the SAP B1 deployment, Service Layer availability, company database, field
mappings, authentication and permissions have not been confirmed with Lives Group.

Domains do not share one endpoint. In SAP B1 Service Layer terms (to be confirmed):
  CUSTOMER / VENDOR -> BusinessPartners (CardType cCustomer / cSupplier)
  ITEM              -> Items
  COST_CENTER       -> ProfitCenters (SAP B1 models cost centres as profit centres / distribution rules)
"""
from dataclasses import dataclass

OBJECT_TYPES = {
    "CUSTOMER": ("CREATE_BUSINESS_PARTNER", "BusinessPartners"),
    "VENDOR": ("CREATE_BUSINESS_PARTNER", "BusinessPartners"),
    "ITEM": ("CREATE_ITEM", "Items"),
    "COST_CENTER": ("CREATE_COST_CENTER", "ProfitCenters"),
}
MAX_LEN = {"CardName": 100, "ItemName": 100, "CenterName": 100, "CardCode": 15, "ItemCode": 50, "CenterCode": 8}


class SapAdapterError(Exception):
    def __init__(self, message: str, retryable: bool = True, code: str = "SAP_ERROR"):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass
class SapResult:
    sap_key: str
    object_type: str
    raw: dict


def build_payload(domain: str, data: dict, entity_code: str | None, country_code: str | None) -> dict:
    """Maps a request onto an *assumed* SAP B1 payload. Field mapping must be confirmed before go-live."""
    if domain in ("CUSTOMER", "VENDOR"):
        p = {
            "CardType": "cCustomer" if domain == "CUSTOMER" else "cSupplier",
            "CardName": data.get("legal_name"), "FederalTaxID": data.get("business_reg_no") or data.get("vendor_reg_no"),
            "Country": country_code, "EmailAddress": data.get("contact_email"), "Phone1": data.get("contact_phone"),
            "ContactPerson": data.get("contact_person"), "PayTermsGrpCode": data.get("payment_terms"),
            "Address": data.get("registered_address") or data.get("address"),
            "U_LivesEntity": entity_code,  # assumed user-defined field
        }
        if domain == "CUSTOMER":
            p["CreditLimit"] = float(data["credit_limit"]) if data.get("credit_limit") else 0.0
        else:
            p["BPBankAccounts"] = [{"BankCode": data.get("bank_name"), "AccountNo": data.get("bank_account_no"),
                                    "BICSwiftCode": data.get("swift_code")}]
        return p
    if domain == "ITEM":
        return {
            "ItemName": data.get("item_name"), "ForeignName": data.get("item_description"),
            "ItemsGroupCode": data.get("item_category"), "InventoryUOM": data.get("unit_of_measure"),
            "Manufacturer": data.get("manufacturer"), "SupplierCatalogNo": data.get("manufacturer_part_no"),
            "InventoryItem": "tYES" if data.get("stock_managed") == "Yes" else "tNO",
            "U_ProductFamily": data.get("product_family"), "U_RegClass": data.get("regulatory_class"),
            "U_LicenceNo": data.get("licence_number"), "U_LivesEntity": entity_code, "U_Country": country_code,
        }
    if domain == "COST_CENTER":
        return {"CenterCode": (data.get("cost_center_code") or "").replace("-", "")[:8], "CenterName": data.get("cost_center_name"),
                "InWhichDimension": 1, "EffectiveFrom": data.get("effective_date"), "CenterOwner": data.get("responsible_manager"),
                "U_LivesEntity": entity_code}
    raise SapAdapterError(f"Unsupported domain {domain}", retryable=False)


def validate_payload(domain: str, payload: dict) -> list[str]:
    problems = []
    name_key = {"CUSTOMER": "CardName", "VENDOR": "CardName", "ITEM": "ItemName", "COST_CENTER": "CenterName"}[domain]
    if not payload.get(name_key):
        problems.append(f"{name_key} is required.")
    for k, n in MAX_LEN.items():
        if isinstance(payload.get(k), str) and len(payload[k]) > n:
            problems.append(f"{k} exceeds SAP B1 maximum length of {n} characters.")
    if domain == "VENDOR" and not (payload.get("BPBankAccounts") or [{}])[0].get("AccountNo"):
        problems.append("Vendor bank account is required.")
    return problems


class MockSapB1Adapter:
    """Simulated SAP B1. Deterministic keys, idempotent per idempotency key, optional forced failure."""
    mode = "mock"

    def __init__(self):
        self._by_key: dict[str, SapResult] = {}

    def create(self, domain: str, payload: dict, idempotency_key: str, sequence: int, fail: bool = False) -> SapResult:
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        if fail:
            raise SapAdapterError("Simulated failure: SAP B1 Service Layer unavailable (HTTP 503). No record was created.",
                                  retryable=True, code="MOCK_503")
        prefix = {"CUSTOMER": "C", "VENDOR": "V", "ITEM": "I", "COST_CENTER": "CC"}[domain]
        key = f"MOCK-{prefix}{sequence:05d}"
        _, obj = OBJECT_TYPES[domain]
        result = SapResult(key, obj, {"mock": True, "object": obj, "key": key, "message": "Simulated SAP B1 confirmation — no real SAP system was called."})
        self._by_key[idempotency_key] = result
        return result


class ServiceLayerSapB1Adapter:  # pragma: no cover - future integration contract
    mode = "service_layer"

    def create(self, domain, payload, idempotency_key, sequence, fail=False):
        raise SapAdapterError("Real SAP B1 integration is not configured in this prototype.", retryable=False, code="NOT_CONFIGURED")


_mock = MockSapB1Adapter()


def get_adapter(mode: str):
    return _mock if mode == "mock" else ServiceLayerSapB1Adapter()
