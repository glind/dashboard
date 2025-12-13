"""
FounderShield FastAPI Endpoints
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

from .service import FounderShieldService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["foundershield"])

# Initialize service
foundershield = FounderShieldService()


class ReportRequest(BaseModel):
    """Request model for email risk report."""
    email: EmailStr
    raw_headers: Optional[str] = None
    raw_body: Optional[str] = None


@router.post("/report")
async def generate_risk_report(request: ReportRequest):
    """
    Generate comprehensive email and domain risk report.
    
    Analyzes:
    - DNS records (MX, SPF, DMARC, MTA-STS, TLSRPT)
    - WHOIS domain age
    - Email authentication (SPF, DKIM, DMARC from headers)
    - Content patterns (scam indicators, suspicious URLs)
    
    Returns risk score (0-100) and detailed findings.
    """
    try:
        report = await foundershield.generate_report(
            email_address=request.email,
            raw_headers=request.raw_headers,
            raw_body=request.raw_body
        )
        return report
    
    except Exception as e:
        logger.error(f"Error generating risk report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "FounderShield",
        "version": "1.0.0"
    }
