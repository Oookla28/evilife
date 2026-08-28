"""Evidence Packet models and deterministic citation verification."""

from ..schemas import EvidenceAnswer, EvidenceCitation, EvidenceItem, EvidencePacket
from .citation_verifier import (
    CitedClaim,
    CitationReference,
    CitationVerificationError,
    CitationVerificationResult,
    CitationVerifier,
    VerificationIssue,
)
from .fast_path import FastPath, FastPathResult
from .deep_path import DeepPath, DeepPathResult
from .modes import EvaluationModeRouter, ModeSelection
from .repository import (
    EvidencePacketNotFoundError,
    EvidencePacketRepository,
    EvidencePacketSchemaError,
    EvidenceRepositoryError,
)
from .safety import EvidenceGate, SafetyAssessment, SafetyCategory, SafetyRouter
from .topic_matcher import UNKNOWN_TOPIC, TopicMatcher

__all__ = [
    "CitedClaim",
    "CitationReference",
    "CitationVerificationError",
    "CitationVerificationResult",
    "CitationVerifier",
    "EvidenceItem",
    "EvidenceAnswer",
    "EvidenceCitation",
    "EvidenceGate",
    "EvidencePacket",
    "EvidencePacketNotFoundError",
    "EvidencePacketRepository",
    "EvidencePacketSchemaError",
    "EvidenceRepositoryError",
    "DeepPath",
    "DeepPathResult",
    "EvaluationModeRouter",
    "FastPath",
    "FastPathResult",
    "ModeSelection",
    "SafetyAssessment",
    "SafetyCategory",
    "SafetyRouter",
    "TopicMatcher",
    "UNKNOWN_TOPIC",
    "VerificationIssue",
]
