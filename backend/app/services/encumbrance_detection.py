"""Encumbrance Detection Service

Detects and creates encumbrances from document analysis.
Identifies liens, mortgages, easements, and other title issues.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal

from app.models.document import Document, DocumentType
from app.models.encumbrance import Encumbrance, EncumbranceType, EncumbranceStatus

logger = logging.getLogger(__name__)


# Mapping from DocumentType to EncumbranceType
DOCUMENT_TO_ENCUMBRANCE_TYPE = {
    DocumentType.MORTGAGE: EncumbranceType.MORTGAGE,
    DocumentType.DEED_OF_TRUST: EncumbranceType.DEED_OF_TRUST,
    DocumentType.LIEN: EncumbranceType.MECHANICS_LIEN,  # Default, will be refined
    DocumentType.JUDGMENT: EncumbranceType.JUDGMENT_LIEN,
    DocumentType.EASEMENT: EncumbranceType.EASEMENT,
    DocumentType.LIS_PENDENS: EncumbranceType.LIS_PENDENS,
    DocumentType.BANKRUPTCY: EncumbranceType.BANKRUPTCY,
    DocumentType.UCC_FILING: EncumbranceType.UCC_FILING,
}


# Keywords for detecting specific lien types
LIEN_TYPE_KEYWORDS = {
    EncumbranceType.MECHANICS_LIEN: [
        "mechanic's lien", "mechanics lien", "materialman's lien",
        "construction lien", "contractor's lien", "labor lien"
    ],
    EncumbranceType.TAX_LIEN: [
        "tax lien", "property tax", "delinquent tax", "tax sale"
    ],
    EncumbranceType.IRS_LIEN: [
        "federal tax lien", "irs lien", "internal revenue", "irs"
    ],
    EncumbranceType.STATE_TAX_LIEN: [
        "state tax lien", "colorado department of revenue"
    ],
    EncumbranceType.HOA_LIEN: [
        "hoa lien", "homeowner's association", "association lien",
        "assessment lien", "condo association"
    ],
    EncumbranceType.JUDGMENT_LIEN: [
        "judgment lien", "abstract of judgment", "court judgment",
        "civil judgment"
    ],
}


# Keywords indicating a release/satisfaction
RELEASE_KEYWORDS = [
    "release", "satisfaction", "reconveyance", "discharged",
    "paid in full", "satisfied", "released of record"
]


class EncumbranceDetector:
    """Detects encumbrances from document analysis"""

    def detect_from_document(
        self,
        document: Document,
        ai_extracted_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if a document represents an encumbrance.

        Args:
            document: The document to analyze
            ai_extracted_data: Optional AI-extracted data from the document

        Returns:
            Dictionary with encumbrance details if detected, None otherwise
        """
        # Check if document type is an encumbrance type
        enc_type = DOCUMENT_TO_ENCUMBRANCE_TYPE.get(document.document_type)

        if not enc_type:
            # Check if it's a release (affects existing encumbrance)
            if document.document_type in [DocumentType.RELEASE, DocumentType.SATISFACTION]:
                return self._detect_release(document, ai_extracted_data)
            return None

        # Get text content for analysis
        text = document.ocr_text or ""
        if ai_extracted_data:
            text += " " + str(ai_extracted_data.get("summary", ""))

        # Refine lien type if it's a generic lien
        if document.document_type == DocumentType.LIEN:
            enc_type = self._refine_lien_type(text)

        # Detect status (might be a release even if typed as lien/mortgage)
        is_release = self._is_release_document(text)
        status = EncumbranceStatus.RELEASED if is_release else EncumbranceStatus.ACTIVE

        # Extract holder name
        holder = self._extract_holder(document, ai_extracted_data, enc_type)

        # Extract amounts
        original_amount, current_amount = self._extract_amounts(
            document, ai_extracted_data, text
        )

        # Calculate risk level
        risk_level = self._calculate_risk_level(enc_type, status, original_amount)

        return {
            "encumbrance_type": enc_type,
            "status": status,
            "holder_name": holder,
            "original_amount": original_amount,
            "current_amount": current_amount,
            "recorded_date": document.recording_date,
            "recording_reference": self._get_recording_reference(document),
            "description": self._generate_description(document, enc_type, holder),
            "risk_level": risk_level,
            "requires_action": status == EncumbranceStatus.ACTIVE,
            "action_description": self._get_action_description(enc_type, status),
        }

    def _detect_release(
        self,
        document: Document,
        ai_extracted_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect a release document and identify what it releases"""
        # This is a release - it affects an existing encumbrance
        # Return info about finding and updating the original encumbrance

        # Try to find the original recording reference
        original_ref = None
        if ai_extracted_data:
            refs = ai_extracted_data.get("chain_of_title", {}).get("references", [])
            if refs:
                original_ref = refs[0]

        return {
            "is_release": True,
            "original_reference": original_ref,
            "release_date": document.recording_date,
            "release_recording_reference": self._get_recording_reference(document),
        }

    def _refine_lien_type(self, text: str) -> EncumbranceType:
        """Refine a generic lien to a specific type based on content"""
        text_lower = text.lower()

        for lien_type, keywords in LIEN_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return lien_type

        return EncumbranceType.MECHANICS_LIEN  # Default

    def _is_release_document(self, text: str) -> bool:
        """Check if document text indicates it's a release"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in RELEASE_KEYWORDS)

    def _extract_holder(
        self,
        document: Document,
        ai_extracted_data: Optional[Dict[str, Any]],
        enc_type: EncumbranceType
    ) -> Optional[str]:
        """Extract the holder/beneficiary name"""
        # Try AI extraction first
        if ai_extracted_data:
            parties = ai_extracted_data.get("parties", {})

            # For liens, the holder is usually the grantee/beneficiary
            if enc_type in [
                EncumbranceType.MORTGAGE, EncumbranceType.DEED_OF_TRUST
            ]:
                grantees = parties.get("grantee", [])
                if grantees:
                    return grantees[0] if isinstance(grantees, list) else grantees

            # For other encumbrances
            additional = parties.get("additional_parties", [])
            if additional:
                return additional[0]

        # Fall back to document grantee
        if document.grantee:
            grantees = document.grantee
            if isinstance(grantees, list) and grantees:
                return grantees[0]
            return str(grantees)

        return None

    def _extract_amounts(
        self,
        document: Document,
        ai_extracted_data: Optional[Dict[str, Any]],
        text: str
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract original and current amounts"""
        original = None
        current = None

        # Try AI extraction
        if ai_extracted_data:
            financial = ai_extracted_data.get("financial", {})
            consideration = financial.get("consideration")
            if consideration:
                original = self._parse_amount(consideration)
                current = original  # Assume current equals original initially

        # Try document consideration
        if not original and document.consideration:
            original = self._parse_amount(document.consideration)
            current = original

        # Try regex extraction from text
        if not original and text:
            amount_patterns = [
                r'\$\s*([\d,]+(?:\.\d{2})?)',
                r'([\d,]+(?:\.\d{2})?)\s+[Dd]ollars',
                r'[Aa]mount[:\s]+\$?\s*([\d,]+)',
                r'[Pp]rincipal[:\s]+\$?\s*([\d,]+)',
            ]

            for pattern in amount_patterns:
                match = re.search(pattern, text)
                if match:
                    original = self._parse_amount(match.group(1))
                    current = original
                    break

        return original, current

    def _parse_amount(self, amount_str: str) -> Optional[Decimal]:
        """Parse an amount string to Decimal"""
        if not amount_str:
            return None

        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,]', '', str(amount_str))
            # Extract first number
            match = re.search(r'[\d.]+', cleaned)
            if match:
                return Decimal(match.group())
        except Exception:
            pass

        return None

    def _get_recording_reference(self, document: Document) -> str:
        """Get recording reference from document"""
        parts = []
        if document.instrument_number:
            parts.append(f"Reception #{document.instrument_number}")
        if document.book and document.page:
            parts.append(f"Book {document.book}, Page {document.page}")
        return "; ".join(parts) if parts else ""

    def _generate_description(
        self,
        document: Document,
        enc_type: EncumbranceType,
        holder: Optional[str]
    ) -> str:
        """Generate a description for the encumbrance"""
        type_names = {
            EncumbranceType.MORTGAGE: "Mortgage",
            EncumbranceType.DEED_OF_TRUST: "Deed of Trust",
            EncumbranceType.TAX_LIEN: "Tax Lien",
            EncumbranceType.MECHANICS_LIEN: "Mechanic's Lien",
            EncumbranceType.JUDGMENT_LIEN: "Judgment Lien",
            EncumbranceType.HOA_LIEN: "HOA Lien",
            EncumbranceType.IRS_LIEN: "Federal Tax Lien",
            EncumbranceType.STATE_TAX_LIEN: "State Tax Lien",
            EncumbranceType.EASEMENT: "Easement",
            EncumbranceType.RESTRICTION: "Restriction",
            EncumbranceType.COVENANT: "Covenant",
            EncumbranceType.LIS_PENDENS: "Lis Pendens",
            EncumbranceType.BANKRUPTCY: "Bankruptcy",
            EncumbranceType.UCC_FILING: "UCC Filing",
            EncumbranceType.ASSESSMENT: "Assessment",
            EncumbranceType.OTHER: "Encumbrance",
        }

        type_name = type_names.get(enc_type, "Encumbrance")
        parts = [type_name]

        if holder:
            parts.append(f"in favor of {holder}")

        if document.recording_date:
            parts.append(f"recorded {document.recording_date.strftime('%m/%d/%Y')}")

        return " ".join(parts)

    def _calculate_risk_level(
        self,
        enc_type: EncumbranceType,
        status: EncumbranceStatus,
        amount: Optional[Decimal]
    ) -> str:
        """Calculate risk level for the encumbrance"""
        if status in [EncumbranceStatus.RELEASED, EncumbranceStatus.SATISFIED]:
            return "low"

        # Critical risk types
        if enc_type in [
            EncumbranceType.IRS_LIEN,
            EncumbranceType.JUDGMENT_LIEN,
            EncumbranceType.LIS_PENDENS,
            EncumbranceType.BANKRUPTCY,
        ]:
            return "critical"

        # High risk types
        if enc_type in [
            EncumbranceType.TAX_LIEN,
            EncumbranceType.STATE_TAX_LIEN,
            EncumbranceType.MECHANICS_LIEN,
        ]:
            return "high"

        # Check amount for mortgages
        if enc_type in [EncumbranceType.MORTGAGE, EncumbranceType.DEED_OF_TRUST]:
            if amount and amount > 100000:
                return "high"
            return "medium"

        return "medium"

    def _get_action_description(
        self,
        enc_type: EncumbranceType,
        status: EncumbranceStatus
    ) -> Optional[str]:
        """Get recommended action for the encumbrance"""
        if status in [EncumbranceStatus.RELEASED, EncumbranceStatus.SATISFIED]:
            return "Verify release is properly recorded."

        actions = {
            EncumbranceType.MORTGAGE: "Obtain payoff statement and arrange for satisfaction at closing.",
            EncumbranceType.DEED_OF_TRUST: "Obtain payoff statement and arrange for reconveyance at closing.",
            EncumbranceType.TAX_LIEN: "Obtain tax certificate showing current status. Pay prior to closing.",
            EncumbranceType.MECHANICS_LIEN: "Obtain lien waiver or arrange payment from closing funds.",
            EncumbranceType.JUDGMENT_LIEN: "Obtain payoff amount. May require satisfaction agreement.",
            EncumbranceType.IRS_LIEN: "Contact IRS for payoff. May require Certificate of Discharge.",
            EncumbranceType.HOA_LIEN: "Obtain estoppel letter from HOA showing amounts due.",
            EncumbranceType.LIS_PENDENS: "Review pending litigation. May need court approval for sale.",
            EncumbranceType.BANKRUPTCY: "Verify case status. May require court approval for sale.",
            EncumbranceType.EASEMENT: "Review for impact on use of property.",
        }

        return actions.get(enc_type, "Review and determine appropriate action.")


def detect_encumbrances_from_documents(
    documents: List[Document]
) -> List[Dict[str, Any]]:
    """
    Detect encumbrances from a list of documents.

    Args:
        documents: List of documents to analyze

    Returns:
        List of detected encumbrance dictionaries
    """
    detector = EncumbranceDetector()
    encumbrances = []
    releases = []

    for doc in documents:
        result = detector.detect_from_document(
            doc,
            doc.ai_extracted_data
        )

        if result:
            if result.get("is_release"):
                releases.append({
                    "document_id": doc.id,
                    **result
                })
            else:
                encumbrances.append({
                    "document_id": doc.id,
                    **result
                })

    # Match releases to encumbrances
    for release in releases:
        original_ref = release.get("original_reference")
        if original_ref:
            for enc in encumbrances:
                if original_ref in (enc.get("recording_reference") or ""):
                    enc["status"] = EncumbranceStatus.RELEASED
                    enc["released_date"] = release.get("release_date")
                    enc["requires_action"] = False
                    enc["action_description"] = "Release recorded."
                    break

    return encumbrances


def create_encumbrance_from_detection(
    search_id: int,
    document_id: int,
    detection: Dict[str, Any]
) -> Encumbrance:
    """
    Create an Encumbrance object from detection results.

    Args:
        search_id: ID of the title search
        document_id: ID of the source document
        detection: Detection results dictionary

    Returns:
        Encumbrance model instance (not saved to DB)
    """
    return Encumbrance(
        search_id=search_id,
        document_id=document_id,
        encumbrance_type=detection["encumbrance_type"],
        status=detection.get("status", EncumbranceStatus.ACTIVE),
        holder_name=detection.get("holder_name"),
        original_amount=detection.get("original_amount"),
        current_amount=detection.get("current_amount"),
        recorded_date=detection.get("recorded_date"),
        released_date=detection.get("released_date"),
        recording_reference=detection.get("recording_reference"),
        description=detection.get("description"),
        risk_level=detection.get("risk_level", "medium"),
        risk_notes=None,
        requires_action=detection.get("requires_action", True),
        action_description=detection.get("action_description"),
    )
