"""
Company Profiler - Analyzes specific company interactions to create templates for finding similar opportunities.

This module creates detailed profiles of successful business relationships like:
- Buildly: Software development platform and consulting
- Open Build: Development tools and methodologies  
- Oregon Software: Custom software development

It learns patterns that can be applied to find similar high-potential leads.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
from pathlib import Path
import json
import re

from processors.email_meeting_analyzer import EmailMeetingAnalyzer, CompanyProfile
from processors.task_ai_trainer import TaskAITrainer

logger = logging.getLogger(__name__)


@dataclass
class CompanyTemplate:
    """Template created from successful company interactions."""
    template_name: str
    source_companies: List[str]
    industry_characteristics: Dict[str, Any]
    interaction_patterns: Dict[str, Any]
    success_indicators: List[str]
    communication_style: Dict[str, Any]
    project_types: List[str]
    typical_engagement_timeline: str
    decision_makers: Dict[str, Any]
    technical_requirements: List[str]
    business_model_indicators: List[str]
    company_size_range: str
    geographic_preferences: List[str]
    matching_score_weights: Dict[str, float]


@dataclass
class LeadScoringCriteria:
    """Criteria for scoring potential leads based on learned patterns."""
    industry_match: float
    size_compatibility: float
    technical_alignment: float
    communication_style_fit: float
    project_type_match: float
    timeline_compatibility: float
    decision_maker_accessibility: float
    overall_potential: float


class CompanyProfiler:
    """Creates detailed company interaction profiles and templates for lead generation."""
    
    def __init__(self):
        self.email_analyzer = EmailMeetingAnalyzer()
        self.task_trainer = TaskAITrainer()
        self.company_templates = {}
        self.known_successful_companies = {
            'buildly': {
                'name': 'Buildly',
                'domain': 'buildly.io',
                'industry': 'Low-Code/No-Code Platform',
                'focus_areas': ['Platform Development', 'API Integration', 'Workflow Automation']
            },
            'openbuild': {
                'name': 'Open Build',
                'domain': 'openbuild.xyz',
                'industry': 'Developer Tools',
                'focus_areas': ['Open Source', 'Community Building', 'Developer Experience']
            },
            'oregon-software': {
                'name': 'Oregon Software',
                'domain': 'oregonsoftware.com',
                'industry': 'Custom Software Development',
                'focus_areas': ['Enterprise Solutions', 'Legacy Modernization', 'System Integration']
            }
        }
    
    async def create_company_profiles(self, emails: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> Dict[str, CompanyTemplate]:
        """Create detailed company profiles and templates from interaction data."""
        try:
            logger.info("Creating detailed company profiles from interaction data...")
            
            # Analyze email patterns for all companies
            email_analysis = await self.email_analyzer.analyze_email_patterns(emails)
            company_profiles = {cp['name']: cp for cp in email_analysis.get('company_profiles', [])}
            
            # Analyze task patterns to understand work preferences
            user_preferences = await self.task_trainer.analyze_task_patterns()
            
            # Create templates for each known successful company
            templates = {}
            
            for company_key, company_info in self.known_successful_companies.items():
                template = await self._create_company_template(
                    company_info, 
                    company_profiles.get(company_info['name']), 
                    emails, 
                    tasks, 
                    user_preferences
                )
                templates[company_key] = template
            
            # Create composite templates for similar company types
            templates['platform_companies'] = self._create_platform_company_template(templates)
            templates['consulting_companies'] = self._create_consulting_company_template(templates)
            templates['enterprise_clients'] = self._create_enterprise_client_template(templates)
            
            self.company_templates = templates
            
            # Save templates for future use
            await self._save_company_templates(templates)
            
            logger.info(f"Created {len(templates)} company templates")
            return templates
            
        except Exception as e:
            logger.error(f"Error creating company profiles: {e}")
            return {}
    
    async def _create_company_template(self, company_info: Dict[str, Any], email_profile: Optional[Dict[str, Any]], 
                                     emails: List[Dict[str, Any]], tasks: List[Dict[str, Any]], 
                                     user_preferences) -> CompanyTemplate:
        """Create a detailed template for a specific company."""
        
        company_name = company_info['name']
        
        # Extract company-specific emails and tasks
        company_emails = self._filter_company_interactions(emails, company_info['domain'], company_name)
        company_tasks = self._filter_company_tasks(tasks, company_name)
        
        # Analyze interaction patterns
        interaction_patterns = self._analyze_company_interactions(company_emails, company_tasks)
        
        # Extract communication style
        communication_style = self._analyze_communication_style(company_emails)
        
        # Determine project types and technical requirements
        project_analysis = self._analyze_project_types(company_emails, company_tasks)
        
        # Analyze decision maker patterns
        decision_makers = self._analyze_decision_makers(company_emails)
        
        # Create success indicators
        success_indicators = self._identify_success_indicators(company_emails, company_tasks, email_profile)
        
        # Determine engagement timeline
        timeline = self._analyze_engagement_timeline(company_emails, company_tasks)
        
        template = CompanyTemplate(
            template_name=f"{company_name} Template",
            source_companies=[company_name],
            industry_characteristics=self._extract_industry_characteristics(company_info, company_emails),
            interaction_patterns=interaction_patterns,
            success_indicators=success_indicators,
            communication_style=communication_style,
            project_types=project_analysis['types'],
            typical_engagement_timeline=timeline,
            decision_makers=decision_makers,
            technical_requirements=project_analysis['technical_requirements'],
            business_model_indicators=self._extract_business_model_indicators(company_emails, company_info),
            company_size_range=self._estimate_company_size_range(company_info, email_profile),
            geographic_preferences=self._analyze_geographic_patterns(company_emails),
            matching_score_weights=self._calculate_matching_weights(user_preferences)
        )
        
        return template
    
    def _filter_company_interactions(self, emails: List[Dict[str, Any]], domain: str, company_name: str) -> List[Dict[str, Any]]:
        """Filter emails for a specific company."""
        company_emails = []
        
        for email in emails:
            sender = email.get('sender', '').lower()
            subject = email.get('subject', '').lower()
            snippet = email.get('snippet', '').lower()
            
            # Check if email is from this company
            if (domain.lower() in sender or 
                company_name.lower() in sender or 
                company_name.lower() in subject or 
                company_name.lower() in snippet):
                company_emails.append(email)
        
        return company_emails
    
    def _filter_company_tasks(self, tasks: List[Dict[str, Any]], company_name: str) -> List[Dict[str, Any]]:
        """Filter tasks related to a specific company."""
        company_tasks = []
        
        for task in tasks:
            title = task.get('title', '').lower()
            description = task.get('description', '').lower()
            
            if company_name.lower() in title or company_name.lower() in description:
                company_tasks.append(task)
        
        return company_tasks
    
    def _analyze_company_interactions(self, emails: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze interaction patterns for a company."""
        
        # Analyze email frequency and timing
        email_frequency = self._calculate_interaction_frequency(emails)
        
        # Analyze task completion patterns
        task_patterns = self._analyze_task_completion_patterns(tasks)
        
        # Analyze meeting patterns
        meeting_emails = [email for email in emails if self._is_meeting_related(email)]
        meeting_patterns = self._analyze_meeting_patterns(meeting_emails)
        
        # Response time analysis
        response_patterns = self._analyze_response_patterns(emails)
        
        return {
            'email_frequency': email_frequency,
            'task_patterns': task_patterns,
            'meeting_patterns': meeting_patterns,
            'response_patterns': response_patterns,
            'total_interactions': len(emails),
            'total_tasks': len(tasks),
            'meeting_to_email_ratio': len(meeting_emails) / len(emails) if emails else 0
        }
    
    def _analyze_communication_style(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze communication style from email interactions."""
        
        # Analyze email formality
        formality_indicators = {
            'formal': ['dear', 'sincerely', 'regards', 'respectfully'],
            'casual': ['hi', 'hey', 'thanks', 'cheers'],
            'business': ['please', 'kindly', 'appreciate', 'looking forward']
        }
        
        formality_scores = {style: 0 for style in formality_indicators}
        
        for email in emails:
            content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
            
            for style, indicators in formality_indicators.items():
                for indicator in indicators:
                    if indicator in content:
                        formality_scores[style] += 1
        
        # Determine dominant style
        dominant_style = max(formality_scores.keys(), key=lambda k: formality_scores[k]) if any(formality_scores.values()) else 'business'
        
        # Analyze technical depth
        technical_terms = ['api', 'integration', 'development', 'platform', 'architecture', 'system']
        technical_score = sum(1 for email in emails for term in technical_terms 
                            if term in (email.get('subject', '') + ' ' + email.get('snippet', '')).lower())
        
        # Analyze urgency patterns
        urgency_terms = ['urgent', 'asap', 'priority', 'immediate', 'deadline']
        urgency_score = sum(1 for email in emails for term in urgency_terms 
                          if term in (email.get('subject', '') + ' ' + email.get('snippet', '')).lower())
        
        return {
            'dominant_style': dominant_style,
            'formality_scores': formality_scores,
            'technical_depth': min(technical_score / len(emails), 1.0) if emails else 0,
            'urgency_level': min(urgency_score / len(emails), 1.0) if emails else 0,
            'preferred_communication_channels': ['email', 'video_call', 'phone'],  # Could be enhanced
            'response_time_expectations': self._analyze_response_time_expectations(emails)
        }
    
    def _analyze_project_types(self, emails: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze types of projects and technical requirements."""
        
        # Project type keywords
        project_keywords = {
            'Web Development': ['website', 'web app', 'frontend', 'backend', 'full stack'],
            'Mobile Development': ['mobile', 'ios', 'android', 'app store', 'native'],
            'API Integration': ['api', 'integration', 'webhook', 'rest', 'graphql'],
            'Platform Development': ['platform', 'saas', 'infrastructure', 'scalable'],
            'Data Analytics': ['analytics', 'dashboard', 'reporting', 'data', 'metrics'],
            'System Migration': ['migration', 'upgrade', 'modernization', 'legacy'],
            'Consulting': ['strategy', 'consultation', 'advisory', 'planning'],
            'Custom Software': ['custom', 'bespoke', 'tailored', 'specific requirements']
        }
        
        project_scores = {project_type: 0 for project_type in project_keywords}
        
        # Analyze emails and tasks for project type indicators
        all_content = []
        for email in emails:
            all_content.append(email.get('subject', '') + ' ' + email.get('snippet', ''))
        for task in tasks:
            all_content.append(task.get('title', '') + ' ' + task.get('description', ''))
        
        combined_content = ' '.join(all_content).lower()
        
        for project_type, keywords in project_keywords.items():
            for keyword in keywords:
                if keyword in combined_content:
                    project_scores[project_type] += 1
        
        # Get top project types
        top_project_types = sorted(project_scores.items(), key=lambda x: x[1], reverse=True)
        relevant_types = [ptype for ptype, score in top_project_types if score > 0][:5]
        
        # Extract technical requirements
        technical_requirements = self._extract_technical_requirements(combined_content)
        
        return {
            'types': relevant_types,
            'project_scores': project_scores,
            'technical_requirements': technical_requirements,
            'complexity_indicators': self._analyze_complexity_indicators(combined_content)
        }
    
    def _extract_technical_requirements(self, content: str) -> List[str]:
        """Extract technical requirements from content."""
        tech_patterns = {
            'programming_languages': ['python', 'javascript', 'java', 'react', 'node.js', 'php', 'ruby'],
            'databases': ['mysql', 'postgresql', 'mongodb', 'redis', 'sqlite'],
            'cloud_platforms': ['aws', 'azure', 'google cloud', 'gcp', 'heroku', 'digital ocean'],
            'frameworks': ['django', 'flask', 'express', 'spring', 'laravel', 'rails'],
            'integration_tech': ['rest api', 'graphql', 'webhook', 'oauth', 'jwt', 'soap'],
            'frontend_tech': ['html5', 'css3', 'vue.js', 'angular', 'bootstrap', 'tailwind']
        }
        
        requirements = []
        content_lower = content.lower()
        
        for category, technologies in tech_patterns.items():
            for tech in technologies:
                if tech in content_lower:
                    requirements.append(tech)
        
        return list(set(requirements))  # Remove duplicates
    
    def _analyze_decision_makers(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze decision maker patterns from email interactions."""
        
        # Extract sender information
        senders = []
        for email in emails:
            sender = email.get('sender', '')
            if sender:
                senders.append(sender)
        
        # Analyze titles and roles (basic heuristic)
        title_indicators = {
            'C-Level': ['ceo', 'cto', 'cfo', 'coo', 'chief'],
            'VP/Director': ['vp', 'vice president', 'director'],
            'Manager': ['manager', 'lead', 'head of'],
            'Technical': ['developer', 'engineer', 'architect', 'technical'],
            'Business': ['business', 'product', 'project', 'account']
        }
        
        role_counts = {role: 0 for role in title_indicators}
        
        for sender in senders:
            sender_lower = sender.lower()
            for role, indicators in title_indicators.items():
                if any(indicator in sender_lower for indicator in indicators):
                    role_counts[role] += 1
        
        return {
            'primary_contact_types': role_counts,
            'decision_maker_accessibility': self._calculate_decision_maker_accessibility(role_counts),
            'typical_approval_chain': self._infer_approval_chain(role_counts),
            'contact_diversity': len(set(senders))
        }
    
    def _identify_success_indicators(self, emails: List[Dict[str, Any]], tasks: List[Dict[str, Any]], 
                                   email_profile: Optional[Dict[str, Any]]) -> List[str]:
        """Identify indicators of successful engagement."""
        
        indicators = []
        
        # Email-based indicators
        if emails:
            # Multiple ongoing threads
            if len(emails) > 5:
                indicators.append('sustained_communication')
            
            # Meeting scheduling
            meeting_emails = [e for e in emails if self._is_meeting_related(e)]
            if meeting_emails:
                indicators.append('meeting_engagement')
            
            # Technical discussions
            technical_content = sum(1 for email in emails 
                                  if any(term in (email.get('subject', '') + ' ' + email.get('snippet', '')).lower() 
                                        for term in ['api', 'technical', 'architecture', 'integration']))
            if technical_content > 0:
                indicators.append('technical_alignment')
        
        # Task-based indicators
        if tasks:
            completed_tasks = [task for task in tasks if task.get('status') == 'completed']
            if len(completed_tasks) > len(tasks) * 0.7:  # 70% completion rate
                indicators.append('high_task_completion')
            
            # Business-focused tasks
            business_tasks = [task for task in tasks 
                            if any(term in (task.get('title', '') + ' ' + task.get('description', '')).lower()
                                  for term in ['proposal', 'contract', 'meeting', 'demo'])]
            if business_tasks:
                indicators.append('business_progression')
        
        # Email profile indicators
        if email_profile:
            if email_profile.get('business_potential', 0) > 0.7:
                indicators.append('high_business_potential')
            
            if email_profile.get('meeting_count', 0) > 0:
                indicators.append('meeting_history')
        
        return indicators
    
    def _analyze_engagement_timeline(self, emails: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> str:
        """Analyze typical engagement timeline."""
        
        if not emails:
            return "Unknown"
        
        # Calculate span of interactions
        dates = []
        for email in emails:
            date_str = email.get('date', '')
            if date_str:
                try:
                    # Simplified date parsing
                    date = datetime.now()  # Placeholder - would need proper parsing
                    dates.append(date)
                except:
                    continue
        
        if len(dates) < 2:
            return "Short-term (< 1 month)"
        
        # This is a simplified calculation - would need proper date parsing
        if len(emails) > 20:
            return "Long-term (6+ months)"
        elif len(emails) > 10:
            return "Medium-term (3-6 months)"
        else:
            return "Short-term (1-3 months)"
    
    def _extract_industry_characteristics(self, company_info: Dict[str, Any], emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract industry-specific characteristics."""
        
        industry = company_info.get('industry', 'Technology')
        focus_areas = company_info.get('focus_areas', [])
        
        # Analyze industry-specific terms in emails
        industry_terms = []
        for email in emails:
            content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
            # Extract relevant terms based on industry
            if 'platform' in industry.lower():
                platform_terms = ['saas', 'platform', 'integration', 'workflow', 'automation']
                industry_terms.extend([term for term in platform_terms if term in content])
            elif 'development' in industry.lower():
                dev_terms = ['software', 'development', 'custom', 'solution', 'system']
                industry_terms.extend([term for term in dev_terms if term in content])
        
        return {
            'primary_industry': industry,
            'focus_areas': focus_areas,
            'industry_specific_terms': list(set(industry_terms)),
            'market_segment': self._determine_market_segment(industry, emails),
            'technology_stack_preferences': self._analyze_tech_stack_preferences(emails)
        }
    
    def _extract_business_model_indicators(self, emails: List[Dict[str, Any]], company_info: Dict[str, Any]) -> List[str]:
        """Extract business model indicators."""
        
        indicators = []
        
        # Analyze email content for business model clues
        all_content = ' '.join([email.get('subject', '') + ' ' + email.get('snippet', '') 
                               for email in emails]).lower()
        
        business_models = {
            'SaaS': ['subscription', 'monthly', 'saas', 'platform', 'cloud'],
            'Consulting': ['consulting', 'services', 'hourly', 'project-based'],
            'Product': ['license', 'perpetual', 'product', 'software license'],
            'Enterprise': ['enterprise', 'on-premise', 'custom', 'implementation'],
            'Marketplace': ['marketplace', 'commission', 'transaction', 'vendors']
        }
        
        for model, keywords in business_models.items():
            if any(keyword in all_content for keyword in keywords):
                indicators.append(model)
        
        return indicators
    
    def _estimate_company_size_range(self, company_info: Dict[str, Any], email_profile: Optional[Dict[str, Any]]) -> str:
        """Estimate appropriate company size range for this type of engagement."""
        
        if email_profile:
            estimated_size = email_profile.get('size_estimate', 'Medium')
            return f"{estimated_size} Companies"
        
        # Default based on industry type
        industry = company_info.get('industry', '')
        if 'platform' in industry.lower() or 'saas' in industry.lower():
            return "Medium to Large Companies"
        elif 'consulting' in industry.lower():
            return "Small to Medium Companies"
        else:
            return "Small to Large Companies"
    
    def _analyze_geographic_patterns(self, emails: List[Dict[str, Any]]) -> List[str]:
        """Analyze geographic preferences from email interactions."""
        
        # This would be enhanced with timezone analysis or domain analysis
        # For now, return common business regions
        return ["North America", "Europe", "English-speaking markets"]
    
    def _calculate_matching_weights(self, user_preferences) -> Dict[str, float]:
        """Calculate scoring weights based on user preferences."""
        
        # Default weights that can be adjusted based on learned preferences
        weights = {
            'industry_match': 0.25,
            'size_compatibility': 0.15,
            'technical_alignment': 0.20,
            'communication_style_fit': 0.10,
            'project_type_match': 0.15,
            'timeline_compatibility': 0.10,
            'decision_maker_accessibility': 0.05
        }
        
        # Adjust based on user preferences if available
        if user_preferences:
            if user_preferences.company_interaction_patterns.get('company_completion_rate', 0) > 0.8:
                weights['project_type_match'] += 0.05
                weights['technical_alignment'] += 0.05
        
        return weights
    
    def _create_platform_company_template(self, templates: Dict[str, CompanyTemplate]) -> CompanyTemplate:
        """Create a composite template for platform companies."""
        
        platform_companies = ['buildly', 'openbuild']
        relevant_templates = [templates[key] for key in platform_companies if key in templates]
        
        if not relevant_templates:
            return self._create_default_template('Platform Companies')
        
        return self._merge_templates(relevant_templates, 'Platform Companies Template')
    
    def _create_consulting_company_template(self, templates: Dict[str, CompanyTemplate]) -> CompanyTemplate:
        """Create a composite template for consulting companies."""
        
        consulting_companies = ['oregon-software']  # Could include more
        relevant_templates = [templates[key] for key in consulting_companies if key in templates]
        
        if not relevant_templates:
            return self._create_default_template('Consulting Companies')
        
        return self._merge_templates(relevant_templates, 'Consulting Companies Template')
    
    def _create_enterprise_client_template(self, templates: Dict[str, CompanyTemplate]) -> CompanyTemplate:
        """Create a template for enterprise client engagement."""
        
        # Merge insights from all templates to create enterprise client template
        all_templates = list(templates.values())
        
        if not all_templates:
            return self._create_default_template('Enterprise Clients')
        
        return self._merge_templates(all_templates, 'Enterprise Client Template')
    
    def _merge_templates(self, templates: List[CompanyTemplate], name: str) -> CompanyTemplate:
        """Merge multiple templates into a composite template."""
        
        if not templates:
            return self._create_default_template(name)
        
        # Combine characteristics from all templates
        combined_project_types = []
        combined_success_indicators = []
        combined_technical_requirements = []
        combined_business_models = []
        
        for template in templates:
            combined_project_types.extend(template.project_types)
            combined_success_indicators.extend(template.success_indicators)
            combined_technical_requirements.extend(template.technical_requirements)
            combined_business_models.extend(template.business_model_indicators)
        
        # Get most common characteristics
        common_project_types = list(set(combined_project_types))[:5]
        common_success_indicators = list(set(combined_success_indicators))
        common_tech_requirements = list(set(combined_technical_requirements))[:10]
        common_business_models = list(set(combined_business_models))
        
        # Average scoring weights
        avg_weights = {}
        if templates and hasattr(templates[0], 'matching_score_weights') and templates[0].matching_score_weights:
            weight_keys = templates[0].matching_score_weights.keys()
            for key in weight_keys:
                avg_weights[key] = sum(t.matching_score_weights.get(key, 0) for t in templates if hasattr(t, 'matching_score_weights') and t.matching_score_weights) / len(templates)
        else:
            # Default weights if no templates have matching_score_weights
            avg_weights = {
                'industry_match': 0.3,
                'size_match': 0.2,
                'tech_match': 0.2,
                'location_match': 0.1,
                'engagement_fit': 0.2
            }
        
        return CompanyTemplate(
            template_name=name,
            source_companies=[comp for template in templates for comp in template.source_companies],
            industry_characteristics=self._merge_industry_characteristics(templates),
            interaction_patterns=self._merge_interaction_patterns(templates),
            success_indicators=common_success_indicators,
            communication_style=self._merge_communication_styles(templates),
            project_types=common_project_types,
            typical_engagement_timeline="Medium-term (3-6 months)",  # Average
            decision_makers=self._merge_decision_maker_patterns(templates),
            technical_requirements=common_tech_requirements,
            business_model_indicators=common_business_models,
            company_size_range="Small to Large Companies",
            geographic_preferences=["North America", "Europe"],
            matching_score_weights=avg_weights
        )
    
    def _create_default_template(self, name: str) -> CompanyTemplate:
        """Create a default template when no data is available."""
        
        return CompanyTemplate(
            template_name=name,
            source_companies=[],
            industry_characteristics={'primary_industry': 'Technology', 'focus_areas': []},
            interaction_patterns={},
            success_indicators=['sustained_communication', 'meeting_engagement'],
            communication_style={'dominant_style': 'business', 'technical_depth': 0.5},
            project_types=['Web Development', 'API Integration'],
            typical_engagement_timeline="Medium-term (3-6 months)",
            decision_makers={'primary_contact_types': {}},
            technical_requirements=['python', 'javascript', 'rest api'],
            business_model_indicators=['SaaS', 'Consulting'],
            company_size_range="Small to Medium Companies",
            geographic_preferences=["North America"],
            matching_score_weights={
                'industry_match': 0.25, 'size_compatibility': 0.15,
                'technical_alignment': 0.20, 'communication_style_fit': 0.10,
                'project_type_match': 0.15, 'timeline_compatibility': 0.10,
                'decision_maker_accessibility': 0.05
            }
        )
    
    async def _save_company_templates(self, templates: Dict[str, CompanyTemplate]) -> None:
        """Save company templates to file for future use."""
        try:
            # Convert templates to serializable format
            serializable_templates = {}
            for key, template in templates.items():
                serializable_templates[key] = asdict(template)
            
            # Get project root (two levels up from processors/)
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            
            # Save to JSON file
            templates_file = data_dir / "company_templates.json"
            with open(templates_file, 'w') as f:
                json.dump(serializable_templates, f, indent=2, default=str)
            
            logger.info(f"Saved {len(templates)} company templates")
            
        except Exception as e:
            logger.error(f"Error saving company templates: {e}")
    
    # Helper methods for analysis
    def _is_meeting_related(self, email: Dict[str, Any]) -> bool:
        """Check if email is meeting-related."""
        meeting_keywords = ['meeting', 'call', 'schedule', 'calendar', 'demo', 'presentation']
        content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
        return any(keyword in content for keyword in meeting_keywords)
    
    def _calculate_interaction_frequency(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate interaction frequency metrics."""
        if not emails:
            return {'frequency': 0, 'pattern': 'none'}
        
        # Simplified frequency calculation
        total_emails = len(emails)
        if total_emails > 20:
            return {'frequency': total_emails, 'pattern': 'high_frequency'}
        elif total_emails > 5:
            return {'frequency': total_emails, 'pattern': 'medium_frequency'}
        else:
            return {'frequency': total_emails, 'pattern': 'low_frequency'}
    
    def _analyze_task_completion_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze task completion patterns."""
        if not tasks:
            return {'completion_rate': 0, 'total_tasks': 0}
        
        completed_tasks = [task for task in tasks if task.get('status') == 'completed']
        completion_rate = len(completed_tasks) / len(tasks)
        
        return {
            'completion_rate': completion_rate,
            'total_tasks': len(tasks),
            'completed_tasks': len(completed_tasks),
            'task_types': [task.get('category', 'general') for task in tasks]
        }
    
    def _analyze_meeting_patterns(self, meeting_emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze meeting patterns."""
        return {
            'total_meetings': len(meeting_emails),
            'meeting_frequency': 'regular' if len(meeting_emails) > 3 else 'occasional',
            'meeting_types': self._categorize_meeting_types(meeting_emails)
        }
    
    def _categorize_meeting_types(self, meeting_emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize meeting types."""
        types = {'demo': 0, 'sync': 0, 'technical': 0, 'business': 0}
        
        for email in meeting_emails:
            content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
            
            if any(term in content for term in ['demo', 'demonstration', 'showcase']):
                types['demo'] += 1
            elif any(term in content for term in ['sync', 'standup', 'check-in']):
                types['sync'] += 1
            elif any(term in content for term in ['technical', 'architecture', 'development']):
                types['technical'] += 1
            else:
                types['business'] += 1
        
        return types
    
    def _analyze_response_patterns(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze response time patterns."""
        # Simplified analysis - would need proper date parsing for accuracy
        return {
            'estimated_response_time': '24-48 hours',
            'response_consistency': 'good',
            'preferred_communication_hours': 'business_hours'
        }
    
    def _analyze_response_time_expectations(self, emails: List[Dict[str, Any]]) -> str:
        """Analyze response time expectations."""
        # Look for urgency indicators
        urgent_count = 0
        for email in emails:
            content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
            if any(term in content for term in ['urgent', 'asap', 'immediate']):
                urgent_count += 1
        
        if urgent_count > len(emails) * 0.3:  # 30% urgent
            return 'fast_response_expected'
        else:
            return 'standard_business_response'
    
    def _analyze_complexity_indicators(self, content: str) -> List[str]:
        """Analyze project complexity indicators."""
        complexity_terms = {
            'high_complexity': ['enterprise', 'scalable', 'architecture', 'complex', 'advanced'],
            'medium_complexity': ['integration', 'api', 'database', 'system'],
            'low_complexity': ['simple', 'basic', 'straightforward', 'minimal']
        }
        
        indicators = []
        content_lower = content.lower()
        
        for complexity, terms in complexity_terms.items():
            if any(term in content_lower for term in terms):
                indicators.append(complexity)
        
        return indicators
    
    def _calculate_decision_maker_accessibility(self, role_counts: Dict[str, int]) -> float:
        """Calculate how accessible decision makers are."""
        # Higher score for more C-level and VP contacts
        c_level_score = role_counts.get('C-Level', 0) * 0.5
        vp_score = role_counts.get('VP/Director', 0) * 0.3
        manager_score = role_counts.get('Manager', 0) * 0.2
        
        total_contacts = sum(role_counts.values())
        if total_contacts == 0:
            return 0.5  # Default
        
        accessibility_score = (c_level_score + vp_score + manager_score) / total_contacts
        return min(accessibility_score, 1.0)
    
    def _infer_approval_chain(self, role_counts: Dict[str, int]) -> List[str]:
        """Infer typical approval chain."""
        chain = []
        
        if role_counts.get('Technical', 0) > 0:
            chain.append('Technical Review')
        if role_counts.get('Manager', 0) > 0:
            chain.append('Management Approval')
        if role_counts.get('VP/Director', 0) > 0:
            chain.append('Executive Review')
        if role_counts.get('C-Level', 0) > 0:
            chain.append('C-Level Decision')
        
        return chain if chain else ['Standard Approval Process']
    
    def _determine_market_segment(self, industry: str, emails: List[Dict[str, Any]]) -> str:
        """Determine market segment."""
        if 'platform' in industry.lower():
            return 'B2B SaaS'
        elif 'consulting' in industry.lower():
            return 'Professional Services'
        else:
            return 'Technology Solutions'
    
    def _analyze_tech_stack_preferences(self, emails: List[Dict[str, Any]]) -> List[str]:
        """Analyze technology stack preferences."""
        tech_terms = ['python', 'javascript', 'react', 'node.js', 'aws', 'docker']
        
        preferences = []
        all_content = ' '.join([email.get('subject', '') + ' ' + email.get('snippet', '') 
                               for email in emails]).lower()
        
        for tech in tech_terms:
            if tech in all_content:
                preferences.append(tech)
        
        return preferences
    
    def _merge_industry_characteristics(self, templates: List[CompanyTemplate]) -> Dict[str, Any]:
        """Merge industry characteristics from multiple templates."""
        industries = [t.industry_characteristics.get('primary_industry', '') for t in templates]
        focus_areas = []
        for t in templates:
            focus_areas.extend(t.industry_characteristics.get('focus_areas', []))
        
        return {
            'primary_industry': max(set(industries), key=industries.count) if industries else 'Technology',
            'focus_areas': list(set(focus_areas)),
            'market_segment': 'B2B Technology Solutions'
        }
    
    def _merge_interaction_patterns(self, templates: List[CompanyTemplate]) -> Dict[str, Any]:
        """Merge interaction patterns."""
        total_interactions = sum(t.interaction_patterns.get('total_interactions', 0) for t in templates)
        total_meetings = sum(t.interaction_patterns.get('total_meetings', 0) for t in templates)
        
        return {
            'average_interactions': total_interactions / len(templates) if templates else 0,
            'average_meetings': total_meetings / len(templates) if templates else 0,
            'engagement_level': 'high' if total_interactions > 50 else 'medium'
        }
    
    def _merge_communication_styles(self, templates: List[CompanyTemplate]) -> Dict[str, Any]:
        """Merge communication styles."""
        styles = [t.communication_style.get('dominant_style', 'business') for t in templates]
        technical_depths = [t.communication_style.get('technical_depth', 0.5) for t in templates]
        
        return {
            'dominant_style': max(set(styles), key=styles.count) if styles else 'business',
            'technical_depth': sum(technical_depths) / len(technical_depths) if technical_depths else 0.5,
            'response_time_expectations': 'standard_business_response'
        }
    
    def _merge_decision_maker_patterns(self, templates: List[CompanyTemplate]) -> Dict[str, Any]:
        """Merge decision maker patterns."""
        return {
            'typical_contact_level': 'Management to Executive',
            'decision_maker_accessibility': 0.7,  # Average
            'approval_complexity': 'medium'
        }