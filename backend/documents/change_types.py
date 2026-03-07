from __future__ import annotations

from enum import StrEnum


class ChangeType(StrEnum):
    DEADLINE = "deadline_change"
    DOCUMENT = "document_change"
    OBLIGATION = "obligation_change"
    SERVICE_PROCEDURE = "service_procedure_change"
    REFUSAL = "refusal_change"
    EDITORIAL = "editorial_change"
    STRUCTURAL = "structural_change"
