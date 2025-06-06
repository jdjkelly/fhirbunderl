import json
import requests
from typing import Dict, Any, Union, List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ValidationResult:
    """Result of FHIR resource validation from server"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    information: List[str]
    resource_type: str = None
    timestamp: str = None
    operation_outcome: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

def validate_fhir_resource(
    resource_json: Union[str, Dict[str, Any]], 
    fhir_server_url: str,
    resource_type: Optional[str] = None,
    profile_url: Optional[str] = None,
    timeout: int = 30
) -> ValidationResult:
    """
    Validate a FHIR resource by making a REST call to a FHIR server's validation endpoint.
    
    Args:
        resource_json: FHIR resource as JSON string or dictionary
        fhir_server_url: Base URL of the FHIR server (e.g., "https://hapi.fhir.org/baseR4")
        resource_type: Optional resource type for validation endpoint (e.g., "Patient")
        profile_url: Optional profile URL to validate against
        timeout: Request timeout in seconds (default: 30)
        
    Returns:
        ValidationResult: Object containing validation status, errors, and warnings
    """
    errors = []
    warnings = []
    information = []
    detected_resource_type = None
    operation_outcome = None
    
    try:
        # Parse JSON if string input
        if isinstance(resource_json, str):
            try:
                resource_dict = json.loads(resource_json)
            except json.JSONDecodeError as e:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Invalid JSON format: {str(e)}"],
                    warnings=[],
                    information=[]
                )
        else:
            resource_dict = resource_json
        
        # Extract resource type from the resource
        if isinstance(resource_dict, dict) and 'resourceType' in resource_dict:
            detected_resource_type = resource_dict['resourceType']
        
        # Prepare validation endpoint URL
        fhir_base_url = fhir_server_url.rstrip('/')
        
        # Build validation URL - can be specific to resource type or general
        if resource_type:
            validation_url = f"{fhir_base_url}/{resource_type}/$validate"
        elif detected_resource_type:
            validation_url = f"{fhir_base_url}/{detected_resource_type}/$validate"
        else:
            validation_url = f"{fhir_base_url}/$validate"
        
        # Prepare request headers
        headers = {
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json'
        }
        
        # Add profile parameter if specified
        params = {}
        if profile_url:
            params['profile'] = profile_url
        
        # Make the validation request
        response = requests.post(
            validation_url,
            json=resource_dict,
            headers=headers,
            params=params,
            timeout=timeout
        )
        
        # Parse the response
        if response.status_code == 200:
            # Successful validation - parse OperationOutcome
            try:
                operation_outcome = response.json()
                is_valid, parsed_errors, parsed_warnings, parsed_info = _parse_operation_outcome(operation_outcome)
                errors.extend(parsed_errors)
                warnings.extend(parsed_warnings)
                information.extend(parsed_info)
                
            except json.JSONDecodeError:
                errors.append("Server returned invalid JSON response")
                
        elif response.status_code == 400:
            # Bad request - usually means validation failed
            try:
                operation_outcome = response.json()
                is_valid, parsed_errors, parsed_warnings, parsed_info = _parse_operation_outcome(operation_outcome)
                errors.extend(parsed_errors)
                warnings.extend(parsed_warnings)
                information.extend(parsed_info)
            except json.JSONDecodeError:
                errors.append(f"Validation failed with status {response.status_code}: {response.text}")
                
        elif response.status_code == 404:
            errors.append("FHIR server validation endpoint not found - check server URL and resource type")
            
        elif response.status_code == 422:
            # Unprocessable Entity - validation errors
            try:
                operation_outcome = response.json()
                is_valid, parsed_errors, parsed_warnings, parsed_info = _parse_operation_outcome(operation_outcome)
                errors.extend(parsed_errors)
                warnings.extend(parsed_warnings)
                information.extend(parsed_info)
            except json.JSONDecodeError:
                errors.append(f"Validation failed with status {response.status_code}: {response.text}")
                
        else:
            errors.append(f"FHIR server returned status {response.status_code}: {response.text}")
            
    except requests.exceptions.Timeout:
        errors.append(f"Request to FHIR server timed out after {timeout} seconds")
        
    except requests.exceptions.ConnectionError:
        errors.append("Could not connect to FHIR server - check URL and network connectivity")
        
    except requests.exceptions.RequestException as e:
        errors.append(f"Request to FHIR server failed: {str(e)}")
        
    except Exception as e:
        errors.append(f"Unexpected error during validation: {str(e)}")
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        information=information,
        resource_type=detected_resource_type,
        operation_outcome=operation_outcome
    )

def _parse_operation_outcome(operation_outcome: Dict[str, Any]) -> tuple[bool, List[str], List[str], List[str]]:
    """
    Parse FHIR OperationOutcome resource to extract validation results.
    
    Returns:
        Tuple of (is_valid, errors, warnings, information)
    """
    errors = []
    warnings = []
    information = []
    is_valid = True
    
    if not isinstance(operation_outcome, dict):
        errors.append("Invalid OperationOutcome format")
        return False, errors, warnings, information
    
    # Check if it's actually an OperationOutcome resource
    if operation_outcome.get('resourceType') != 'OperationOutcome':
        errors.append("Expected OperationOutcome resource from validation endpoint")
        return False, errors, warnings, information
    
    # Parse issues from OperationOutcome
    issues = operation_outcome.get('issue', [])
    
    for issue in issues:
        if not isinstance(issue, dict):
            continue
            
        severity = issue.get('severity', 'error')
        code = issue.get('code', 'unknown')
        details = issue.get('details', {})
        diagnostics = issue.get('diagnostics', '')
        location = issue.get('location', [])
        
        # Build error message
        message_parts = []
        
        if details and isinstance(details, dict):
            detail_text = details.get('text', '')
            if detail_text:
                message_parts.append(detail_text)
        
        if diagnostics:
            message_parts.append(diagnostics)
            
        if location:
            location_str = ', '.join(location)
            message_parts.append(f"Location: {location_str}")
        
        if not message_parts:
            message_parts.append(f"Validation issue ({code})")
            
        message = ' - '.join(message_parts)
        
        # Categorize by severity
        if severity in ['fatal', 'error']:
            errors.append(f"Error: {message}")
            is_valid = False
        elif severity == 'warning':
            warnings.append(f"Warning: {message}")
        elif severity == 'information':
            information.append(f"Info: {message}")
    
    # If no issues but we have an OperationOutcome, it might be successful
    if not issues and operation_outcome.get('resourceType') == 'OperationOutcome':
        information.append("Validation completed successfully")
    
    return is_valid, errors, warnings, information