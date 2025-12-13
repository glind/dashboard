"""
Email Risk Learning System

Learns from user feedback to improve email risk scoring over time.
Tracks false positives/negatives and adjusts scoring rules.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from database import DatabaseManager

logger = logging.getLogger(__name__)


class EmailRiskLearningSystem:
    """Machine learning-lite system for improving email risk assessment."""
    
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create learning tables if they don't exist."""
        try:
            with self.db.get_connection() as conn:
                # User feedback on risk assessments
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS email_risk_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        email_id TEXT,
                        sender_email TEXT NOT NULL,
                        sender_domain TEXT,
                        original_risk_score INTEGER,
                        original_risk_level TEXT,
                        user_assessment TEXT,
                        actual_risk_level TEXT,
                        feedback_reason TEXT,
                        signals_present TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Learned patterns for future scoring
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS learned_risk_patterns (
                        pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pattern_type TEXT,
                        pattern_value TEXT,
                        associated_risk TEXT,
                        confidence REAL DEFAULT 0.5,
                        match_count INTEGER DEFAULT 0,
                        correct_count INTEGER DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Deleted leads (to avoid re-suggesting)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS deleted_leads (
                        deleted_lead_id TEXT PRIMARY KEY,
                        contact_email TEXT NOT NULL,
                        contact_name TEXT,
                        company TEXT,
                        deletion_reason TEXT,
                        signals_detected TEXT,
                        lead_type TEXT,
                        score INTEGER,
                        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("✅ Learning system tables created")
        except Exception as e:
            logger.error(f"Error creating learning tables: {e}")
    
    async def record_user_feedback(
        self,
        email_id: str,
        sender_email: str,
        original_score: int,
        original_level: str,
        user_assessment: str,  # 'safe', 'risky', 'spam'
        reason: Optional[str] = None,
        signals: Optional[list] = None
    ) -> bool:
        """
        Record user feedback on email risk assessment.
        
        Args:
            email_id: Email identifier
            sender_email: Sender's email address
            original_score: System's original risk score (1-10)
            original_level: System's risk level (safe, moderate, high, critical)
            user_assessment: User's actual assessment
            reason: Why user marked it this way
            signals: Signals that were detected
        """
        try:
            feedback_id = f"feedback_{email_id}_{int(datetime.now().timestamp())}"
            
            # Extract domain
            import re
            domain_match = re.search(r'@([a-zA-Z0-9.-]+)', sender_email)
            sender_domain = domain_match.group(1).lower() if domain_match else ''
            
            # Map user assessment to risk level
            actual_risk = {
                'safe': 'safe',
                'risky': 'high',
                'spam': 'critical'
            }.get(user_assessment, 'moderate')
            
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO email_risk_feedback (
                        feedback_id, email_id, sender_email, sender_domain,
                        original_risk_score, original_risk_level,
                        user_assessment, actual_risk_level, feedback_reason,
                        signals_present
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback_id, email_id, sender_email, sender_domain,
                    original_score, original_level, user_assessment,
                    actual_risk, reason, ','.join(signals) if signals else ''
                ))
                conn.commit()
            
            # Update learned patterns
            await self._update_patterns(sender_domain, signals, actual_risk)
            
            logger.info(f"✅ Recorded feedback for {sender_email}: {user_assessment}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")
            return False
    
    async def _update_patterns(
        self,
        domain: str,
        signals: Optional[list],
        actual_risk: str
    ):
        """Update learned patterns based on feedback."""
        try:
            with self.db.get_connection() as conn:
                # Update domain pattern
                conn.execute("""
                    INSERT INTO learned_risk_patterns (
                        pattern_type, pattern_value, associated_risk,
                        match_count, correct_count
                    ) VALUES ('domain', ?, ?, 1, 1)
                    ON CONFLICT(pattern_type, pattern_value) DO UPDATE SET
                        match_count = match_count + 1,
                        correct_count = correct_count + 1,
                        confidence = CAST(correct_count AS REAL) / match_count,
                        updated_at = CURRENT_TIMESTAMP
                """, (domain, actual_risk))
                
                # Update signal patterns
                if signals:
                    for signal in signals:
                        conn.execute("""
                            INSERT INTO learned_risk_patterns (
                                pattern_type, pattern_value, associated_risk,
                                match_count, correct_count
                            ) VALUES ('signal', ?, ?, 1, 1)
                            ON CONFLICT(pattern_type, pattern_value) DO UPDATE SET
                                match_count = match_count + 1,
                                correct_count = correct_count + 1,
                                confidence = CAST(correct_count AS REAL) / match_count,
                                updated_at = CURRENT_TIMESTAMP
                        """, (signal, actual_risk))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating patterns: {e}")
    
    def get_learned_risk_adjustment(
        self,
        sender_domain: str,
        signals: list
    ) -> int:
        """
        Get risk score adjustment based on learned patterns.
        
        Returns adjustment value (-3 to +3) to add to base risk score.
        """
        try:
            adjustment = 0
            
            with self.db.get_connection() as conn:
                # Check domain history
                domain_row = conn.execute("""
                    SELECT associated_risk, confidence
                    FROM learned_risk_patterns
                    WHERE pattern_type = 'domain'
                    AND pattern_value = ?
                    AND match_count >= 3
                    ORDER BY confidence DESC
                    LIMIT 1
                """, (sender_domain,)).fetchone()
                
                if domain_row:
                    risk_level, confidence = domain_row
                    if confidence > 0.7:
                        if risk_level == 'safe':
                            adjustment -= 2
                        elif risk_level in ['high', 'critical']:
                            adjustment += 2
                
                # Check signal patterns
                for signal in signals[:3]:  # Limit to top 3 signals
                    signal_row = conn.execute("""
                        SELECT associated_risk, confidence
                        FROM learned_risk_patterns
                        WHERE pattern_type = 'signal'
                        AND pattern_value = ?
                        AND match_count >= 2
                        ORDER BY confidence DESC
                        LIMIT 1
                    """, (signal,)).fetchone()
                    
                    if signal_row:
                        risk_level, confidence = signal_row
                        if confidence > 0.6:
                            if risk_level == 'safe':
                                adjustment -= 1
                            elif risk_level in ['high', 'critical']:
                                adjustment += 1
            
            # Cap adjustment
            return max(-3, min(3, adjustment))
            
        except Exception as e:
            logger.error(f"Error getting learned adjustment: {e}")
            return 0
    
    def record_deleted_lead(
        self,
        contact_email: str,
        contact_name: str,
        company: Optional[str],
        reason: str,
        signals: list,
        lead_type: str,
        score: int
    ) -> bool:
        """Record a deleted lead so we don't suggest it again."""
        try:
            deleted_id = f"deleted_{contact_email}_{int(datetime.now().timestamp())}"
            
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO deleted_leads (
                        deleted_lead_id, contact_email, contact_name,
                        company, deletion_reason, signals_detected,
                        lead_type, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    deleted_id, contact_email, contact_name,
                    company, reason, ','.join(signals),
                    lead_type, score
                ))
                conn.commit()
            
            logger.info(f"✅ Recorded deleted lead: {contact_email} - {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording deleted lead: {e}")
            return False
    
    def was_lead_deleted(self, contact_email: str) -> bool:
        """Check if this contact was previously deleted as a lead."""
        try:
            with self.db.get_connection() as conn:
                result = conn.execute("""
                    SELECT deleted_lead_id FROM deleted_leads
                    WHERE contact_email = ? COLLATE NOCASE
                """, (contact_email.lower(),)).fetchone()
                
                return result is not None
                
        except Exception as e:
            logger.error(f"Error checking deleted lead: {e}")
            return False
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics on feedback and learning performance."""
        try:
            with self.db.get_connection() as conn:
                # Total feedback count
                total = conn.execute(
                    "SELECT COUNT(*) FROM email_risk_feedback"
                ).fetchone()[0]
                
                # Feedback by assessment
                by_assessment = {}
                rows = conn.execute("""
                    SELECT user_assessment, COUNT(*) as count
                    FROM email_risk_feedback
                    GROUP BY user_assessment
                """).fetchall()
                for row in rows:
                    by_assessment[row[0]] = row[1]
                
                # False positives (marked safe when system said risky)
                false_positives = conn.execute("""
                    SELECT COUNT(*) FROM email_risk_feedback
                    WHERE user_assessment = 'safe'
                    AND original_risk_score >= 7
                """).fetchone()[0]
                
                # False negatives (marked risky when system said safe)
                false_negatives = conn.execute("""
                    SELECT COUNT(*) FROM email_risk_feedback
                    WHERE user_assessment IN ('risky', 'spam')
                    AND original_risk_score <= 3
                """).fetchone()[0]
                
                # Learned patterns count
                patterns = conn.execute("""
                    SELECT COUNT(*) FROM learned_risk_patterns
                    WHERE confidence > 0.7
                """).fetchone()[0]
                
                # Deleted leads
                deleted_leads = conn.execute(
                    "SELECT COUNT(*) FROM deleted_leads"
                ).fetchone()[0]
                
                # Accuracy (when enough data)
                accuracy = 0.0
                if total > 10:
                    correct = total - false_positives - false_negatives
                    accuracy = (correct / total) * 100
                
                return {
                    'total_feedback': total,
                    'by_assessment': by_assessment,
                    'false_positives': false_positives,
                    'false_negatives': false_negatives,
                    'accuracy_percent': round(accuracy, 1),
                    'learned_patterns': patterns,
                    'deleted_leads': deleted_leads
                }
                
        except Exception as e:
            logger.error(f"Error getting feedback stats: {e}")
            return {}
