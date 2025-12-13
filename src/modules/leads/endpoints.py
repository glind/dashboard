"""
Lead Collection API Endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from collectors.lead_collector import LeadCollector
from collectors.gmail_collector import GmailCollector
from collectors.calendar_collector import CalendarCollector
from collectors.notes_collector import ObsidianNotesCollector
from database import DatabaseManager
from processors.email_risk_learning import EmailRiskLearningSystem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["leads"])

# Initialize collectors and learning system
db = DatabaseManager()
lead_collector = LeadCollector(db=db)
learning_system = EmailRiskLearningSystem(db=db)


class TaskCreateRequest(BaseModel):
    """Request to create a task for a lead."""
    lead_id: str
    task_type: str
    description: str
    priority: str = 'medium'
    due_days: int = 7


class CRMExportRequest(BaseModel):
    """Request to export lead to CRM."""
    lead_id: str
    crm_type: str = 'generic'


@router.post("/collect")
async def collect_leads(
    days_back: int = Query(default=30, ge=1, le=90),
    sources: str = Query(default="email,calendar,notes", description="Comma-separated: email,calendar,notes")
):
    """
    Collect leads from communications sources.
    
    Analyzes recent emails, calendar events, and notes to identify
    potential customers, investors, and partners.
    """
    try:
        source_list = [s.strip() for s in sources.split(',')]
        all_leads = []
        
        # Collect from emails
        if 'email' in source_list:
            try:
                from config.settings import settings as app_settings
                gmail_collector = GmailCollector(app_settings)
                start_date = datetime.now() - timedelta(days=days_back)
                end_date = datetime.now()
                
                emails = await gmail_collector.collect_emails(start_date, end_date)
                email_leads = await lead_collector.collect_from_gmail(emails, days_back)
                
                # Save each lead
                for lead in email_leads:
                    await lead_collector.save_lead(lead)
                    # Create initial task
                    if lead.next_action:
                        await lead_collector.create_task_for_lead(
                            lead.lead_id,
                            'follow_up',
                            lead.next_action,
                            priority='high' if lead.score >= 75 else 'medium'
                        )
                
                all_leads.extend(email_leads)
                logger.info(f"✅ Collected {len(email_leads)} leads from email")
                
            except Exception as e:
                logger.error(f"Error collecting from email: {e}")
        
        # Collect from calendar
        if 'calendar' in source_list:
            try:
                from config.settings import settings as app_settings
                calendar_collector = CalendarCollector(app_settings)
                start_date = datetime.now() - timedelta(days=days_back)
                end_date = datetime.now() + timedelta(days=30)  # Include upcoming meetings
                
                events = await calendar_collector.collect_events(start_date, end_date)
                calendar_leads = await lead_collector.collect_from_calendar(events)
                
                for lead in calendar_leads:
                    await lead_collector.save_lead(lead)
                    await lead_collector.create_task_for_lead(
                        lead.lead_id,
                        'meeting_prep',
                        f"Prepare for meeting: {lead.next_action}"
                    )
                
                all_leads.extend(calendar_leads)
                logger.info(f"✅ Collected {len(calendar_leads)} leads from calendar")
                
            except Exception as e:
                logger.error(f"Error collecting from calendar: {e}")
        
        # Collect from notes
        if 'notes' in source_list:
            try:
                from config.settings import settings as app_settings
                notes_collector = ObsidianNotesCollector(app_settings)
                notes = await notes_collector.collect_notes()
                notes_leads = await lead_collector.collect_from_notes(notes)
                
                for lead in notes_leads:
                    await lead_collector.save_lead(lead)
                    await lead_collector.create_task_for_lead(
                        lead.lead_id,
                        'initial_outreach',
                        f"Follow up on note: {lead.next_action}"
                    )
                
                all_leads.extend(notes_leads)
                logger.info(f"✅ Collected {len(notes_leads)} leads from notes")
                
            except Exception as e:
                logger.error(f"Error collecting from notes: {e}")
        
        # Get statistics
        stats = {
            'total_collected': len(all_leads),
            'by_type': {},
            'by_source': {},
            'by_risk': {}
        }
        
        for lead in all_leads:
            # By type
            stats['by_type'][lead.lead_type] = stats['by_type'].get(lead.lead_type, 0) + 1
            # By source
            stats['by_source'][lead.source] = stats['by_source'].get(lead.source, 0) + 1
            # By risk
            risk = lead.risk_level or 'unknown'
            stats['by_risk'][risk] = stats['by_risk'].get(risk, 0) + 1
        
        return {
            'success': True,
            'leads_collected': len(all_leads),
            'statistics': stats,
            'message': f"Collected {len(all_leads)} leads from {', '.join(source_list)}"
        }
        
    except Exception as e:
        logger.error(f"Error collecting leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_leads(
    lead_type: Optional[str] = Query(default=None, description="Filter by type: customer, investor, partner"),
    status: Optional[str] = Query(default=None, description="Filter by status: new, contacted, qualified"),
    min_score: int = Query(default=0, ge=0, le=100, description="Minimum lead score")
):
    """
    List all collected leads with optional filters.
    """
    try:
        leads = await lead_collector.get_all_leads(
            lead_type=lead_type,
            status=status,
            min_score=min_score
        )
        
        return {
            'success': True,
            'count': len(leads),
            'leads': leads
        }
        
    except Exception as e:
        logger.error(f"Error listing leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{lead_id}")
async def get_lead(lead_id: str):
    """Get details for a specific lead."""
    try:
        with db.get_connection() as conn:
            # Get lead
            lead_row = conn.execute(
                "SELECT * FROM leads WHERE lead_id = ?",
                (lead_id,)
            ).fetchone()
            
            if not lead_row:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            lead = dict(lead_row)
            if lead.get('signals'):
                lead['signals'] = lead['signals'].split(',')
            
            # Get interactions
            interactions = conn.execute(
                "SELECT * FROM lead_interactions WHERE lead_id = ? ORDER BY timestamp DESC",
                (lead_id,)
            ).fetchall()
            
            # Get tasks
            tasks = conn.execute(
                "SELECT * FROM lead_tasks WHERE lead_id = ? ORDER BY created_at DESC",
                (lead_id,)
            ).fetchall()
            
            return {
                'success': True,
                'lead': lead,
                'interactions': [dict(row) for row in interactions],
                'tasks': [dict(row) for row in tasks]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/task")
async def create_task(lead_id: str, request: TaskCreateRequest):
    """Create a new task for a lead."""
    try:
        task_id = await lead_collector.create_task_for_lead(
            lead_id=request.lead_id,
            task_type=request.task_type,
            description=request.description,
            priority=request.priority,
            due_days=request.due_days
        )
        
        if not task_id:
            raise HTTPException(status_code=500, detail="Failed to create task")
        
        return {
            'success': True,
            'task_id': task_id,
            'message': 'Task created successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/status")
async def update_lead_status(lead_id: str, status: str):
    """Update lead status."""
    try:
        valid_statuses = ['new', 'contacted', 'qualified', 'converted', 'closed']
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?",
                (status, lead_id)
            )
            conn.commit()
        
        return {
            'success': True,
            'message': f'Lead status updated to {status}'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating lead status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_to_crm(request: CRMExportRequest):
    """
    Export lead to CRM format.
    
    Supports: generic, hubspot, salesforce, pipedrive
    """
    try:
        result = await lead_collector.export_to_crm(
            lead_id=request.lead_id,
            crm_type=request.crm_type
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Export failed'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting to CRM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/confirm")
async def confirm_lead(lead_id: str):
    """Confirm a potential lead (move from potential to active)."""
    try:
        with db.get_connection() as conn:
            # Check if lead exists
            lead_row = conn.execute(
                "SELECT * FROM leads WHERE lead_id = ?",
                (lead_id,)
            ).fetchone()
            
            if not lead_row:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            # Update status to confirmed
            conn.execute(
                "UPDATE leads SET status = 'new', updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?",
                (lead_id,)
            )
            conn.commit()
        
        return {
            'success': True,
            'message': 'Lead confirmed successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, reason: str = Query(default="not_relevant")):
    """Delete a potential lead and learn from it."""
    try:
        with db.get_connection() as conn:
            # Get lead details
            lead_row = conn.execute(
                "SELECT * FROM leads WHERE lead_id = ?",
                (lead_id,)
            ).fetchone()
            
            if not lead_row:
                raise HTTPException(status_code=404, detail="Lead not found")
            
            lead = dict(lead_row)
            
            # Record deletion for learning
            learning_system.record_deleted_lead(
                contact_email=lead['contact_email'],
                contact_name=lead['contact_name'],
                company=lead['company'],
                reason=reason,
                signals=lead['signals'].split(',') if lead.get('signals') else [],
                lead_type=lead['lead_type'],
                score=lead['score']
            )
            
            # Delete the lead
            conn.execute("DELETE FROM leads WHERE lead_id = ?", (lead_id,))
            conn.execute("DELETE FROM lead_tasks WHERE lead_id = ?", (lead_id,))
            conn.execute("DELETE FROM lead_interactions WHERE lead_id = ?", (lead_id,))
            conn.commit()
        
        return {
            'success': True,
            'message': f'Lead deleted and reason recorded: {reason}'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/email-risk")
async def submit_email_risk_feedback(
    email_id: str,
    sender_email: str,
    original_score: int,
    original_level: str,
    user_assessment: str,
    reason: Optional[str] = None,
    signals: Optional[str] = None
):
    """Submit feedback on email risk assessment to improve future scoring."""
    try:
        signal_list = signals.split(',') if signals else []
        
        success = learning_system.record_user_feedback(
            email_id=email_id,
            sender_email=sender_email,
            original_score=original_score,
            original_level=original_level,
            user_assessment=user_assessment,
            reason=reason,
            signals=signal_list
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to record feedback")
        
        return {
            'success': True,
            'message': 'Feedback recorded. System will learn from this.'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/stats")
async def get_learning_stats():
    """Get statistics on the learning system's performance."""
    try:
        stats = learning_system.get_feedback_stats()
        return {
            'success': True,
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Error getting learning stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_lead_stats():
    """Get lead collection statistics."""
    try:
        with db.get_connection() as conn:
            # Total leads
            total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            
            # By type
            by_type = conn.execute("""
                SELECT lead_type, COUNT(*) as count
                FROM leads
                GROUP BY lead_type
            """).fetchall()
            
            # By status
            by_status = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM leads
                GROUP BY status
            """).fetchall()
            
            # By source
            by_source = conn.execute("""
                SELECT source, COUNT(*) as count
                FROM leads
                GROUP BY source
            """).fetchall()
            
            # High-priority leads (score >= 75)
            high_priority = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE score >= 75"
            ).fetchone()[0]
            
            # Recent leads (last 7 days)
            recent = conn.execute("""
                SELECT COUNT(*) FROM leads
                WHERE last_contact >= datetime('now', '-7 days')
            """).fetchone()[0]
            
            return {
                'success': True,
                'total_leads': total,
                'high_priority_leads': high_priority,
                'recent_leads_7d': recent,
                'by_type': {row[0]: row[1] for row in by_type},
                'by_status': {row[0]: row[1] for row in by_status},
                'by_source': {row[0]: row[1] for row in by_source}
            }
            
    except Exception as e:
        logger.error(f"Error getting lead stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
