"""Deterministic educational traceability tabletop templates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TabletopInputs:
    product_category: str
    hazard_category: str
    classification: str | None
    company_profile: str
    facilities: int
    distribution_scope: str
    difficulty: str
    roles: tuple[str, ...]
    ftl_category: str | None = None


@dataclass(frozen=True, slots=True)
class TabletopPacket:
    objective: str
    narrative: str
    injects: tuple[str, ...]
    decision_points: tuple[str, ...]
    records_to_locate: tuple[str, ...]
    communications: tuple[str, ...]
    role_assignments: tuple[str, ...]
    analogs: tuple[dict[str, object], ...]
    debrief: tuple[str, ...]
    assumptions: tuple[str, ...]
    markdown: str


def select_analogs(records: Sequence[Mapping[str, object]], inputs: TabletopInputs, limit: int = 5) -> tuple[dict[str, object], ...]:
    """Select deterministic historical analogs from already trusted filtered rows."""
    selected = [dict(row) for row in records if _matches(row, inputs)]
    return tuple(sorted(selected, key=lambda row: (str(row.get("report_date") or ""), str(row.get("source_record_id") or "")), reverse=True)[:limit])


def build_tabletop(inputs: TabletopInputs, records: Sequence[Mapping[str, object]]) -> TabletopPacket:
    """Build a fixed educational exercise; no compliance decision is made."""
    analogs = select_analogs(records, inputs)
    ftl = f" The user selected the FTL context '{inputs.ftl_category}'." if inputs.ftl_category else " No FTL category was selected."
    objective = f"Practice tracing a fictional {inputs.hazard_category} signal involving {inputs.product_category} across {inputs.facilities} facility or facilities."
    narrative = f"At 09:00, the {inputs.company_profile} team receives a fictional quality escalation involving a {inputs.product_category} lot distributed across a {inputs.distribution_scope} footprint.{ftl}"
    injects = ("09:15 — A lot identifier is incomplete in one receiving record.", "09:45 — A trading partner requests a product and destination list.", "10:30 — A second facility reports potentially related inventory.", "11:15 — Leadership requests a concise traceability status and assumptions log.")
    assumptions = ("This is a fictional preparedness exercise inspired by historical records, not a current incident.", "FTL selection is educational context only; coverage, exemptions, and obligations require independent review.", "The FDA describes a 24-hour records-production context for persons subject to the rule; this exercise does not determine whether it applies.", "Completing this exercise does not establish compliance.")
    analog_lines = tuple(_citation(row) for row in analogs) or ("No matching historical analogs were found for the selected filters.",)
    decisions = ("Decide the tracing lead and information cadence.", "Decide what remains unknown before communicating.")
    records_to_locate = ("Lot/traceability identifiers and receiving/shipping records.", "Supplier, facility, product, quantity, and destination information.")
    communications = ("Internal: operations, quality, legal/comms liaison.", "External: use approved fictional exercise channels only.")
    assignments = tuple(f"{role}: identify decisions and information needs." for role in inputs.roles)
    debrief = ("Which records were available quickly?", "Which assumptions changed the response?", "What would improve the next exercise?")
    markdown = "\n".join(["# RecallReady Traceability Tabletop", "", "## Objective", objective, "", "## Initial narrative", narrative, "", "## Timed injects", *[f"- {item}" for item in injects], "", "## Decision points", *[f"- {item}" for item in decisions], "", "## Records and information to locate", *[f"- {item}" for item in records_to_locate], "", "## Communication checklist", *[f"- {item}" for item in communications], "", "## Role assignments", *[f"- {item}" for item in assignments], "", "## Historical analogs", *[f"- {item}" for item in analog_lines], "", "## Debrief questions", *[f"- {item}" for item in debrief], "", "## Assumptions and limitations", *[f"- {item}" for item in assumptions]]) + "\n"
    return TabletopPacket(objective, narrative, injects, decisions, records_to_locate, communications, assignments, analogs, debrief, assumptions, markdown)


def _matches(row: Mapping[str, object], inputs: TabletopInputs) -> bool:
    category = str(row.get("derived_product_category") or row.get("product_category") or "")
    hazard = str(row.get("primary_hazard") or row.get("hazard") or "")
    classification = str(row.get("classification") or "")
    return category == inputs.product_category and (not inputs.hazard_category or hazard == inputs.hazard_category) and (inputs.classification is None or classification == inputs.classification)


def _citation(row: Mapping[str, object]) -> str:
    return f"Recall {row.get('recall_number') or 'unknown'}; event {row.get('event_id') or 'not reported'}; report date {row.get('report_date') or 'not reported'}."
