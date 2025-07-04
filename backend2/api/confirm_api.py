import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.patient_interaction_logger import patient_logger

KOLLA_BASE_URL = "https://unify.kolla.dev/dental/v1"
KOLLA_HEADERS = {
    'connector-id': 'opendental',
    'consumer-id': 'kolla-opendental-sandbox',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Authorization': 'Bearer kc.hd4iscieh5emlk75rsjuowweya'
}

router = APIRouter(prefix="/api", tags=["confirm"])

class ConfirmRequest(BaseModel):
    appointment_id: str
    name: Optional[str] = None
    dob: Optional[str] = None  # Date of birth
    confirmed: bool = True
    confirmation_type: Optional[str] = "confirmationTypes/0"  # Fixed: valid confirmation type
    notes: Optional[str] = None

@router.post("/confirm_appointment")
async def confirm_appointment_endpoint(request: ConfirmRequest):
    """Confirm an appointment using Kolla API with proper format."""
    try:
        url = f"{KOLLA_BASE_URL}/appointments/{request.appointment_id}:confirm"
        
        # Prepare the payload in the format expected by Kolla API
        payload = {
            "confirmed": request.confirmed,
            "additional_data": {
                "confirmation_type": request.confirmation_type
            }
        }
        
        # Add notes if provided
        if request.notes:
            payload["notes"] = request.notes
            
        # Add name if provided
        if request.name:
            payload["name"] = request.name
            
        # Print DOB if provided (as requested)
        if request.dob:
            print(f"Confirming appointment for patient DOB: {request.dob}")
            
        response = requests.post(url, headers=KOLLA_HEADERS, json=payload)
        
        if response.status_code in (200, 204):
            # Log successful confirmation interaction - let the logger fetch patient details
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=True,
                appointment_id=request.appointment_id,
                details={
                    "confirmed": request.confirmed,
                    "confirmation_type": request.confirmation_type,
                    "notes": request.notes,
                    "patient_dob": request.dob
                }
            )
            
            return {
                "success": True,
                "message": f"Appointment {request.appointment_id} confirmed successfully.",
                "appointment_id": request.appointment_id,
                "patient_name": request.name,
                "patient_dob": request.dob,
                "confirmed": request.confirmed,
                "confirmation_type": request.confirmation_type,
                "notes": request.notes,
                "status": "confirmed"
            }
        else:
            # Log failed confirmation interaction - let the logger fetch patient details
            patient_logger.log_interaction(
                interaction_type="confirmation",
                success=False,
                appointment_id=request.appointment_id,
                error_message=f"Kolla API error: {response.text}",
                details={
                    "confirmed": request.confirmed,
                    "confirmation_type": request.confirmation_type,
                    "notes": request.notes,
                    "patient_dob": request.dob,
                    "status_code": response.status_code
                }
            )
            
            return {
                "success": False,
                "message": f"Failed to confirm appointment: {response.text}",
                "status_code": response.status_code,
                "appointment_id": request.appointment_id,
                "status": "failed"
            }
    except Exception as e:
        # Log failed confirmation interaction due to exception - let the logger fetch patient details
        patient_logger.log_interaction(
            interaction_type="confirmation",
            success=False,
            appointment_id=request.appointment_id,
            error_message=str(e),
            details={
                "confirmed": request.confirmed,
                "confirmation_type": request.confirmation_type,
                "notes": request.notes,
                "patient_dob": request.dob,
                "error_type": "exception"
            }
        )
        
        raise HTTPException(status_code=500, detail=f"Error confirming appointment: {str(e)}")
