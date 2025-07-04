"""
Reporting API endpoints for the patient interaction logging system
Provides endpoints for configuring reports, viewing statistics, and managing the reporting system
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.patient_interaction_logger import patient_logger

router = APIRouter(prefix="/api", tags=["reporting"])

class ReportingConfigRequest(BaseModel):
    """Request model for updating reporting configuration"""
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    recipients: Optional[List[str]] = None
    daily_email_time: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    include_patient_details: Optional[bool] = None
    backup_email: Optional[str] = None

class ManualReportRequest(BaseModel):
    """Request model for generating manual reports"""
    target_date: Optional[str] = None  # YYYY-MM-DD format
    send_email: Optional[bool] = False

@router.post("/configure_reporting")
async def configure_reporting(request: ReportingConfigRequest):
    """Update reporting system configuration"""
    try:
        config_updates = {}
        
        # Update email configuration
        if any([request.email_username, request.email_password, request.recipients, 
                request.smtp_server, request.smtp_port]):
            config_updates["email"] = {}
            if request.email_username:
                config_updates["email"]["username"] = request.email_username
            if request.email_password:
                config_updates["email"]["password"] = request.email_password
            if request.recipients:
                config_updates["email"]["recipients"] = request.recipients
            if request.smtp_server:
                config_updates["email"]["smtp_server"] = request.smtp_server
            if request.smtp_port:
                config_updates["email"]["smtp_port"] = request.smtp_port
        
        # Update reporting configuration
        if any([request.daily_email_time, request.include_patient_details is not None]):
            config_updates["reporting"] = {}
            if request.daily_email_time:
                config_updates["reporting"]["daily_email_time"] = request.daily_email_time
            if request.include_patient_details is not None:
                config_updates["reporting"]["include_patient_details"] = request.include_patient_details
        
        # Update fallback configuration
        if request.backup_email:
            config_updates["fallback"] = {"backup_email": request.backup_email}
        
        # Apply configuration updates
        patient_logger.update_config(config_updates)
        
        return {
            "success": True,
            "message": "Reporting configuration updated successfully",
            "updated_fields": list(config_updates.keys())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {str(e)}")

@router.get("/reporting_config")
async def get_reporting_config():
    """Get current reporting system configuration (sensitive data masked)"""
    try:
        config = patient_logger.config.copy()
        
        # Mask sensitive information
        if "email" in config and "password" in config["email"]:
            config["email"]["password"] = "***MASKED***"
        
        return {
            "success": True,
            "config": config
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving configuration: {str(e)}")

@router.post("/generate_report")
async def generate_manual_report(request: ManualReportRequest):
    """Generate a manual daily report"""
    try:
        # Parse target date
        target_date = None
        if request.target_date:
            try:
                target_date = datetime.strptime(request.target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            target_date = date.today()
        
        # Generate HTML report
        html_report = patient_logger.generate_daily_report(target_date)
        
        # Optionally send email
        if request.send_email:
            try:
                patient_logger._send_email_report(html_report, target_date)
                email_status = "Email sent successfully"
            except Exception as e:
                email_status = f"Email failed: {str(e)}"
        else:
            email_status = "Email not requested"
        
        # Save report to file
        report_filename = f"manual_report_{target_date.strftime('%Y_%m_%d')}_{datetime.now().strftime('%H%M%S')}.html"
        report_path = patient_logger.log_directory / report_filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        return {
            "success": True,
            "message": f"Report generated for {target_date.strftime('%Y-%m-%d')}",
            "report_date": target_date.strftime('%Y-%m-%d'),
            "report_file": str(report_path),
            "email_status": email_status,
            "report_size": len(html_report)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

@router.get("/interaction_statistics")
async def get_interaction_statistics(days: Optional[int] = 7):
    """Get interaction statistics for the specified number of days"""
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        summary = patient_logger.get_interaction_summary(days)
        return {
            "success": True,
            "statistics": summary
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")

@router.get("/daily_interactions/{target_date}")
async def get_daily_interactions(target_date: str):
    """Get all interactions for a specific date"""
    try:
        # Parse date
        try:
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        interactions = patient_logger.get_daily_interactions(parsed_date)
        
        return {
            "success": True,
            "date": target_date,
            "interaction_count": len(interactions),
            "interactions": interactions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving daily interactions: {str(e)}")

@router.get("/interaction_summary")
async def get_today_summary():
    """Get a quick summary of today's interactions"""
    try:
        today_interactions = patient_logger.get_daily_interactions(date.today())
        stats = patient_logger._calculate_statistics(today_interactions)
        
        return {
            "success": True,
            "date": date.today().strftime('%Y-%m-%d'),
            "summary": {
                "total_interactions": stats['total_calls'],
                "successful_interactions": stats['successful_calls'],
                "failed_interactions": stats['failed_calls'],
                "success_rate": stats['success_rate'],
                "interaction_types": stats['type_counts'],
                "peak_hour": stats.get('peak_hour'),
                "peak_hour_count": stats.get('peak_hour_count', 0)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving today's summary: {str(e)}")

@router.post("/test_email")
async def test_email_configuration():
    """Test the email configuration by sending a test email"""
    try:
        if not patient_logger.config["email"]["recipients"]:
            raise HTTPException(status_code=400, detail="No email recipients configured")
        
        if not patient_logger.config["email"]["username"]:
            raise HTTPException(status_code=400, detail="No email username configured")
        
        # Create a simple test report
        test_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Email</title>
</head>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <h2 style="color: #667eea;">🦷 BrightSmile Dental AI Assistant</h2>
    <h3>Email Configuration Test</h3>
    <p>This is a test email to verify that the reporting system email configuration is working correctly.</p>
    <p><strong>Test sent at:</strong> {timestamp}</p>
    <p>If you received this email, your configuration is working properly!</p>
</body>
</html>
        """.format(timestamp=datetime.now().strftime("%B %d, %Y at %I:%M %p"))
        
        # Send test email
        patient_logger._send_email_report(test_html, date.today())
        
        return {
            "success": True,
            "message": "Test email sent successfully",
            "recipients": patient_logger.config["email"]["recipients"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending test email: {str(e)}")

@router.get("/log_files")
async def list_log_files():
    """List all available log files"""
    try:
        log_files = []
        for file_path in patient_logger.log_directory.glob("*.json"):
            if file_path.name.startswith("interactions_"):
                # Extract date from filename
                date_part = file_path.name.replace("interactions_", "").replace(".json", "")
                try:
                    file_date = datetime.strptime(date_part, "%Y_%m_%d").date()
                    file_size = file_path.stat().st_size
                    
                    # Count interactions in file
                    interactions = patient_logger.get_daily_interactions(file_date)
                    
                    log_files.append({
                        "filename": file_path.name,
                        "date": file_date.strftime("%Y-%m-%d"),
                        "size_bytes": file_size,
                        "interaction_count": len(interactions)
                    })
                except ValueError:
                    continue
        
        # Sort by date (newest first)
        log_files.sort(key=lambda x: x["date"], reverse=True)
        
        return {
            "success": True,
            "log_files": log_files,
            "total_files": len(log_files)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing log files: {str(e)}")
