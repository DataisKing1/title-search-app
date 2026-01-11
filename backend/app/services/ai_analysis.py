"""Enhanced AI Document Analysis Service

Provides advanced AI-powered analysis for title documents including:
- Document type-specific analysis prompts
- Entity extraction (names, dates, amounts)
- Legal description parsing
- Encumbrance detection
- Chain of title relationship extraction
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from app.config import settings
from app.models.document import DocumentType

logger = logging.getLogger(__name__)


class AnalysisConfidence(str, Enum):
    """Confidence levels for extracted data"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


# Document type-specific analysis prompts
DOCUMENT_PROMPTS = {
    DocumentType.DEED: """Analyze this DEED document for title insurance purposes.

Key information to extract:
1. **Parties**: Grantor(s) who are conveying property, Grantee(s) who are receiving property
2. **Deed Type**: Warranty Deed, Quitclaim Deed, Special Warranty Deed, etc.
3. **Legal Description**: Full property legal description (lot, block, subdivision, section/township/range)
4. **Consideration**: Purchase price or "love and affection" if gift
5. **Execution Date**: Date deed was signed
6. **Marital Status**: Spouses' names and marital status of grantors
7. **Encumbrances**: Any exceptions or reservations (mineral rights, easements, restrictions)
8. **Notary Information**: Notarization date, county, notary name

Flag any issues:
- Name discrepancies between document and prior records
- Missing marital status or spousal joinder
- Unusual reservations or exceptions
- Potential forged signatures or alterations""",

    DocumentType.MORTGAGE: """Analyze this MORTGAGE/DEED OF TRUST document for title insurance purposes.

Key information to extract:
1. **Borrower(s)**: Mortgagor/Trustor names and addresses
2. **Lender**: Mortgagee/Beneficiary name and address
3. **Loan Amount**: Principal amount of the loan
4. **Interest Rate**: If stated
5. **Maturity Date**: When loan is due
6. **Legal Description**: Property securing the loan
7. **Rider Types**: Any additional riders (PUD, Condominium, ARM, etc.)
8. **Assignment Provisions**: MERS clause, successor provisions

Flag any issues:
- Unrecorded assignments that may affect chain
- Missing signatures or acknowledgments
- Inconsistent property descriptions
- Signs of subordination agreements needed""",

    DocumentType.LIEN: """Analyze this LIEN document for title insurance purposes.

Key information to extract:
1. **Lien Type**: Mechanic's lien, Tax lien, Judgment lien, HOA lien, etc.
2. **Lienholder**: Creditor/Claimant name
3. **Property Owner**: Debtor/Owner name at time of lien
4. **Amount**: Lien amount (principal + interest + fees if stated)
5. **Recording Date**: When filed
6. **Expiration Date**: When lien expires (if applicable)
7. **Legal Description**: Property affected
8. **Priority**: Any stated priority position

Flag any issues:
- Potential priority disputes
- Expired liens that need releases
- Federal tax liens (special requirements)
- Lis pendens associated with lawsuit""",

    DocumentType.EASEMENT: """Analyze this EASEMENT document for title insurance purposes.

Key information to extract:
1. **Easement Type**: Utility, Access, Drainage, Conservation, etc.
2. **Servient Estate**: Property burdened by easement
3. **Dominant Estate**: Property benefiting (if appurtenant)
4. **Grantors/Grantees**: Parties creating and receiving easement
5. **Location/Description**: Where easement is located on property
6. **Purpose**: Specific use allowed
7. **Duration**: Perpetual or term
8. **Maintenance**: Who maintains the easement area

Flag any issues:
- Unclear or ambiguous easement location
- Potential conflicts with building improvements
- Access easement affecting marketability
- Utility easements affecting development potential""",

    DocumentType.RELEASE: """Analyze this RELEASE/SATISFACTION document for title insurance purposes.

Key information to extract:
1. **Document Being Released**: Original mortgage/lien reference
2. **Original Recording**: Book/page or reception number of original
3. **Borrower(s)**: Property owners at time of original recording
4. **Lender**: Entity providing the release
5. **Release Date**: Date of satisfaction
6. **Full vs Partial**: Whether it's a complete or partial release
7. **Property Description**: Property being released

Flag any issues:
- Mismatch between release and original document
- Partial release with remaining balance
- Corporate authorization questions
- Missing recording information for original""",

    DocumentType.LIS_PENDENS: """Analyze this LIS PENDENS (Notice of Pending Litigation) document.

Key information to extract:
1. **Case Information**: Court, case number, parties
2. **Nature of Action**: Foreclosure, quiet title, partition, etc.
3. **Property Affected**: Legal description
4. **Plaintiffs**: Who filed the action
5. **Defendants**: Property owners and other parties
6. **Relief Sought**: What the lawsuit demands
7. **Filing Date**: When the lis pendens was recorded

Flag any issues:
- Foreclosure indicating unpaid loans
- Quiet title action may indicate ownership dispute
- Partition action may affect entire property
- Expired lis pendens requiring dismissal verification""",
}

