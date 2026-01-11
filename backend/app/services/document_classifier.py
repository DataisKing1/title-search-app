"""Document Classification Service

Classifies title documents based on content analysis using both
pattern matching and AI when available.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from app.models.document import DocumentType

logger = logging.getLogger(__name__)


# Document classification patterns with weighted scoring
CLASSIFICATION_PATTERNS = {
    DocumentType.DEED: {
        "strong": [
            (r"\bwarranty\s+deed\b", 30),
            (r"\bquit\s*claim\s+deed\b", 30),
            (r"\bquitclaim\s+deed\b", 30),
            (r"\bspecial\s+warranty\s+deed\b", 30),
            (r"\bgrant\s+deed\b", 30),
            (r"\bbargain\s+and\s+sale\s+deed\b", 25),
            (r"\btax\s+deed\b", 25),
            (r"\btrustee'?s\s+deed\b", 25),
            (r"\bpersonal\s+representative'?s?\s+deed\b", 25),
            (r"\bcorrection\s+deed\b", 25),
        ],
        "medium": [
            (r"\bgrantor\b.*\bgrantee\b", 15),
            (r"\bconvey(?:s|ed)?\s+and\s+warrant", 15),
            (r"\bremise,?\s+release,?\s+(?:and\s+)?(?:quit)?claim", 12),
            (r"\bgrant,?\s+bargain,?\s+(?:and\s+)?sell", 12),
            (r"\bhereby\s+grants?\b", 10),
        ],
        "weak": [
            (r"\bproperty\s+(?:at|located)\b", 5),
            (r"\bcounty\s+of\b.*\bstate\s+of\b", 5),
            (r"\blegaldescription\b", 5),
        ],
    },
    DocumentType.MORTGAGE: {
        "strong": [
            (r"\bmortgage\b", 25),
            (r"\bopen-?end\s+mortgage\b", 30),
            (r"\bfuture\s+advance\s+mortgage\b", 30),
            (r"\breverse\s+mortgage\b", 30),
        ],
        "medium": [
            (r"\bmortgagor\b.*\bmortgagee\b", 20),
            (r"\bsecure\s+(?:the\s+)?(?:payment|repayment)\b", 15),
            (r"\bpower\s+of\s+sale\b", 10),
            (r"\bpromissory\s+note\b", 10),
        ],
        "weak": [
            (r"\bprincipal\s+(?:sum|amount)\b", 5),
            (r"\binterest\s+rate\b", 5),
        ],
    },
    DocumentType.DEED_OF_TRUST: {
        "strong": [
            (r"\bdeed\s+of\s+trust\b", 30),
            (r"\btrust\s+deed\b", 25),
            (r"\bshort\s+form\s+deed\s+of\s+trust\b", 30),
        ],
        "medium": [
            (r"\btrustor\b.*\btrustee\b.*\bbeneficiary\b", 20),
            (r"\btrustor\b.*\bbeneficiary\b", 15),
            (r"\btrustee\b.*\bbeneficiary\b", 15),
            (r"\birrevocable\s+power\s+of\s+attorney\b", 10),
        ],
        "weak": [
            (r"\bpublic\s+trustee\b", 8),
            (r"\bforeclosure\b", 5),
        ],
    },
    DocumentType.LIEN: {
        "strong": [
            (r"\bmechanic'?s?\s+lien\b", 30),
            (r"\bmaterialman'?s?\s+lien\b", 30),
            (r"\bconstruction\s+lien\b", 30),
            (r"\bhoa\s+lien\b", 30),
            (r"\bassociation\s+lien\b", 25),
            (r"\bstate\s+tax\s+lien\b", 30),
            (r"\bfederal\s+tax\s+lien\b", 30),
            (r"\birs\s+(?:tax\s+)?lien\b", 30),
            (r"\bnotice\s+of\s+lien\b", 25),
        ],
        "medium": [
            (r"\blienholder\b", 15),
            (r"\blien\s+claimant\b", 15),
            (r"\bstatement\s+of\s+lien\b", 15),
            (r"\bclaim\s+of\s+lien\b", 15),
        ],
        "weak": [
            (r"\bsubcontractor\b", 5),
            (r"\bimprovement\b.*\bproperty\b", 5),
        ],
    },
    DocumentType.JUDGMENT: {
        "strong": [
            (r"\bjudgment\s+lien\b", 30),
            (r"\babstract\s+of\s+judgment\b", 30),
            (r"\btranscript\s+of\s+judgment\b", 30),
            (r"\bcertificate\s+of\s+judgment\b", 30),
        ],
        "medium": [
            (r"\bjudgment\s+(?:creditor|debtor)\b", 15),
            (r"\bcourt\s+(?:ordered|judgment)\b", 12),
            (r"\bjudgment\s+amount\b", 10),
        ],
        "weak": [
            (r"\bdistrict\s+court\b", 5),
            (r"\bcounty\s+court\b", 5),
        ],
    },
    DocumentType.EASEMENT: {
        "strong": [
            (r"\beasement\s+(?:agreement|grant|deed)\b", 30),
            (r"\bgrant\s+of\s+easement\b", 30),
            (r"\butility\s+easement\b", 30),
            (r"\baccess\s+easement\b", 30),
            (r"\bdrainage\s+easement\b", 30),
            (r"\bconservation\s+easement\b", 30),
            (r"\bright\s+of\s+way\b", 20),
        ],
        "medium": [
            (r"\bservient\s+(?:estate|tenement)\b", 15),
            (r"\bdominant\s+(?:estate|tenement)\b", 15),
            (r"\beasement\s+(?:appurtenant|in\s+gross)\b", 15),
        ],
        "weak": [
            (r"\bperpetual\s+(?:right|easement)\b", 8),
            (r"\bingress\s+(?:and\s+)?egress\b", 8),
        ],
    },
    DocumentType.PLAT: {
        "strong": [
            (r"\bplat\s+of\b", 30),
            (r"\bfinal\s+plat\b", 30),
            (r"\bsubdivision\s+plat\b", 30),
            (r"\brecorded\s+plat\b", 25),
            (r"\bamended\s+plat\b", 25),
            (r"\breplat\b", 25),
        ],
        "medium": [
            (r"\bsurvey\s+(?:map|plat)\b", 15),
            (r"\blot\s+and\s+block\b", 12),
            (r"\bsubdivision\s+map\b", 12),
        ],
        "weak": [
            (r"\bsurvey(?:or|ed)\b", 5),
            (r"\bboundary\s+lines?\b", 5),
        ],
    },
    DocumentType.RELEASE: {
        "strong": [
            (r"\brelease\s+of\s+(?:lien|mortgage|deed\s+of\s+trust)\b", 30),
            (r"\bsatisfaction\s+of\s+(?:mortgage|judgment)\b", 30),
            (r"\bfull\s+reconveyance\b", 30),
            (r"\brelease\s+of\s+(?:mechanics?\s+)?lien\b", 30),
            (r"\bdeed\s+of\s+release\b", 25),
            (r"\bmarginal\s+release\b", 25),
        ],
        "medium": [
            (r"\bpaid\s+in\s+full\b", 15),
            (r"\bsatisfied\s+(?:in\s+full|and\s+discharged)\b", 15),
            (r"\breleases?\s+(?:and\s+)?discharg(?:es?|ed)\b", 12),
        ],
        "weak": [
            (r"\breconveyance\b", 8),
            (r"\bdischarged?\b", 5),
        ],
    },
    DocumentType.SATISFACTION: {
        "strong": [
            (r"\bsatisfaction\s+(?:piece|of\s+mortgage)\b", 30),
            (r"\bcertificate\s+of\s+satisfaction\b", 30),
            (r"\bfull\s+satisfaction\b", 25),
        ],
        "medium": [
            (r"\bfully\s+paid\s+(?:and\s+)?satisfied\b", 15),
            (r"\bmortgage\s+(?:is\s+)?satisfied\b", 12),
        ],
        "weak": [
            (r"\bdischarge\s+of\s+mortgage\b", 8),
        ],
    },
    DocumentType.ASSIGNMENT: {
        "strong": [
            (r"\bassignment\s+of\s+(?:mortgage|deed\s+of\s+trust|rents?|leases?)\b", 30),
            (r"\bcorporate\s+assignment\b", 25),
            (r"\bassignment\s+and\s+assumption\b", 25),
        ],
        "medium": [
            (r"\bassignor\b.*\bassignee\b", 15),
            (r"\bhereby\s+assigns?\b", 12),
            (r"\btransfer\s+(?:and\s+)?assign\b", 10),
        ],
        "weak": [
            (r"\bsuccessor\s+in\s+interest\b", 8),
        ],
    },
    DocumentType.SUBORDINATION: {
        "strong": [
            (r"\bsubordination\s+agreement\b", 30),
            (r"\bsubordination,?\s+non-?disturbance,?\s+(?:and\s+)?attornment\b", 30),
            (r"\bsnda\b", 25),
        ],
        "medium": [
            (r"\bsubordinate\s+(?:to|its\s+lien)\b", 15),
            (r"\bsenior\s+(?:lien|mortgage)\b", 10),
            (r"\bjunior\s+(?:lien|mortgage)\b", 10),
        ],
        "weak": [
            (r"\blien\s+priority\b", 8),
        ],
    },
    DocumentType.LIS_PENDENS: {
        "strong": [
            (r"\blis\s+pendens\b", 30),
            (r"\bnotice\s+of\s+(?:pending\s+)?(?:action|litigation)\b", 30),
            (r"\bpendency\s+of\s+action\b", 25),
        ],
        "medium": [
            (r"\bforeclosure\s+(?:action|proceeding)\b", 15),
            (r"\bquiet\s+title\s+action\b", 15),
            (r"\bpartition\s+action\b", 15),
        ],
        "weak": [
            (r"\bcourt\s+case\s+(?:no|number)\b", 5),
        ],
    },
    DocumentType.BANKRUPTCY: {
        "strong": [
            (r"\bbankruptcy\s+(?:petition|case|filing)\b", 30),
            (r"\bchapter\s+(?:7|11|13)\s+bankruptcy\b", 30),
            (r"\bnotice\s+of\s+bankruptcy\b", 30),
        ],
        "medium": [
            (r"\bbankruptcy\s+court\b", 15),
            (r"\bdebtor\s+in\s+(?:possession|bankruptcy)\b", 12),
            (r"\bautomatic\s+stay\b", 10),
        ],
        "weak": [
            (r"\bbankrupt\b", 5),
            (r"\bdischarge\s+(?:of|in)\s+bankruptcy\b", 8),
        ],
    },
    DocumentType.UCC_FILING: {
        "strong": [
            (r"\bucc[-\s]?(?:1|financing\s+statement)\b", 30),
            (r"\bfinancing\s+statement\b", 25),
            (r"\bucc\s+filing\b", 25),
        ],
        "medium": [
            (r"\bsecured\s+party\b", 15),
            (r"\bcollateral\s+description\b", 12),
            (r"\bdebtor\b.*\bsecured\s+party\b", 12),
        ],
        "weak": [
            (r"\bfixtures?\b", 5),
            (r"\bpersonal\s+property\b", 5),
        ],
    },
    DocumentType.SURVEY: {
        "strong": [
            (r"\balta[/-]?(?:acsm|nsps)?\s+survey\b", 30),
            (r"\bboundary\s+survey\b", 30),
            (r"\bimprovement\s+location\s+certificate\b", 30),
            (r"\bilc\b", 20),
        ],
        "medium": [
            (r"\bsurveyor'?s?\s+certificate\b", 15),
            (r"\bmetes\s+and\s+bounds\b", 12),
            (r"\bpoint\s+of\s+beginning\b", 12),
        ],
        "weak": [
            (r"\bsurveyed\s+by\b", 8),
            (r"\bbearing\s+(?:and\s+)?distance\b", 5),
        ],
    },
    DocumentType.TAX_RECORD: {
        "strong": [
            (r"\bproperty\s+tax\s+(?:statement|record)\b", 30),
            (r"\btax\s+(?:certificate|sale)\b", 25),
            (r"\btax\s+deed\b", 25),
        ],
        "medium": [
            (r"\bassessed\s+value\b", 12),
            (r"\btax\s+(?:parcel|account)\s+(?:no|number)\b", 12),
        ],
        "weak": [
            (r"\bmill\s+levy\b", 5),
            (r"\btaxable\s+value\b", 5),
        ],
    },
    DocumentType.COURT_FILING: {
        "strong": [
            (r"\bdecree\s+(?:of|in)\s+(?:divorce|dissolution)\b", 30),
            (r"\bprobate\s+(?:order|decree)\b", 30),
            (r"\bcourt\s+order\b", 25),
        ],
        "medium": [
            (r"\bdistrict\s+court\s+(?:of|for)\b", 12),
            (r"\bin\s+the\s+matter\s+of\b", 10),
            (r"\bcause\s+no\b", 10),
        ],
        "weak": [
            (r"\bcourt\s+clerk\b", 5),
            (r"\bfiled\s+(?:in|with)\s+court\b", 5),
        ],
    },
}


class DocumentClassifier:
    """Classifies title documents based on content"""

    def __init__(self):
        self.patterns = CLASSIFICATION_PATTERNS

    def classify(
        self,
        text: str,
        filename: Optional[str] = None,
        raw_doc_type: Optional[str] = None
    ) -> Tuple[DocumentType, float, Dict[str, Any]]:
        """
        Classify a document based on its content.

        Args:
            text: Document text content
            filename: Optional filename for additional hints
            raw_doc_type: Optional raw document type from scraper

        Returns:
            Tuple of (DocumentType, confidence_score, classification_details)
        """
        if not text:
            return DocumentType.OTHER, 0.0, {"reason": "No text provided"}

        text_lower = text.lower()
        scores = {}
        matches = {}

        # Score each document type
        for doc_type, pattern_groups in self.patterns.items():
            type_score = 0
            type_matches = []

            for strength, patterns in pattern_groups.items():
                for pattern, weight in patterns:
                    found = re.findall(pattern, text_lower, re.IGNORECASE)
                    if found:
                        type_score += weight * min(len(found), 3)
                        type_matches.append({
                            "pattern": pattern,
                            "strength": strength,
                            "count": len(found),
                            "weight": weight
                        })

            scores[doc_type] = type_score
            matches[doc_type] = type_matches

        # Boost from raw doc type if available
        if raw_doc_type:
            mapped_type = self._map_raw_type(raw_doc_type)
            if mapped_type in scores:
                scores[mapped_type] += 20

        # Boost from filename
        if filename:
            filename_type = self._classify_from_filename(filename)
            if filename_type in scores:
                scores[filename_type] += 15

        # Find best match
        if not scores or max(scores.values()) == 0:
            return DocumentType.OTHER, 0.0, {
                "reason": "No matching patterns found",
                "text_length": len(text)
            }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        # Calculate confidence (0-1 scale)
        max_possible = 100  # Approximate max score for strong match
        confidence = min(best_score / max_possible, 1.0)

        # If confidence is too low, return OTHER
        if confidence < 0.15:
            return DocumentType.OTHER, confidence, {
                "reason": "Low confidence match",
                "best_guess": best_type.value,
                "scores": {k.value: v for k, v in scores.items() if v > 0}
            }

        details = {
            "matches": matches.get(best_type, [])[:5],
            "score": best_score,
            "all_scores": {k.value: v for k, v in sorted(
                scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5] if v > 0},
            "boosted_by": []
        }

        if raw_doc_type:
            details["boosted_by"].append(f"raw_type:{raw_doc_type}")
        if filename:
            details["boosted_by"].append(f"filename")

        return best_type, confidence, details

    def _map_raw_type(self, raw_type: str) -> Optional[DocumentType]:
        """Map raw document type codes to DocumentType enum"""
        raw_upper = raw_type.upper().strip()

        # Direct mappings
        mappings = {
            # Deeds
            "DEED": DocumentType.DEED,
            "WD": DocumentType.DEED,
            "QCD": DocumentType.DEED,
            "SWD": DocumentType.DEED,
            "SPWD": DocumentType.DEED,
            "BD": DocumentType.DEED,
            "TD": DocumentType.DEED_OF_TRUST,
            "WARRANTY DEED": DocumentType.DEED,
            "QUIT CLAIM DEED": DocumentType.DEED,
            "QUITCLAIM": DocumentType.DEED,

            # Mortgages/Deeds of Trust
            "MORT": DocumentType.MORTGAGE,
            "MTG": DocumentType.MORTGAGE,
            "MORTGAGE": DocumentType.MORTGAGE,
            "DOT": DocumentType.DEED_OF_TRUST,
            "DTD": DocumentType.DEED_OF_TRUST,
            "DEED OF TRUST": DocumentType.DEED_OF_TRUST,

            # Liens
            "LIEN": DocumentType.LIEN,
            "ML": DocumentType.LIEN,
            "MECHL": DocumentType.LIEN,
            "MECHANIC'S LIEN": DocumentType.LIEN,
            "MECHANICS LIEN": DocumentType.LIEN,
            "FTL": DocumentType.LIEN,
            "FEDERAL TAX LIEN": DocumentType.LIEN,
            "STL": DocumentType.LIEN,
            "STATE TAX LIEN": DocumentType.LIEN,
            "HOA": DocumentType.LIEN,

            # Judgments
            "JL": DocumentType.JUDGMENT,
            "JUDG": DocumentType.JUDGMENT,
            "JUDGMENT": DocumentType.JUDGMENT,
            "JUDGMENT LIEN": DocumentType.JUDGMENT,

            # Easements
            "EASE": DocumentType.EASEMENT,
            "ESMT": DocumentType.EASEMENT,
            "EASEMENT": DocumentType.EASEMENT,
            "ROW": DocumentType.EASEMENT,
            "RIGHT OF WAY": DocumentType.EASEMENT,

            # Plats
            "PLAT": DocumentType.PLAT,
            "SUBDIVISION": DocumentType.PLAT,
            "MAP": DocumentType.PLAT,

            # Releases
            "REL": DocumentType.RELEASE,
            "RELS": DocumentType.RELEASE,
            "RELEASE": DocumentType.RELEASE,
            "RELDOT": DocumentType.RELEASE,
            "RELMORT": DocumentType.RELEASE,
            "SAT": DocumentType.SATISFACTION,
            "SATISFACTION": DocumentType.SATISFACTION,

            # Assignments
            "ASGN": DocumentType.ASSIGNMENT,
            "ASSIGN": DocumentType.ASSIGNMENT,
            "ASSIGNMENT": DocumentType.ASSIGNMENT,
            "AOT": DocumentType.ASSIGNMENT,

            # Subordination
            "SUB": DocumentType.SUBORDINATION,
            "SNDA": DocumentType.SUBORDINATION,
            "SUBORDINATION": DocumentType.SUBORDINATION,

            # Lis Pendens
            "LP": DocumentType.LIS_PENDENS,
            "NLP": DocumentType.LIS_PENDENS,
            "LIS PENDENS": DocumentType.LIS_PENDENS,
            "NOTICE OF LIS PENDENS": DocumentType.LIS_PENDENS,

            # Bankruptcy
            "BK": DocumentType.BANKRUPTCY,
            "BANKRUPTCY": DocumentType.BANKRUPTCY,

            # UCC
            "UCC": DocumentType.UCC_FILING,
            "UCC1": DocumentType.UCC_FILING,
            "UCC-1": DocumentType.UCC_FILING,
            "FINANCING STATEMENT": DocumentType.UCC_FILING,

            # Survey
            "SURVEY": DocumentType.SURVEY,
            "SUR": DocumentType.SURVEY,
            "ILC": DocumentType.SURVEY,
            "ALTA": DocumentType.SURVEY,
        }

        return mappings.get(raw_upper)

    def _classify_from_filename(self, filename: str) -> Optional[DocumentType]:
        """Extract document type hints from filename"""
        filename_lower = filename.lower()

        patterns = [
            (r"deed", DocumentType.DEED),
            (r"mort(?:gage)?", DocumentType.MORTGAGE),
            (r"dot|deed.?of.?trust", DocumentType.DEED_OF_TRUST),
            (r"lien", DocumentType.LIEN),
            (r"judg(?:ment)?", DocumentType.JUDGMENT),
            (r"ease(?:ment)?", DocumentType.EASEMENT),
            (r"plat", DocumentType.PLAT),
            (r"release|rel(?:s)?", DocumentType.RELEASE),
            (r"sat(?:isfaction)?", DocumentType.SATISFACTION),
            (r"assign", DocumentType.ASSIGNMENT),
            (r"sub(?:ordination)?", DocumentType.SUBORDINATION),
            (r"lis.?pendens|lp", DocumentType.LIS_PENDENS),
            (r"survey", DocumentType.SURVEY),
        ]

        for pattern, doc_type in patterns:
            if re.search(pattern, filename_lower):
                return doc_type

        return None


# Create singleton instance
classifier = DocumentClassifier()


def classify_document(
    text: str,
    filename: Optional[str] = None,
    raw_doc_type: Optional[str] = None
) -> Tuple[DocumentType, float, Dict[str, Any]]:
    """Convenience function for document classification"""
    return classifier.classify(text, filename, raw_doc_type)


def classify_from_raw_type(raw_type: str) -> DocumentType:
    """Quick classification from raw document type code"""
    mapped = classifier._map_raw_type(raw_type)
    return mapped if mapped else DocumentType.OTHER
