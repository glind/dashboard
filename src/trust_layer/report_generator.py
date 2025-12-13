"""
Report Generator - Orchestrates plugin execution and creates trust reports.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from .models import VerificationContext, TrustReport, TrustClaim, Finding
from .plugin_registry import get_registry
from .scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Orchestrates trust verification by:
    1. Running all enabled verifier plugins
    2. Collecting signals and findings
    3. Calculating trust score
    4. Saving report to database
    """
    
    def __init__(self, db_manager):
        """Initialize report generator with database manager."""
        self.db_manager = db_manager
        self.registry = get_registry()
        self.scoring_engine = ScoringEngine()
    
    async def generate_report(self, context: VerificationContext) -> TrustReport:
        """
        Generate complete trust report for an email.
        
        Args:
            context: Verification context with email data
            
        Returns:
            Complete TrustReport with score and findings
        """
        logger.info(f"Generating trust report for {context.sender_email}")
        
        # Gather signals from all plugins  
        signals_by_plugin = await self.registry.gather_all_signals(context)
        
        # Flatten claims from all plugins
        all_claims = []
        for plugin_name, claims in signals_by_plugin.items():
            all_claims.extend(claims)
        logger.info(f"Gathered {len(all_claims)} claims from {len(self.registry.get_enabled())} plugins")
        
        # Gather findings for scoring
        findings_by_plugin = await self.registry.gather_all_findings(context)
        
        # Flatten findings from all plugins
        all_findings = []
        for plugin_name, findings in findings_by_plugin.items():
            all_findings.extend(findings)
        logger.info(f"Gathered {len(all_findings)} findings")
        
        # Calculate score and create report
        report = self.scoring_engine.create_report(
            thread_id=context.thread_id,
            primary_message_id=context.message_id,
            findings=all_findings,
            claims=all_claims,
            signals={claim.claim_type: claim.to_dict() for claim in all_claims}
        )
        
        # Save to database
        self._save_report(report, all_claims, context)
        
        logger.info(f"Report generated: score={report.score}, risk={report.risk_level.value}")
        return report
    
    async def generate_report_from_email(self, email_dict: Dict[str, Any]) -> TrustReport:
        """
        Convenience method to generate report from email dictionary.
        
        Args:
            email_dict: Email data from database (includes thread_id, subject, sender, etc.)
            
        Returns:
            Complete TrustReport
        """
        # Extract domain from email
        sender_email = email_dict.get('sender', '')
        sender_domain = sender_email.split('@')[-1] if '@' in sender_email else ''
        
        # Create context
        context = VerificationContext(
            thread_id=email_dict.get('thread_id', ''),
            message_id=email_dict.get('message_id', ''),
            sender_email=sender_email,
            sender_domain=sender_domain,
            subject=email_dict.get('subject', ''),
            body_text=email_dict.get('body_text', ''),
            body_html=email_dict.get('body_html', ''),
            snippet=email_dict.get('snippet', ''),
            raw_headers=email_dict.get('headers', {})
        )
        
        return await self.generate_report(context)
    
    def get_report(self, thread_id: str) -> Optional[TrustReport]:
        """
        Fetch existing report from database.
        
        Args:
            thread_id: Email thread ID
            
        Returns:
            TrustReport if found, None otherwise
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, thread_id, primary_message_id, score, risk_level,
                       summary, findings_json, signals_json, created_at
                FROM trust_reports
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (thread_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Reconstruct report from database row
            findings_json = json.loads(row[6]) if row[6] else []
            findings = [Finding(**f) for f in findings_json]
            
            # Create TrustReport from database data
            from .models import TrustReport, RiskLevel
            report = TrustReport(
                report_id=row[0],
                thread_id=row[1],
                primary_message_id=row[2],
                score=row[3],
                risk_level=RiskLevel(row[4]),
                summary=row[5] or '',
                findings=findings,
                signals=json.loads(row[7]) if row[7] else {},
                created_at=datetime.fromisoformat(row[8])
            )
            
            return report
    
    def _save_report(self, report: TrustReport, claims: List[TrustClaim], context: VerificationContext):
        """Save report and claims to database."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Insert report (using actual schema from database.py)
                cursor.execute('''
                    INSERT INTO trust_reports (
                        id, thread_id, primary_message_id, score, risk_level,
                        summary, findings_json, signals_json, ruleset_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    report.report_id,
                    report.thread_id,
                    report.primary_message_id,
                    report.score,
                    report.risk_level.value,
                    report.summary,
                    json.dumps([f.to_dict() for f in report.findings]),
                    json.dumps(report.signals),
                    report.ruleset_version
                ))
                
                # Insert claims (using actual schema)
                for claim in claims:
                    cursor.execute('''
                        INSERT INTO trust_claims (
                            report_id, provider, claim_type, subject, issuer,
                            evidence_json, confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        report.report_id,
                        claim.provider,
                        claim.claim_type,
                        claim.subject,
                        claim.issuer,
                        json.dumps(claim.evidence),
                        claim.confidence
                    ))
                
                # Log audit trail (using actual schema)
                cursor.execute('''
                    INSERT INTO trust_audit_log (
                        action, resource_type, resource_id, details
                    ) VALUES (?, ?, ?, ?)
                ''', (
                    'report_generated',
                    'trust_report',
                    report.report_id,
                    json.dumps({
                        'plugins_used': len(set(c.provider for c in claims)),
                        'findings_count': len(report.findings),
                        'score': report.score,
                        'risk_level': report.risk_level.value
                    })
                ))
                    
                conn.commit()
                logger.info(f"Saved report {report.report_id} to database")
                    
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to save report: {e}")
                raise
    
    def list_reports(self, limit: int = 100, risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List recent trust reports.
        
        Args:
            limit: Maximum number of reports to return
            risk_level: Filter by risk level (likely_ok, caution, high_risk)
            
        Returns:
            List of report summaries
        """
        cursor = self.db_conn.cursor()
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT id, thread_id, primary_message_id, score, risk_level, created_at
                FROM trust_reports
            '''
            params = []
            
            if risk_level:
                query += ' WHERE risk_level = ?'
                params.append(risk_level)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            
            reports = []
            for row in cursor.fetchall():
                reports.append({
                    'report_id': row[0],
                    'thread_id': row[1],
                    'message_id': row[2],
                    'score': row[3],
                    'risk_level': row[4],
                    'created_at': row[5]
                })
            
        
    def get_stats(self) -> Dict[str, Any]:
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Count by risk level
            cursor.execute('''
                SELECT risk_level, COUNT(*) 
                FROM trust_reports 
                GROUP BY risk_level
            ''')
            risk_counts = dict(cursor.fetchall())
            
            # Average score
            cursor.execute('SELECT AVG(score) FROM trust_reports')
            avg_score = cursor.fetchone()[0] or 0
            
            # Total reports
            cursor.execute('SELECT COUNT(*) FROM trust_reports')
            total_reports = cursor.fetchone()[0]
            
            return {
                'total_reports': total_reports,
                'average_score': round(avg_score, 1),
                'risk_distribution': risk_counts,
                'high_risk_percentage': round(risk_counts.get('high_risk', 0) / max(total_reports, 1) * 100, 1)
            }