DEFAULT_PROMPT = """Analyze this title document for insurance purposes.

Extract all relevant information including:
1. Document type and purpose
2. All party names (grantor/grantee, buyer/seller, lender/borrower)
3. Recording information (date, book, page, instrument number)
4. Property legal description
5. Financial terms (consideration, loan amount)
6. Any encumbrances, restrictions, or exceptions
7. Any title concerns or defects noticed

Return structured data that can be used for title insurance underwriting."""


class AIDocumentAnalyzer:
    """Enhanced AI document analyzer for title insurance"""

    def __init__(self):
        self.provider = settings.DEFAULT_AI_PROVIDER
        self.model = settings.DEFAULT_AI_MODEL

    def get_analysis_prompt(self, document_type: DocumentType) -> str:
        """Get document type-specific analysis prompt"""
        base_prompt = DOCUMENT_PROMPTS.get(document_type, DEFAULT_PROMPT)

        return f"""{base_prompt}

IMPORTANT: Return your analysis as valid JSON with this structure:
{{
    "document_type": "detected document type",
    "document_subtype": "specific subtype (e.g., 'warranty_deed', 'mechanics_lien')",
    "summary": "2-3 sentence summary of the document",
    "parties": {{
        "grantor": ["list of grantor/seller/borrower names"],
        "grantee": ["list of grantee/buyer/lender names"],
        "additional_parties": ["witnesses, trustees, attorneys, etc."]
    }},
    "property": {{
        "legal_description": "full legal description text",
        "parsed_legal": {{
            "lot": "lot number if subdivision",
            "block": "block number if subdivision",
            "subdivision": "subdivision name",
            "section": "section if metes and bounds",
            "township": "township",
            "range": "range",
            "county": "county name",
            "street_address": "if mentioned"
        }}
    }},
    "financial": {{
        "consideration": "sale price or loan amount",
        "currency": "USD",
        "is_nominal": false
    }},
    "dates": {{
        "execution_date": "date signed (YYYY-MM-DD)",
        "recording_date": "date recorded (YYYY-MM-DD)",
        "effective_date": "effective date if different (YYYY-MM-DD)"
    }},
    "recording_info": {{
        "instrument_number": "reception/instrument number",
        "book": "book number",
        "page": "page number"
    }},
    "encumbrances": [
        {{
            "type": "easement/lien/restriction/mortgage",
            "description": "description of encumbrance",
            "holder": "who holds the encumbrance",
            "status": "active/released/unknown"
        }}
    ],
    "chain_of_title": {{
        "transfers_from": "prior owner if mentioned",
        "references": ["referenced document numbers or recordings"]
    }},
    "issues_detected": [
        {{
            "severity": "critical/warning/info",
            "category": "category of issue",
            "description": "description of potential problem",
            "recommendation": "suggested action"
        }}
    ],
    "confidence_scores": {{
        "overall": 0.85,
        "parties": 0.90,
        "legal_description": 0.75,
        "financial": 0.80
    }},
    "raw_extractions": {{
        "key_phrases": ["important phrases extracted"],
        "amounts_found": ["monetary amounts found in text"],
        "dates_found": ["dates found in text"]
    }}
}}"""

    async def analyze_document(
        self,
        text: str,
        document_type: DocumentType,
        instrument_number: Optional[str] = None,
        additional_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Perform comprehensive AI analysis on document text"""

        if not text or len(text.strip()) < 50:
            return {
                "success": False,
                "error": "Insufficient text for analysis",
                "confidence": 0
            }

        # Get document-specific prompt
        system_prompt = self.get_analysis_prompt(document_type)

        # Add any additional context
        context_str = ""
        if additional_context:
            context_str = f"\n\nAdditional context:\n{json.dumps(additional_context, indent=2)}"

        try:
            if self.provider == "openai":
                result = await self._analyze_openai(text, system_prompt, context_str)
            elif self.provider == "anthropic":
                result = await self._analyze_anthropic(text, system_prompt, context_str)
            else:
                result = await self._analyze_fallback(text, document_type)

            # Post-process results
            if result.get("success"):
                result["extracted_data"] = self._post_process_extraction(
                    result.get("extracted_data", {}),
                    text
                )

            return result

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Attempt fallback extraction
            return await self._analyze_fallback(text, document_type)

    async def _analyze_openai(
        self,
        text: str,
        system_prompt: str,
        context: str
    ) -> Dict[str, Any]:
        """Analyze with OpenAI"""
        try:
            from openai import AsyncOpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return {"success": False, "error": "OpenAI not configured"}

            client = AsyncOpenAI(api_key=api_key)

            # Truncate text if needed
            max_chars = settings.AI_TEXT_TRUNCATION_LIMIT
            truncated = text[:max_chars] if len(text) > max_chars else text

            response = await client.chat.completions.create(
                model=self.model or "gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this document:{context}\n\n{truncated}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            extracted = json.loads(content)

            return {
                "success": True,
                "extracted_data": extracted,
                "summary": extracted.get("summary", ""),
                "provider": "openai",
                "model": self.model
            }

        except ImportError:
            return {"success": False, "error": "OpenAI package not installed"}
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            return {"success": False, "error": str(e)}

    async def _analyze_anthropic(
        self,
        text: str,
        system_prompt: str,
        context: str
    ) -> Dict[str, Any]:
        """Analyze with Anthropic Claude"""
        try:
            from anthropic import AsyncAnthropic

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return {"success": False, "error": "Anthropic not configured"}

            client = AsyncAnthropic(api_key=api_key)

            max_chars = settings.AI_TEXT_TRUNCATION_LIMIT
            truncated = text[:max_chars] if len(text) > max_chars else text

            response = await client.messages.create(
                model=self.model or "claude-3-5-sonnet-20241022",
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Analyze this document and return JSON:{context}\n\n{truncated}"}
                ]
            )

            content = response.content[0].text

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                extracted = json.loads(json_match.group())
            else:
                extracted = {"summary": content}

            return {
                "success": True,
                "extracted_data": extracted,
                "summary": extracted.get("summary", ""),
                "provider": "anthropic",
                "model": self.model
            }

        except ImportError:
            return {"success": False, "error": "Anthropic package not installed"}
        except Exception as e:
            logger.error(f"Anthropic analysis error: {e}")
            return {"success": False, "error": str(e)}

    async def _analyze_fallback(
        self,
        text: str,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """Fallback regex-based extraction when AI is not available"""
        logger.info("Using fallback regex extraction")

        extracted = {
            "document_type": document_type.value,
            "summary": "Extracted via pattern matching (AI unavailable)",
            "parties": {
                "grantor": self._extract_party_names(text, "grantor"),
                "grantee": self._extract_party_names(text, "grantee"),
            },
            "dates": {
                "execution_date": self._extract_dates(text),
            },
            "financial": {
                "consideration": self._extract_amounts(text),
            },
            "property": {
                "legal_description": self._extract_legal_description(text),
            },
            "recording_info": self._extract_recording_info(text),
            "confidence_scores": {
                "overall": 0.4,
                "note": "Pattern matching only - AI analysis recommended"
            }
        }

        return {
            "success": True,
            "extracted_data": extracted,
            "summary": extracted.get("summary", ""),
            "provider": "fallback",
            "confidence": 0.4
        }

    def _post_process_extraction(
        self,
        data: Dict[str, Any],
        original_text: str
    ) -> Dict[str, Any]:
        """Post-process and validate AI extraction"""

        # Normalize party names
        if "parties" in data:
            for party_type in ["grantor", "grantee"]:
                if party_type in data["parties"]:
                    names = data["parties"][party_type]
                    if isinstance(names, list):
                        data["parties"][party_type] = [
                            self._normalize_name(n) for n in names if n
                        ]

        # Normalize dates
        if "dates" in data:
            for date_field in ["execution_date", "recording_date", "effective_date"]:
                if date_field in data["dates"]:
                    data["dates"][date_field] = self._normalize_date(
                        data["dates"][date_field]
                    )

        # Normalize amounts
        if "financial" in data and "consideration" in data["financial"]:
            data["financial"]["consideration"] = self._normalize_amount(
                data["financial"]["consideration"]
            )

        # Validate legal description
        if "property" in data and "legal_description" in data["property"]:
            legal = data["property"]["legal_description"]
            if legal and len(legal) < 20:
                # Too short, might be incomplete
                data["property"]["legal_description_warning"] = "May be incomplete"

        # Add verification flags
        data["_verification"] = {
            "processed_at": datetime.utcnow().isoformat(),
            "needs_human_review": self._needs_review(data)
        }

        return data

    def _normalize_name(self, name: str) -> str:
        """Normalize a party name"""
        if not name:
            return ""
        # Remove extra whitespace
        name = " ".join(name.split())
        # Title case for natural persons
        if not any(word in name.upper() for word in ["LLC", "INC", "CORP", "LP", "TRUST"]):
            name = name.title()
        return name

    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format"""
        if not date_str:
            return None

        patterns = [
            r"(\d{4})-(\d{1,2})-(\d{1,2})",
            r"(\d{1,2})/(\d{1,2})/(\d{4})",
            r"(\d{1,2})-(\d{1,2})-(\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, str(date_str))
            if match:
                groups = match.groups()
                if len(groups[0]) == 4:
                    return f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                else:
                    return f"{groups[2]}-{groups[0].zfill(2)}-{groups[1].zfill(2)}"

        return date_str

    def _normalize_amount(self, amount: Optional[str]) -> Optional[str]:
        """Normalize monetary amount"""
        if not amount:
            return None

        # Extract numbers
        numbers = re.findall(r'[\d,]+\.?\d*', str(amount))
        if numbers:
            # Take the first substantial number
            for num in numbers:
                cleaned = num.replace(",", "")
                try:
                    value = float(cleaned)
                    if value >= 1:
                        return f"${value:,.2f}"
                except ValueError:
                    continue

        return amount

    def _extract_party_names(self, text: str, party_type: str) -> List[str]:
        """Extract party names using regex patterns"""
        names = []

        if party_type == "grantor":
            patterns = [
                r"[Gg]rantor[s]?\s*[:;]?\s*([A-Z][a-zA-Z\s,&]+?)(?=\s*,?\s*[Gg]rantee|\s*to\s+|\s*does|\s*hereby)",
                r"([A-Z][a-zA-Z\s,&]+?)\s*,?\s*hereinafter\s+(?:called|referred)",
            ]
        else:
            patterns = [
                r"[Gg]rantee[s]?\s*[:;]?\s*([A-Z][a-zA-Z\s,&]+?)(?=\s*,?\s*$|\s*whose|\s*\.)",
                r"to\s+([A-Z][a-zA-Z\s,&]+?)(?=\s*,?\s*(?:whose|a|an|\.))",
            ]

        for pattern in patterns:
            matches = re.findall(pattern, text[:5000])
            for match in matches:
                cleaned = match.strip().rstrip(",")
                if len(cleaned) > 3 and len(cleaned) < 100:
                    names.append(cleaned)

        return list(set(names))[:5]  # Limit to 5 unique names

    def _extract_dates(self, text: str) -> Optional[str]:
        """Extract dates from text"""
        patterns = [
            r'(?:dated|executed|signed)\s+(?:this\s+)?(\d{1,2})\s+day\s+of\s+(\w+),?\s+(\d{4})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    def _extract_amounts(self, text: str) -> Optional[str]:
        """Extract monetary amounts from text"""
        patterns = [
            r'\$\s*([\d,]+(?:\.\d{2})?)',
            r'([\d,]+(?:\.\d{2})?)\s+[Dd]ollars',
            r'consideration\s+of\s+\$?\s*([\d,]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:3000])
            if match:
                return f"${match.group(1)}"

        return None

    def _extract_legal_description(self, text: str) -> Optional[str]:
        """Extract legal description from text"""
        patterns = [
            r'[Ll]egal\s+[Dd]escription[:;\s]+(.{50,500}?)(?=\s*[Ss]ubject|\s*[Ee]xcept|\s*[Tt]ogether|\s*\n\n)',
            r'[Ll]ot\s+\d+[,\s]+[Bb]lock\s+\d+[,\s]+([A-Za-z\s]+?)(?:\s+according|\s+as|\s+County)',
            r'[Ss]ection\s+\d+,?\s+[Tt]ownship\s+\d+[NS],?\s+[Rr]ange\s+\d+[EW]',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(0).strip()

        return None

    def _extract_recording_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract recording information"""
        info = {
            "instrument_number": None,
            "book": None,
            "page": None
        }

        # Instrument/Reception number
        inst_match = re.search(r'(?:[Rr]eception|[Ii]nstrument)\s*(?:[Nn]o\.?|#)?\s*[:;]?\s*(\d{5,})', text)
        if inst_match:
            info["instrument_number"] = inst_match.group(1)

        # Book
        book_match = re.search(r'[Bb]ook\s*[:;]?\s*(\d+)', text)
        if book_match:
            info["book"] = book_match.group(1)

        # Page
        page_match = re.search(r'[Pp]age\s*[:;]?\s*(\d+)', text)
        if page_match:
            info["page"] = page_match.group(1)

        return info

    def _needs_review(self, data: Dict[str, Any]) -> bool:
        """Determine if extracted data needs human review"""
        # Check for issues
        issues = data.get("issues_detected", [])
        if any(issue.get("severity") == "critical" for issue in issues):
            return True

        # Check confidence
        confidence = data.get("confidence_scores", {}).get("overall", 0)
        if confidence < 0.7:
            return True

        # Check for missing critical data
        parties = data.get("parties", {})
        if not parties.get("grantor") and not parties.get("grantee"):
            return True

        return False


# Create singleton instance
analyzer = AIDocumentAnalyzer()


async def analyze_document_text(
    text: str,
    document_type: DocumentType,
    instrument_number: Optional[str] = None,
    additional_context: Optional[Dict] = None
) -> Dict[str, Any]:
    """Convenience function for document analysis"""
    return await analyzer.analyze_document(
        text=text,
        document_type=document_type,
        instrument_number=instrument_number,
        additional_context=additional_context
    )
