from typing import Dict, Any, Tuple
import structlog

logger = structlog.get_logger()

class PolicyEngine:
    """
    Policy engine enforcing compliance rules:
    - Allowed demand sources
    - Allowed contact methods
    - Permission checks
    - Anti-spam & affiliate compliance rules
    Produces auditable decision reasons for all checks.
    """

    ALLOWED_SOURCES = {"owned_api", "authorized_public", "commercial_search"}

    def evaluate_source_policy(self, source_type: str, metadata: Dict[str, Any]) -> Tuple[bool, str]:
        if source_type not in self.ALLOWED_SOURCES:
            return False, f"Source type '{source_type}' is not authorized by policy."

        if source_type == "authorized_public" and not metadata.get("authorized_feed", False):
            return False, "Public feed source is missing authorization metadata."

        return True, f"Source '{source_type}' is compliant with ingestion policy."

    def evaluate_outreach_policy(self, contact_identifier: str, permission_status: str, message_type: str) -> Tuple[bool, str]:
        if not contact_identifier:
            return False, "Outreach rejected: Missing contact identifier."

        if message_type == "recommendation" and permission_status != "granted":
            return False, f"Outreach rejected: Recommendation link requires explicit permission (current status: '{permission_status}'). Anti-spam policy strictly enforced."

        if message_type == "permission_request":
            return True, "Permission request outreach allowed under first-contact policy."

        return True, "Outreach allowed by policy."

    def evaluate_affiliate_policy(self, offer: Dict[str, Any]) -> Tuple[bool, str]:
        if not offer.get("url"):
            return False, "Affiliate recommendation rejected: Offer missing target URL."

        if offer.get("price", 0) <= 0:
            return False, "Affiliate recommendation rejected: Invalid price."

        return True, "Offer meets affiliate recommendation compliance rules."

policy_engine = PolicyEngine()
