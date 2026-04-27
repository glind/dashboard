"""
Trust Layer REST API Endpoints
"""

import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..models import VerificationContext
from ..report_generator import ReportGenerator
from ..plugin_registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/trust", tags=["trust_layer"])

# Database dependency - will be set from main.py
_db_conn = None

def get_db():
    """Get database connection."""
    if _db_conn is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return _db_conn

def set_db_connection(conn):
    """Set database connection (called from main.py)."""
    global _db_conn
    _db_conn = conn


# Pydantic models for API
class GenerateReportRequest(BaseModel):
    """Request to generate trust report."""
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    sender_email: str
    sender_domain: Optional[str] = None
    sender_name: Optional[str] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    snippet: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)


class TrustReportResponse(BaseModel):
    """Trust report response."""
    report_id: str
    thread_id: Optional[str]
    sender_email: str
    sender_domain: str
    score: int
    risk_level: str
    summary: str
    findings: List[Dict[str, Any]]
    generated_at: str


class TrustStatsResponse(BaseModel):
    """Trust statistics response."""
    total_reports: int
    average_score: float
    risk_distribution: Dict[str, int]
    high_risk_percentage: float


class PluginInfo(BaseModel):
    """Plugin information."""
    name: str
    description: str
    enabled: bool


@router.get("/reports/{thread_id}", response_model=TrustReportResponse)
async def get_report(thread_id: str, db=Depends(get_db)):
    """
    Get trust report for an email thread.
    If report doesn't exist and email is in database, generates new report.
    """
    generator = ReportGenerator(db)
    
    # Try to get existing report
    try:
        report = generator.get_report(thread_id)
    except Exception as e:
        logger.warning(f"Trust report lookup failed for thread {thread_id}: {e}")
        report = None
    
    if not report:
        # Try to get email from database and generate report
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(emails)")
            email_columns = {row[1] for row in cursor.fetchall()}

            thread_col = 'thread_id' if 'thread_id' in email_columns else 'id'

            select_fields = {
                'thread_id': 'thread_id' if 'thread_id' in email_columns else 'id',
                'message_id': 'message_id' if 'message_id' in email_columns else 'id',
                'sender': 'sender' if 'sender' in email_columns else "''",
                'sender_name': 'sender_name' if 'sender_name' in email_columns else "''",
                'subject': 'subject' if 'subject' in email_columns else "''",
                'body_text': (
                    'body_text' if 'body_text' in email_columns
                    else ('body' if 'body' in email_columns else "''")
                ),
                'body_html': 'body_html' if 'body_html' in email_columns else "''",
                'snippet': (
                    'snippet' if 'snippet' in email_columns
                    else ("substr(body, 1, 240)" if 'body' in email_columns else "''")
                ),
                'headers': 'headers' if 'headers' in email_columns else "''",
                'received_date': (
                    'received_date' if 'received_date' in email_columns
                    else ('created_at' if 'created_at' in email_columns else "''")
                ),
            }

            select_sql = ', '.join([f"{expr} AS {alias}" for alias, expr in select_fields.items()])
            query = f"""
                SELECT {select_sql}
                FROM emails
                WHERE {thread_col} = ?
                LIMIT 1
            """
            cursor.execute(query, (thread_id,))
            
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Email not found")
            
            # Generate report
            raw_headers = row['headers'] if 'headers' in row.keys() else ''
            parsed_headers = {}
            if raw_headers:
                try:
                    parsed_headers = json.loads(raw_headers)
                except Exception:
                    try:
                        parsed_headers = eval(raw_headers)
                    except Exception:
                        parsed_headers = {}

            email_dict = {
                'thread_id': row['thread_id'] or thread_id,
                'message_id': row['message_id'] or thread_id,
                'sender': row['sender'] or '',
                'sender_name': row['sender_name'] or '',
                'subject': row['subject'] or '',
                'body_text': row['body_text'] or '',
                'body_html': row['body_html'] or '',
                'snippet': row['snippet'] or '',
                'headers': parsed_headers,
                'received_date': row['received_date'] or ''
            }
            
            try:
                report = await generator.generate_report_from_email(email_dict)
            except Exception as e:
                logger.warning(f"Trust report generation failed for thread {thread_id}: {e}")
                raise HTTPException(status_code=404, detail="Trust report unavailable for this email")
    
    return TrustReportResponse(
        report_id=report.report_id,
        thread_id=report.context.thread_id,
        sender_email=report.context.sender_email,
        sender_domain=report.context.sender_domain,
        score=report.score,
        risk_level=report.risk_level.value,
        summary=report.summary,
        findings=[f.to_dict() for f in report.findings],
        generated_at=report.generated_at.isoformat()
    )


@router.post("/reports", response_model=TrustReportResponse)
async def create_report(request: GenerateReportRequest, db=Depends(get_db)):
    """
    Generate trust report for an email.
    """
    # Create verification context
    context = VerificationContext(
        thread_id=request.thread_id or '',
        message_id=request.message_id or '',
        sender_email=request.sender_email,
        sender_domain=request.sender_domain or request.sender_email.split('@')[-1],
        subject=request.subject,
        body_text=request.body_text,
        body_html=request.body_html or '',
        snippet=request.snippet or request.body_text[:200],
        raw_headers=request.headers
    )
    
    # Generate report
    generator = ReportGenerator(db)
    report = await generator.generate_report(context)
    
    return TrustReportResponse(
        report_id=report.report_id,
        thread_id=report.context.thread_id,
        sender_email=report.context.sender_email,
        sender_domain=report.context.sender_domain,
        score=report.score,
        risk_level=report.risk_level.value,
        summary=report.summary,
        findings=[f.to_dict() for f in report.findings],
        generated_at=report.generated_at.isoformat()
    )


@router.get("/reports", response_model=List[Dict[str, Any]])
async def list_reports(
    limit: int = 100,
    risk_level: Optional[str] = None,
    db=Depends(get_db)
):
    """
    List trust reports with optional filtering.
    """
    generator = ReportGenerator(db)
    reports = generator.list_reports(limit=limit, risk_level=risk_level)
    return reports


@router.get("/stats", response_model=TrustStatsResponse)
async def get_stats(db=Depends(get_db)):
    """
    Get trust layer statistics.
    """
    generator = ReportGenerator(db)
    stats = generator.get_stats()
    return TrustStatsResponse(**stats)


@router.get("/plugins", response_model=List[PluginInfo])
async def list_plugins():
    """
    List available verifier plugins.
    """
    registry = get_registry()
    plugins = registry.list_plugins()
    return [PluginInfo(**plugin) for plugin in plugins]


@router.get("/scoring/rules")
async def get_scoring_rules():
    """
    Get scoring rules configuration.
    """
    from ..scoring_engine import ScoringEngine
    engine = ScoringEngine()
    
    return {
        'ruleset_version': engine.ruleset_version,
        'start_score': 100,
        'rules': {
            rule_id: {
                'points_delta': rule.points_delta,
                'description': rule.description,
                'severity': rule.severity.value
            }
            for rule_id, rule in engine.rules.items()
        },
        'risk_levels': {
            'likely_ok': '80-100 points',
            'caution': '55-79 points',
            'high_risk': '0-54 points'
        }
    }
