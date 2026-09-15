"""Unified observation abstraction + fusion + semantic target resolution.

Multiple evidence sources (Windows UIA, browser DOM/accessibility, screenshot,
application adapter, filesystem) produce candidate elements. ObservationFusion
merges them into a single view with confidence, and TargetResolver turns a
semantic request ("click the Save button") into a resolved target or an explicit
non-resolution (AMBIGUOUS / NOT_FOUND / DISABLED / HIDDEN / STALE). It never
guesses among ambiguous candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas.enums import StrEnum
from .models import DesktopObservation, ElementQuery, UIElement


class ObservationSourceKind(StrEnum):
    UIA = "uia"
    BROWSER_DOM = "browser_dom"
    SCREENSHOT = "screenshot"
    APPLICATION = "application"
    FILESYSTEM = "filesystem"


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    DISABLED = "disabled"
    HIDDEN = "hidden"
    STALE = "stale"


@dataclass
class FusedElement:
    element: UIElement
    sources: set[str] = field(default_factory=set)

    @property
    def confidence(self) -> float:
        # more corroborating sources -> higher confidence (capped)
        base = min(1.0, 0.4 + 0.3 * len(self.sources))
        if not self.element.enabled or not self.element.visible:
            base *= 0.5
        return round(base, 3)


@dataclass
class FusedObservation:
    observation_id: str
    state_hash: str
    active_window: str | None
    elements: list[FusedElement]
    sources: set[str]

    def find(self, query: ElementQuery) -> list[FusedElement]:
        return [
            fe
            for fe in self.elements
            if fe.element.matches(role=query.role, name=query.name,
                                  automation_id=query.automation_id)
        ]


class ObservationFusion:
    """Merge observations from multiple sources into one fused view."""

    def fuse(self, observations: dict[str, DesktopObservation]) -> FusedObservation:
        """``observations`` maps source-kind -> DesktopObservation."""

        by_key: dict[str, FusedElement] = {}
        active = None
        state_hash = ""
        obs_id = "obs_fused"
        all_sources: set[str] = set()

        for source, obs in observations.items():
            all_sources.add(source)
            active = active or obs.active_window
            state_hash = state_hash or obs.state_hash
            obs_id = obs.observation_id
            for el in obs.visible_elements:
                key = f"{el.role}|{el.name}|{el.automation_id}"
                if key in by_key:
                    by_key[key].sources.add(source)
                else:
                    by_key[key] = FusedElement(element=el, sources={source})

        return FusedObservation(
            observation_id=obs_id,
            state_hash=state_hash,
            active_window=active,
            elements=list(by_key.values()),
            sources=all_sources,
        )


@dataclass
class Resolution:
    status: ResolutionStatus
    element: UIElement | None = None
    candidates: int = 0
    confidence: float = 0.0
    detail: str = ""


class TargetResolver:
    """Resolve a semantic query against a fused observation. Never guesses."""

    def resolve(self, query: ElementQuery, fused: FusedObservation) -> Resolution:
        matches = fused.find(query)
        if not matches:
            return Resolution(ResolutionStatus.NOT_FOUND, detail=f"no match for {query.describe()}")
        if len(matches) > 1:
            # if exactly one is enabled+visible, prefer it deterministically
            usable = [m for m in matches if m.element.enabled and m.element.visible]
            if len(usable) == 1:
                m = usable[0]
                return Resolution(ResolutionStatus.RESOLVED, element=m.element,
                                  candidates=len(matches), confidence=m.confidence)
            return Resolution(ResolutionStatus.AMBIGUOUS, candidates=len(matches),
                              detail=f"{len(matches)} matches for {query.describe()}")
        m = matches[0]
        if not m.element.visible:
            return Resolution(ResolutionStatus.HIDDEN, element=m.element, candidates=1)
        if not m.element.enabled:
            return Resolution(ResolutionStatus.DISABLED, element=m.element, candidates=1)
        return Resolution(ResolutionStatus.RESOLVED, element=m.element, candidates=1,
                          confidence=m.confidence)
