"""Verifier interface. Tool success != business success (PRD §41, §79)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.agents import VerificationRequest, VerificationResult


class Verifier(Protocol):
    async def verify(self, request: VerificationRequest) -> VerificationResult: ...
