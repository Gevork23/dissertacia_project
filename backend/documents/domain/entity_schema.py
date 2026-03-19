from __future__ import annotations

from enum import StrEnum


class EntityType(StrEnum):
    SERVICE = "service"
    REQUIRED_DOCUMENT = "required_document"
    DEADLINE = "deadline"
    OBLIGATION = "obligation"
    CONDITION = "condition"
    REFUSAL_REASON = "refusal_reason"
    APPLICANT_CATEGORY = "applicant_category"
    AUTHORITY_UNIT = "authority_unit"


class ExtractionMethod(StrEnum):
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    LLM = "llm"


class DeadlineUnit(StrEnum):
    CALENDAR_DAYS = "calendar_days"
    WORKING_DAYS = "working_days"
    HOURS = "hours"
    MINUTES = "minutes"
    SAME_DAY = "same_day"
    UNSPECIFIED = "unspecified"


class DeadlineModifier(StrEnum):
    EXACT = "exact"
    UP_TO = "up_to"
    AT_LEAST = "at_least"


class DeadlineScope(StrEnum):
    SERVICE_PROVISION = "service_provision"
    DOCUMENT_REVIEW = "document_review"
    INTERAGENCY_REQUEST = "interagency_request"
    INFORMING = "informing"
    RESULT_ISSUE = "result_issue"
    UNSPECIFIED = "unspecified"


class ObligationActor(StrEnum):
    EMPLOYEE = "employee"
    AUTHORITY_UNIT = "authority_unit"
    APPLICANT = "applicant"
    REPRESENTATIVE = "representative"
    UNSPECIFIED = "unspecified"


class ObligationPhase(StrEnum):
    BEFORE_REGISTRATION = "before_registration"
    AFTER_REGISTRATION = "after_registration"
    DURING_REVIEW = "during_review"
    DURING_CONSULTATION = "during_consultation"
    RESULT_DELIVERY = "result_delivery"
    UNSPECIFIED = "unspecified"


class ConditionKind(StrEnum):
    REPRESENTATIVE_CASE = "representative_case"
    INTERAGENCY_REQUEST = "interagency_request"
    EXCEPTION_CASE = "exception_case"
    ELIGIBILITY_CASE = "eligibility_case"
    DOCUMENT_DEFICIENCY_CASE = "document_deficiency_case"
    UNSPECIFIED = "unspecified"


class ConditionScope(StrEnum):
    REQUIRED_DOCUMENTS = "required_documents"
    DEADLINE = "deadline"
    OBLIGATION = "obligation"
    REFUSAL = "refusal"
    PROCEDURE = "procedure"
    UNSPECIFIED = "unspecified"


class RefusalCategory(StrEnum):
    INCOMPLETE_DOCUMENTS = "incomplete_documents"
    FALSE_INFORMATION = "false_information"
    NO_ELIGIBILITY = "no_eligibility"
    AUTHORITY_OF_REPRESENTATIVE = "authority_of_representative"
    PROCEDURAL_VIOLATION = "procedural_violation"
    UNSPECIFIED = "unspecified"


class ApplicantKind(StrEnum):
    APPLICANT = "applicant"
    REPRESENTATIVE = "representative"
    CITIZEN = "citizen"
    LEGAL_REPRESENTATIVE = "legal_representative"
    UNSPECIFIED = "unspecified"


class AuthorityKind(StrEnum):
    MFC = "mfc"
    EMPLOYEE_UNIT = "employee_unit"
    GOVERNMENT_AUTHORITY = "government_authority"
    STRUCTURAL_UNIT = "structural_unit"
    UNSPECIFIED = "unspecified"


class DocumentRole(StrEnum):
    MANDATORY = "mandatory"
    ADDITIONAL = "additional"
    OPTIONAL = "optional"


class DocumentActor(StrEnum):
    APPLICANT = "applicant"
    REPRESENTATIVE = "representative"
    ALL = "all"
