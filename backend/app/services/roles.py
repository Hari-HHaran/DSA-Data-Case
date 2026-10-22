"""Role codes and the permission matrix enforced server-side."""

REQUESTOR = "REQUESTOR"
BU_HEAD = "BU_HEAD"
FINANCE = "FINANCE"
QRA = "QRA"
BUSINESS_SUPPORT = "BUSINESS_SUPPORT"
MDM_ANALYST = "MDM_ANALYST"
ADMIN = "ADMIN"
SALES = "SALES"
EXECUTIVE = "EXECUTIVE"

APPROVER_ROLES = (BU_HEAD, FINANCE, QRA, BUSINESS_SUPPORT)

ROLE_DEFINITIONS = [
    (REQUESTOR, "Requestor", "Raises master-data requests and tracks them.", False),
    (BU_HEAD, "Business Unit Head", "Approves the business justification for new records.", True),
    (FINANCE, "Finance", "Approves credit terms, payment terms and banking details.", True),
    (QRA, "Quality / Regulatory Affairs", "Confirms product licensing and supplier quality evidence.", True),
    (BUSINESS_SUPPORT, "Business Support", "Confirms warehouse, pricing and logistics set-up.", True),
    (MDM_ANALYST, "MDM Analyst", "Performs final verification and SAP B1 creation.", False),
    (ADMIN, "Administrator", "Configures forms, approval rules and SLAs.", False),
    (SALES, "Regional Sales", "Uses regional insights and works sales follow-ups.", False),
    (EXECUTIVE, "Executive Viewer", "Read-only view of performance and impact.", False),
]

# Who may see FINANCIAL-sensitivity fields (banking details, credit limits) unmasked.
FINANCIAL_FIELD_ROLES = (FINANCE, MDM_ANALYST)
# Roles that may see every MDM request (others see their own requests and those they act on).
REQUEST_OVERSIGHT_ROLES = (MDM_ANALYST, ADMIN, EXECUTIVE)
COMMERCIAL_ROLES = (SALES, EXECUTIVE, ADMIN)
ANALYTICS_ROLES = (SALES, EXECUTIVE, ADMIN, MDM_ANALYST, BU_HEAD, FINANCE)
