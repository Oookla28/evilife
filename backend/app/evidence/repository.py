from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ..schemas import EvidencePacket


class EvidenceRepositoryError(RuntimeError):
    """Base error for deterministic Evidence Packet loading failures."""


class EvidencePacketNotFoundError(EvidenceRepositoryError):
    """Raised when a requested topic has no precompiled packet."""


class EvidencePacketSchemaError(EvidenceRepositoryError):
    """Raised when a packet file is invalid JSON or violates its schema."""


class EvidencePacketRepository:
    """Load, validate, and cache precompiled Evidence Packets by topic."""

    def __init__(self, evidence_dir: Path | None = None) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        self.evidence_dir = evidence_dir or repository_root / "data" / "evidence"
        self._packets_by_topic: dict[str, EvidencePacket] | None = None

    def get(self, topic: str) -> EvidencePacket:
        packets = self._load_all()
        try:
            return packets[topic]
        except KeyError as error:
            available = ", ".join(sorted(packets)) or "none"
            raise EvidencePacketNotFoundError(
                f"Evidence Packet topic not found: {topic}. Available topics: {available}"
            ) from error

    def all(self) -> dict[str, EvidencePacket]:
        """Return a copy of the topic index without exposing the cache itself."""

        return dict(self._load_all())

    def reload(self) -> dict[str, EvidencePacket]:
        self._packets_by_topic = None
        return self.all()

    def _load_all(self) -> dict[str, EvidencePacket]:
        if self._packets_by_topic is not None:
            return self._packets_by_topic

        if not self.evidence_dir.is_dir():
            raise EvidenceRepositoryError(
                f"Evidence Packet directory does not exist: {self.evidence_dir}"
            )

        paths = sorted(self.evidence_dir.glob("*.json"))
        if not paths:
            raise EvidenceRepositoryError(
                f"No Evidence Packet files found in: {self.evidence_dir}"
            )

        packets: dict[str, EvidencePacket] = {}
        for path in paths:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                packet = EvidencePacket.model_validate(raw)
            except (OSError, json.JSONDecodeError, ValidationError) as error:
                raise EvidencePacketSchemaError(
                    f"Invalid Evidence Packet {path}: {error}"
                ) from error

            if packet.topic in packets:
                raise EvidencePacketSchemaError(
                    f"Duplicate Evidence Packet topic {packet.topic!r} in {path}"
                )
            packets[packet.topic] = packet

        self._packets_by_topic = packets
        return packets
