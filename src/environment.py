from typing import TypedDict
from src.validate import ValidationResult

class GenerateFhirEnvironment(TypedDict):
    resource_json: dict  # The FHIR resource as a JSON dictionary
    id: str  # Unique identifier for this environment
    last_validation: ValidationResult | None  # Result from last validation call

def valid(validation_result: ValidationResult) -> bool:
    return validation_result.valid

