"""
Lead Generator - Uses learned patterns to identify and score potential business opportunities.

This module:
- Uses company templates to search for similar opportunities
- Scores potential leads based on learned success patterns
- Integrates with multiple data sources (web scraping, APIs, directories)
- Provides actionable lead recommendations with contact information
"""

import logging
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
from pathlib import Path
import re
import random

from processors.company_profiler import CompanyProfiler, CompanyTemplate, LeadScoringCriteria

# Import real startup discovery
try:
    from processors.startup_discovery import discover_real_startups
    REAL_DISCOVERY_AVAILABLE = True
except ImportError:
    REAL_DISCOVERY_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass 
class PotentialLead:
    """A potential business lead identified by the system."""
    company_name: str
    domain: str
    industry: str
    estimated_size: str
    contact_info: Dict[str, Any]
    match_score: float
    match_reasons: List[str]
    template_matches: List[str]
    recommended_approach: str
    priority_level: str
    technical_fit_score: float
    business_potential_score: float
    contact_accessibility_score: float
    next_steps: List[str]
    data_sources: List[str]
    confidence_level: float
    last_updated: datetime


@dataclass
class LeadRecommendation:
    """Recommendation for engaging with a lead."""
    lead: PotentialLead
    outreach_strategy: Dict[str, Any]
    timing_recommendation: str
    personalization_tips: List[str]
    technical_talking_points: List[str]
    business_value_propositions: List[str]
    meeting_agenda_template: str
    follow_up_sequence: List[str]


class LeadGenerator:
    """Generates qualified leads based on learned interaction patterns."""
    
    def __init__(self):
        self.profiler = CompanyProfiler()
        self.company_templates = {}
        self.generated_leads = []
        
        # Data sources for lead discovery
        self.data_sources = {
            'crunchbase': 'https://api.crunchbase.com/api/v4/',
            'builtwith': 'https://api.builtwith.com/v20/',
            'linkedin': 'LinkedIn Sales Navigator (manual)',
            'github': 'GitHub organization search',
            'product_hunt': 'Product Hunt API',
            'indie_hackers': 'Indie Hackers community',
            'angel_list': 'AngelList (now Wellfound)',
            'y_combinator': 'Y Combinator directory'
        }
        
        # Simulated lead database (in production, this would be real data)
        self.simulated_leads_db = self._create_simulated_leads()
    
    async def generate_leads(self, templates: List[CompanyTemplate], target_count: int = 10, filters: Optional[Dict[str, str]] = None) -> List[PotentialLead]:
        """Generate potential leads based on company templates and scoring criteria."""
        logger.info(f"Generating {target_count} leads from {len(templates)} templates")
        
        # Always try real startup discovery first when available
        if REAL_DISCOVERY_AVAILABLE:
            try:
                logger.info("🔍 Using real startup discovery system")
                return await self._generate_real_startup_leads(target_count, filters)
            except Exception as e:
                logger.warning(f"Real discovery failed, falling back to template-based generation: {e}")
        
        if not templates:
            logger.warning("No templates provided for lead generation - using defaults")
            # Generate default leads using simulated database
            if self.simulated_leads_db:
                return await self._generate_default_leads(target_count)
            else:
                logger.error("No templates and no simulated database available")
                return []
        
        # Main logic for when templates are provided (fallback)
        all_leads = []
        leads_per_template = max(1, target_count // len(templates))
        
        for template in templates:
            template_leads = await self._generate_leads_for_template(template, leads_per_template)
            all_leads.extend(template_leads)
        
        # Score and rank all leads
        templates_dict = {template.template_name: template for template in templates}
        final_leads = self._score_and_rank_leads(all_leads, templates_dict)
        
        # Apply filters if provided
        if filters:
            final_leads = self._apply_filters(final_leads, filters)
        
        # Store generated leads for statistics
        self.generated_leads = final_leads[:target_count]
        
        return final_leads[:target_count]
    
    async def _generate_leads_for_template(self, template: CompanyTemplate, count: int) -> List[PotentialLead]:
        """Generate leads that match a specific company template."""
        
        leads = []
        
        try:
            # Search different data sources
            industry_leads = await self._search_by_industry(template, count // 3)
            tech_stack_leads = await self._search_by_tech_stack(template, count // 3)
            size_leads = await self._search_by_company_size(template, count // 3)
            
            # Combine and deduplicate
            all_leads = industry_leads + tech_stack_leads + size_leads
            
            # Remove duplicates by domain
            seen_domains = set()
            unique_leads = []
            for lead in all_leads:
                if lead.domain not in seen_domains:
                    unique_leads.append(lead)
                    seen_domains.add(lead.domain)
            
            leads = unique_leads[:count]
            
        except Exception as e:
            logger.error(f"Error generating leads for template {template.template_name}: {e}")
        
        return leads
    
    async def _search_by_industry(self, template: CompanyTemplate, count: int) -> List[PotentialLead]:
        """Search for companies in similar industries."""
        
        industry = template.industry_characteristics.get('primary_industry', 'Technology')
        focus_areas = template.industry_characteristics.get('focus_areas', [])
        
        # In production, this would query real APIs
        # For now, filter simulated data
        industry_matches = []
        
        for lead_data in self.simulated_leads_db:
            if (industry.lower() in lead_data['industry'].lower() or 
                any(area.lower() in lead_data['description'].lower() for area in focus_areas)):
                
                lead = self._create_potential_lead_from_data(lead_data, template, 'industry_match')
                if lead:
                    industry_matches.append(lead)
        
        return industry_matches[:count]
    
    async def _search_by_tech_stack(self, template: CompanyTemplate, count: int) -> List[PotentialLead]:
        """Search for companies using similar technology stacks."""
        
        tech_requirements = template.technical_requirements
        
        tech_matches = []
        
        for lead_data in self.simulated_leads_db:
            tech_overlap = len([tech for tech in tech_requirements 
                              if tech.lower() in lead_data['tech_stack'].lower()])
            
            if tech_overlap >= 2:  # At least 2 technology overlaps
                lead = self._create_potential_lead_from_data(lead_data, template, 'tech_stack_match')
                if lead:
                    tech_matches.append(lead)
        
        return tech_matches[:count]
    
    async def _search_by_company_size(self, template: CompanyTemplate, count: int) -> List[PotentialLead]:
        """Search for companies of appropriate size."""
        
        target_size = template.company_size_range
        
        size_matches = []
        
        for lead_data in self.simulated_leads_db:
            if target_size.lower() in lead_data['size'].lower():
                lead = self._create_potential_lead_from_data(lead_data, template, 'size_match')
                if lead:
                    size_matches.append(lead)
        
        return size_matches[:count]
    
    def _create_potential_lead_from_data(self, lead_data: Dict[str, Any], 
                                       template: CompanyTemplate, match_type: str) -> Optional[PotentialLead]:
        """Create a PotentialLead from raw data."""
        
        try:
            # Calculate scores based on template match
            technical_fit = self._calculate_technical_fit(lead_data, template)
            business_potential = self._calculate_business_potential(lead_data, template)
            contact_accessibility = self._calculate_contact_accessibility(lead_data)
            
            # Overall match score
            match_score = self._calculate_overall_match_score(
                technical_fit, business_potential, contact_accessibility, template
            )
            
            # Determine priority level
            priority_level = self._determine_priority_level(match_score)
            
            # Generate match reasons
            match_reasons = self._generate_match_reasons(lead_data, template, match_type)
            
            # Recommended approach
            recommended_approach = self._determine_recommended_approach(lead_data, template)
            
            # Next steps
            next_steps = self._generate_next_steps(lead_data, template)
            
            lead = PotentialLead(
                company_name=lead_data['name'],
                domain=lead_data['domain'],
                industry=lead_data['industry'],
                estimated_size=lead_data['size'],
                contact_info=lead_data.get('contact_info', {}),
                match_score=match_score,
                match_reasons=match_reasons,
                template_matches=[template.template_name],
                recommended_approach=recommended_approach,
                priority_level=priority_level,
                technical_fit_score=technical_fit,
                business_potential_score=business_potential,
                contact_accessibility_score=contact_accessibility,
                next_steps=next_steps,
                data_sources=['simulated_database'],  # Would be real sources in production
                confidence_level=min(match_score + 0.1, 0.9),
                last_updated=datetime.now()
            )
            
            return lead
            
        except Exception as e:
            logger.error(f"Error creating lead from data: {e}")
            return None
    
    def _calculate_technical_fit(self, lead_data: Dict[str, Any], template: CompanyTemplate) -> float:
        """Calculate how well the lead's tech needs match our capabilities."""
        
        our_capabilities = template.technical_requirements
        their_tech_stack = lead_data.get('tech_stack', '').lower()
        their_needs = lead_data.get('description', '').lower()
        
        # Count technology overlaps
        tech_matches = 0
        for tech in our_capabilities:
            if tech.lower() in their_tech_stack or tech.lower() in their_needs:
                tech_matches += 1
        
        # Calculate fit score
        fit_score = min(tech_matches / max(len(our_capabilities), 1), 1.0)
        
        # Bonus for exact industry match
        if template.industry_characteristics.get('primary_industry', '').lower() in lead_data.get('industry', '').lower():
            fit_score += 0.2
        
        return min(fit_score, 1.0)
    
    def _calculate_business_potential(self, lead_data: Dict[str, Any], template: CompanyTemplate) -> float:
        """Calculate the business potential of this lead."""
        
        potential_score = 0.0
        
        # Company size scoring
        size = lead_data.get('size', '').lower()
        if 'large' in size:
            potential_score += 0.3
        elif 'medium' in size:
            potential_score += 0.4
        elif 'small' in size:
            potential_score += 0.2
        
        # Industry scoring
        high_potential_industries = ['saas', 'fintech', 'healthtech', 'ecommerce']
        if any(industry in lead_data.get('industry', '').lower() for industry in high_potential_industries):
            potential_score += 0.3
        
        # Growth indicators
        growth_indicators = ['series a', 'series b', 'funding', 'growth', 'expanding']
        if any(indicator in lead_data.get('description', '').lower() for indicator in growth_indicators):
            potential_score += 0.2
        
        # Technology modernization needs
        modernization_needs = ['legacy', 'upgrade', 'modernization', 'digital transformation']
        if any(need in lead_data.get('description', '').lower() for need in modernization_needs):
            potential_score += 0.2
        
        return min(potential_score, 1.0)
    
    def _calculate_contact_accessibility(self, lead_data: Dict[str, Any]) -> float:
        """Calculate how accessible decision makers are likely to be."""
        
        accessibility_score = 0.5  # Base score
        
        contact_info = lead_data.get('contact_info', {})
        
        # Check for direct contact information
        if contact_info.get('email'):
            accessibility_score += 0.2
        if contact_info.get('phone'):
            accessibility_score += 0.1
        if contact_info.get('linkedin'):
            accessibility_score += 0.1
        
        # Company size affects accessibility
        size = lead_data.get('size', '').lower()
        if 'small' in size:
            accessibility_score += 0.2  # Easier to reach decision makers
        elif 'medium' in size:
            accessibility_score += 0.1
        # Large companies are harder to reach (no bonus)
        
        return min(accessibility_score, 1.0)
    
    def _calculate_overall_match_score(self, technical_fit: float, business_potential: float, 
                                     contact_accessibility: float, template: CompanyTemplate) -> float:
        """Calculate overall match score using template weights."""
        
        weights = template.matching_score_weights
        
        # Use template weights if available, otherwise defaults
        tech_weight = weights.get('technical_alignment', 0.30)
        business_weight = weights.get('industry_match', 0.40)  
        contact_weight = weights.get('decision_maker_accessibility', 0.30)
        
        # Normalize weights
        total_weight = tech_weight + business_weight + contact_weight
        if total_weight > 0:
            tech_weight /= total_weight
            business_weight /= total_weight
            contact_weight /= total_weight
        
        overall_score = (
            technical_fit * tech_weight +
            business_potential * business_weight +
            contact_accessibility * contact_weight
        )
        
        return min(overall_score, 1.0)
    
    def _determine_priority_level(self, match_score: float) -> str:
        """Determine priority level based on match score."""
        if match_score >= 0.8:
            return 'high'
        elif match_score >= 0.6:
            return 'medium'
        else:
            return 'low'
    
    def _generate_match_reasons(self, lead_data: Dict[str, Any], template: CompanyTemplate, match_type: str) -> List[str]:
        """Generate human-readable reasons for why this lead matches."""
        
        reasons = []
        
        # Industry match
        if template.industry_characteristics.get('primary_industry', '').lower() in lead_data.get('industry', '').lower():
            reasons.append(f"Industry alignment: {lead_data.get('industry')}")
        
        # Technology stack overlap
        tech_overlap = []
        for tech in template.technical_requirements:
            if tech.lower() in lead_data.get('tech_stack', '').lower():
                tech_overlap.append(tech)
        
        if tech_overlap:
            reasons.append(f"Technology stack match: {', '.join(tech_overlap[:3])}")
        
        # Company size fit
        if template.company_size_range.lower() in lead_data.get('size', '').lower():
            reasons.append(f"Appropriate company size: {lead_data.get('size')}")
        
        # Business model alignment
        for model in template.business_model_indicators:
            if model.lower() in lead_data.get('description', '').lower():
                reasons.append(f"Business model fit: {model}")
                break
        
        # Project type match
        for project_type in template.project_types[:2]:  # Top 2 project types
            if any(keyword in lead_data.get('description', '').lower() 
                   for keyword in project_type.lower().split()):
                reasons.append(f"Project type alignment: {project_type}")
                break
        
        return reasons[:4]  # Limit to top 4 reasons
    
    def _determine_recommended_approach(self, lead_data: Dict[str, Any], template: CompanyTemplate) -> str:
        """Determine the recommended outreach approach."""
        
        # Analyze company characteristics to recommend approach
        size = lead_data.get('size', '').lower()
        industry = lead_data.get('industry', '').lower()
        
        if 'startup' in size or 'small' in size:
            return "Direct founder/CEO outreach via LinkedIn or email"
        elif 'large' in size or 'enterprise' in size:
            return "Multi-touch approach: LinkedIn + warm introduction + email sequence"
        elif any(tech_term in industry for tech_term in ['saas', 'software', 'tech']):
            return "Technical value-first approach via engineering team contacts"
        else:
            return "Business value-focused outreach via business development contacts"
    
    def _generate_next_steps(self, lead_data: Dict[str, Any], template: CompanyTemplate) -> List[str]:
        """Generate recommended next steps for this lead."""
        
        steps = []
        
        # Research step
        steps.append(f"Research {lead_data['name']}'s recent developments and tech stack")
        
        # Find contacts
        if not lead_data.get('contact_info', {}).get('email'):
            steps.append("Find key decision maker contacts via LinkedIn or company website")
        
        # Personalization
        steps.append("Create personalized outreach message highlighting relevant experience")
        
        # Value proposition
        business_models = template.business_model_indicators
        if business_models:
            steps.append(f"Prepare {business_models[0]} value proposition and case studies")
        
        # Follow-up sequence
        steps.append("Set up 3-touch follow-up sequence (LinkedIn, email, phone)")
        
        return steps
    
    def _score_and_rank_leads(self, leads: List[PotentialLead], templates: Dict[str, CompanyTemplate]) -> List[PotentialLead]:
        """Score and rank leads by their overall potential."""
        
        # Sort by match score (descending)
        ranked_leads = sorted(leads, key=lambda lead: lead.match_score, reverse=True)
        
        return ranked_leads
    
    def _apply_filters(self, leads: List[PotentialLead], filters: Dict[str, Any]) -> List[PotentialLead]:
        """Apply user-specified filters to leads."""
        
        filtered_leads = leads
        
        # Filter by industry
        if 'industry' in filters and filters['industry']:
            filtered_leads = [lead for lead in filtered_leads 
                            if filters['industry'].lower() in lead.industry.lower()]
        
        # Filter by company size
        if 'company_size' in filters and filters['company_size']:
            filtered_leads = [lead for lead in filtered_leads 
                            if filters['company_size'].lower() in lead.estimated_size.lower()]
        
        # Filter by minimum match score
        if 'min_match_score' in filters:
            min_score = float(filters['min_match_score'])
            filtered_leads = [lead for lead in filtered_leads if lead.match_score >= min_score]
        
        # Filter by priority level
        if 'priority_level' in filters and filters['priority_level']:
            filtered_leads = [lead for lead in filtered_leads 
                            if lead.priority_level == filters['priority_level']]
        
        return filtered_leads
    
    async def generate_lead_recommendations(self, leads: List[PotentialLead]) -> List[LeadRecommendation]:
        """Generate detailed recommendations for engaging with leads."""
        
        recommendations = []
        
        for lead in leads[:10]:  # Generate recommendations for top 10 leads
            try:
                recommendation = await self._create_lead_recommendation(lead)
                recommendations.append(recommendation)
            except Exception as e:
                logger.error(f"Error creating recommendation for {lead.company_name}: {e}")
        
        return recommendations
    
    async def _create_lead_recommendation(self, lead: PotentialLead) -> LeadRecommendation:
        """Create a detailed recommendation for engaging with a specific lead."""
        
        # Find matching template for detailed guidance
        template = None
        if self.company_templates and lead.template_matches:
            template_name = lead.template_matches[0]
            template = self.company_templates.get(template_name)
        
        # Generate outreach strategy
        outreach_strategy = self._create_outreach_strategy(lead, template)
        
        # Timing recommendation
        timing_recommendation = self._determine_optimal_timing(lead, template)
        
        # Personalization tips
        personalization_tips = self._generate_personalization_tips(lead, template)
        
        # Technical talking points
        technical_talking_points = self._generate_technical_talking_points(lead, template)
        
        # Business value propositions
        business_value_props = self._generate_business_value_propositions(lead, template)
        
        # Meeting agenda template
        meeting_agenda = self._create_meeting_agenda_template(lead, template)
        
        # Follow-up sequence
        follow_up_sequence = self._create_follow_up_sequence(lead, template)
        
        recommendation = LeadRecommendation(
            lead=lead,
            outreach_strategy=outreach_strategy,
            timing_recommendation=timing_recommendation,
            personalization_tips=personalization_tips,
            technical_talking_points=technical_talking_points,
            business_value_propositions=business_value_props,
            meeting_agenda_template=meeting_agenda,
            follow_up_sequence=follow_up_sequence
        )
        
        return recommendation
    
    def _create_outreach_strategy(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> Dict[str, Any]:
        """Create a customized outreach strategy."""
        
        strategy = {
            'primary_channel': 'linkedin',
            'message_tone': 'professional',
            'value_first_approach': True,
            'follow_up_cadence': '3-5-7 day intervals'
        }
        
        # Customize based on company size
        if 'small' in lead.estimated_size.lower() or 'startup' in lead.estimated_size.lower():
            strategy['primary_channel'] = 'email'
            strategy['message_tone'] = 'friendly_professional'
            strategy['direct_founder_approach'] = True
        elif 'large' in lead.estimated_size.lower():
            strategy['multi_touch_approach'] = True
            strategy['warm_introduction_preferred'] = True
        
        # Customize based on industry
        if 'technology' in lead.industry.lower() or 'software' in lead.industry.lower():
            strategy['technical_credibility_important'] = True
            strategy['github_portfolio_reference'] = True
        
        return strategy
    
    def _determine_optimal_timing(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> str:
        """Determine optimal timing for outreach."""
        
        # Default business timing
        timing = "Tuesday-Thursday, 10 AM - 4 PM in their timezone"
        
        # Adjust for company type
        if 'startup' in lead.estimated_size.lower():
            timing = "Flexible timing - startups often work non-traditional hours"
        elif 'enterprise' in lead.estimated_size.lower():
            timing = "Strict business hours - Monday-Friday, 9 AM - 5 PM"
        
        return timing
    
    def _generate_personalization_tips(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> List[str]:
        """Generate personalization tips for outreach."""
        
        tips = [
            f"Reference {lead.company_name}'s industry focus on {lead.industry}",
            "Mention specific technology alignment from their stack",
            "Reference similar successful projects in their industry"
        ]
        
        # Add template-specific tips
        if template:
            for success_indicator in template.success_indicators:
                if success_indicator == 'technical_alignment':
                    tips.append("Highlight technical expertise and past integration work")
                elif success_indicator == 'meeting_engagement':
                    tips.append("Offer a brief technical demo or strategy session")
        
        return tips[:4]
    
    def _generate_technical_talking_points(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> List[str]:
        """Generate technical talking points."""
        
        talking_points = []
        
        # Based on lead's tech stack
        if 'python' in lead.domain or template and 'python' in template.technical_requirements:
            talking_points.append("Python development expertise and scalable architecture")
        
        if 'api' in str(lead.match_reasons).lower():
            talking_points.append("API integration and microservices architecture")
        
        if 'cloud' in lead.industry.lower():
            talking_points.append("Cloud-native development and DevOps practices")
        
        # Default technical points
        talking_points.extend([
            "Scalable system design and performance optimization",
            "Modern development practices and testing methodologies",
            "Security best practices and compliance considerations"
        ])
        
        return talking_points[:5]
    
    def _generate_business_value_propositions(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> List[str]:
        """Generate business value propositions."""
        
        value_props = []
        
        # Size-based value props
        if 'small' in lead.estimated_size.lower():
            value_props.append("Cost-effective development with startup-friendly pricing")
            value_props.append("Rapid MVP development and iterative improvement")
        elif 'large' in lead.estimated_size.lower():
            value_props.append("Enterprise-grade security and scalability")
            value_props.append("Integration with existing enterprise systems")
        
        # Industry-specific value props
        if 'fintech' in lead.industry.lower():
            value_props.append("Financial services compliance and security expertise")
        elif 'healthcare' in lead.industry.lower():
            value_props.append("HIPAA compliance and healthcare data security")
        
        # Generic value props
        value_props.extend([
            "Faster time-to-market with experienced development team",
            "Reduced technical debt and improved code quality"
        ])
        
        return value_props[:4]
    
    def _create_meeting_agenda_template(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> str:
        """Create a meeting agenda template."""
        
        agenda = f"""
        Meeting Agenda: {lead.company_name} Technical Discussion
        
        1. Introductions and Company Overview (10 min)
           - Your background and technical expertise
           - Brief overview of relevant past projects
        
        2. {lead.company_name} Current Challenges (15 min)
           - Current technology stack and pain points
           - Growth objectives and technical requirements
        
        3. Technical Alignment Discussion (15 min)
           - Relevant experience with {lead.industry} solutions
           - Technology recommendations and best practices
        
        4. Potential Collaboration Areas (10 min)
           - Specific ways we can help achieve their goals
           - Timeline and approach recommendations
        
        5. Next Steps (5 min)
           - Follow-up items and timeline
           - Technical proposal or discovery session
        
        Total Duration: 45-60 minutes
        """
        
        return agenda.strip()
    
    def _create_follow_up_sequence(self, lead: PotentialLead, template: Optional[CompanyTemplate]) -> List[str]:
        """Create a follow-up sequence."""
        
        sequence = [
            "Day 1: Initial outreach with personalized value proposition",
            "Day 4: Follow-up with relevant case study or technical insight",
            "Day 8: Share industry report or technical article that adds value",
            "Day 14: Final follow-up with different angle (business vs technical)",
            "Month 2: Quarterly check-in with company updates or new offerings"
        ]
        
        return sequence
    
    async def _generate_default_leads(self, count: int) -> List[PotentialLead]:
        """Generate default leads when no templates are available."""
        
        # Use a subset of simulated data as default leads
        default_leads = []
        
        for lead_data in self.simulated_leads_db[:count]:
            lead = PotentialLead(
                company_name=lead_data['name'],
                domain=lead_data['domain'],
                industry=lead_data['industry'],
                estimated_size=lead_data['size'],
                contact_info=lead_data.get('contact_info', {}),
                match_score=0.6,  # Default score
                match_reasons=["Technology company", "Appropriate size"],
                template_matches=["Default Template"],
                recommended_approach="Research and personalized outreach",
                priority_level='medium',
                technical_fit_score=0.6,
                business_potential_score=0.6,
                contact_accessibility_score=0.5,
                next_steps=["Research company", "Find contacts", "Create outreach message"],
                data_sources=['default_database'],
                confidence_level=0.6,
                last_updated=datetime.now()
            )
            default_leads.append(lead)
        
        return default_leads
    
    async def _generate_real_startup_leads(self, target_count: int, filters: Optional[Dict[str, str]] = None) -> List[PotentialLead]:
        """Generate leads by discovering real startups from various sources."""
        logger.info(f"🚀 Discovering {target_count} real startup leads")
        
        # Create search preferences from any existing learned patterns
        search_preferences = {
            'high_value_keywords': ['saas', 'automation', 'api', 'ai', 'fintech', 'healthtech', 'no-code'],
            'preferred_industries': ['Technology', 'Software Development', 'SaaS'],
            'preferred_company_sizes': ['Early Stage', 'Small', 'Startup']
        }
        
        # Apply any provided filters
        if filters:
            if filters.get('industry'):
                search_preferences['high_value_keywords'].append(filters['industry'].lower())
        
        # Discover real startups
        real_leads_data = await discover_real_startups(search_preferences, target_count)
        
        # Convert to PotentialLead objects
        real_leads = []
        for lead_data in real_leads_data:
            try:
                potential_lead = PotentialLead(
                    company_name=lead_data['company_name'],
                    domain=lead_data['domain'],
                    industry=lead_data.get('industry', 'Technology'),
                    estimated_size=lead_data.get('estimated_size', 'Early Stage'),
                    contact_info=lead_data.get('contact_info', {}),
                    match_score=float(lead_data['match_score']),
                    match_reasons=lead_data.get('match_reasons', []),
                    template_matches=lead_data.get('template_matches', ['real-startup']),
                    recommended_approach=lead_data.get('recommended_approach', 'Email outreach'),
                    priority_level=lead_data.get('priority_level', 'medium'),
                    technical_fit_score=float(lead_data.get('technical_fit_score', 0.7)),
                    business_potential_score=float(lead_data.get('business_potential_score', 0.6)),
                    contact_accessibility_score=float(lead_data.get('contact_accessibility_score', 0.5)),
                    next_steps=lead_data.get('next_steps', ['Research company', 'Prepare outreach']),
                    data_sources=lead_data.get('data_sources', ['Real Discovery']),
                    confidence_level=float(lead_data.get('confidence_level', 0.7)),
                    last_updated=datetime.now()
                )
                real_leads.append(potential_lead)
                
            except Exception as e:
                logger.warning(f"Error converting real lead {lead_data.get('company_name', 'Unknown')}: {e}")
                continue
        
        # Store generated leads for statistics
        self.generated_leads = real_leads
        
        logger.info(f"✅ Generated {len(real_leads)} real startup leads")
        return real_leads
    
    def _create_simulated_leads(self) -> List[Dict[str, Any]]:
        """Create simulated lead database for demonstration."""
        
        simulated_leads = [
            {
                'name': 'TechFlow Solutions',
                'domain': 'techflow.com',
                'industry': 'SaaS Platform Development',
                'size': 'Medium (50-200 employees)',
                'description': 'API integration platform for enterprise workflow automation',
                'tech_stack': 'Python, React, PostgreSQL, AWS, Docker',
                'contact_info': {'email': 'info@techflow.com', 'linkedin': '/company/techflow'}
            },
            {
                'name': 'DataBridge Analytics',
                'domain': 'databridge.io',
                'industry': 'Data Analytics SaaS',
                'size': 'Small (10-50 employees)',
                'description': 'Real-time analytics dashboard for e-commerce businesses',
                'tech_stack': 'JavaScript, Node.js, MongoDB, React, Redis',
                'contact_info': {'email': 'hello@databridge.io', 'phone': '+1-555-0123'}
            },
            {
                'name': 'CloudNative Systems',
                'domain': 'cloudnative.tech',
                'industry': 'Cloud Infrastructure',
                'size': 'Large (200+ employees)',
                'description': 'Kubernetes-based platform for legacy system modernization',
                'tech_stack': 'Python, Kubernetes, Docker, PostgreSQL, GraphQL',
                'contact_info': {'linkedin': '/company/cloudnative-systems'}
            },
            {
                'name': 'FinTech Innovations',
                'domain': 'fintech-innov.com',
                'industry': 'Financial Technology',
                'size': 'Medium (50-200 employees)',
                'description': 'Mobile payment processing and digital wallet solutions',
                'tech_stack': 'Java, Spring Boot, MySQL, React Native, AWS',
                'contact_info': {'email': 'partnerships@fintech-innov.com'}
            },
            {
                'name': 'HealthTech Connect',
                'domain': 'healthtech.connect',
                'industry': 'Healthcare Technology',
                'size': 'Small (10-50 employees)',
                'description': 'Telemedicine platform with HIPAA-compliant video conferencing',
                'tech_stack': 'Python, Django, PostgreSQL, WebRTC, AWS',
                'contact_info': {'email': 'info@healthtech.connect', 'linkedin': '/company/healthtech-connect'}
            },
            {
                'name': 'RetailFlow Pro',
                'domain': 'retailflow.pro',
                'industry': 'E-commerce Technology',
                'size': 'Medium (50-200 employees)',
                'description': 'Inventory management and POS system for retail chains',
                'tech_stack': 'PHP, Laravel, MySQL, Vue.js, Redis',
                'contact_info': {'phone': '+1-555-0456', 'email': 'sales@retailflow.pro'}
            },
            {
                'name': 'AI Automation Hub',
                'domain': 'aiautomation.hub',
                'industry': 'Artificial Intelligence',
                'size': 'Small (10-50 employees)',
                'description': 'Custom AI solutions for business process automation',
                'tech_stack': 'Python, TensorFlow, FastAPI, PostgreSQL, Docker',
                'contact_info': {'email': 'contact@aiautomation.hub'}
            },
            {
                'name': 'DevTools United',
                'domain': 'devtools.united',
                'industry': 'Developer Tools',
                'size': 'Small (10-50 employees)',
                'description': 'Code quality and security scanning tools for development teams',
                'tech_stack': 'Go, React, PostgreSQL, Kubernetes, GraphQL',
                'contact_info': {'email': 'hello@devtools.united', 'linkedin': '/company/devtools-united'}
            },
            {
                'name': 'LogisticsTech Corp',
                'domain': 'logisticstech.corp',
                'industry': 'Supply Chain Technology',
                'size': 'Large (200+ employees)',
                'description': 'Supply chain optimization and tracking platform',
                'tech_stack': 'Java, Spring, Oracle, React, Microservices',
                'contact_info': {'email': 'partnerships@logisticstech.corp'}
            },
            {
                'name': 'EduPlatform Next',
                'domain': 'eduplatform.next',
                'industry': 'Education Technology',
                'size': 'Medium (50-200 employees)',
                'description': 'Online learning management system with interactive features',
                'tech_stack': 'Python, Django, PostgreSQL, React, Redis',
                'contact_info': {'email': 'info@eduplatform.next', 'phone': '+1-555-0789'}
            },
            {
                'name': 'StartupBoost Labs',
                'domain': 'startupboost.labs',
                'industry': 'Startup Acceleration Platform',
                'size': 'Small (10-50 employees)',
                'description': 'Platform connecting startups with mentors and investors',
                'tech_stack': 'JavaScript, Node.js, MongoDB, React, Socket.io',
                'contact_info': {'email': 'contact@startupboost.labs', 'linkedin': '/company/startupboost-labs'}
            },
            {
                'name': 'GreenTech Solutions',
                'domain': 'greentech.solutions',
                'industry': 'Environmental Technology',
                'size': 'Medium (50-200 employees)',
                'description': 'Carbon footprint tracking and sustainability reporting tools',
                'tech_stack': 'Python, FastAPI, PostgreSQL, Vue.js, Docker',
                'contact_info': {'email': 'partnerships@greentech.solutions'}
            },
            {
                'name': 'PropertyTech Innovations',
                'domain': 'proptech.innovations',
                'industry': 'Real Estate Technology',
                'size': 'Small (10-50 employees)',
                'description': 'Digital property management and tenant communication platform',
                'tech_stack': 'Ruby, Rails, PostgreSQL, React Native, AWS',
                'contact_info': {'email': 'hello@proptech.innovations', 'phone': '+1-555-0321'}
            },
            {
                'name': 'Manufacturing Intelligence',
                'domain': 'mfg-intelligence.com',
                'industry': 'Industrial IoT',
                'size': 'Large (200+ employees)',
                'description': 'IoT sensors and analytics for smart manufacturing',
                'tech_stack': 'C++, Python, InfluxDB, React, MQTT',
                'contact_info': {'email': 'enterprise@mfg-intelligence.com'}
            },
            {
                'name': 'SocialMedia Analytics Pro',
                'domain': 'socialmedia-analytics.pro',
                'industry': 'Marketing Technology',
                'size': 'Medium (50-200 employees)',
                'description': 'Social media monitoring and sentiment analysis platform',
                'tech_stack': 'Python, Elasticsearch, React, Redis, Apache Kafka',
                'contact_info': {'email': 'sales@socialmedia-analytics.pro', 'linkedin': '/company/socialmedia-analytics-pro'}
            }
        ]
        
        return simulated_leads
    
    async def save_generated_leads(self, leads: List[PotentialLead]) -> None:
        """Save generated leads to file for future reference."""
        try:
            if not leads:
                logger.warning("No leads to save")
                return
            
            # Convert leads to serializable format
            serializable_leads = []
            for lead in leads:
                lead_dict = asdict(lead)
                lead_dict['last_updated'] = lead.last_updated.isoformat()
                serializable_leads.append(lead_dict)
            
            # Get project root (two levels up from processors/)
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            
            # Save to JSON file
            leads_file = data_dir / "generated_leads.json"
            with open(leads_file, 'w') as f:
                json.dump(serializable_leads, f, indent=2, default=str)
            
            logger.info(f"Saved {len(leads)} generated leads")
            
        except Exception as e:
            logger.error(f"Error saving generated leads: {e}")
    
    def get_lead_statistics(self) -> Dict[str, Any]:
        """Get statistics about generated leads."""
        
        if not self.generated_leads:
            return {'total_leads': 0}
        
        # Calculate statistics
        total_leads = len(self.generated_leads)
        high_priority = len([lead for lead in self.generated_leads if lead.priority_level == 'high'])
        medium_priority = len([lead for lead in self.generated_leads if lead.priority_level == 'medium'])
        low_priority = len([lead for lead in self.generated_leads if lead.priority_level == 'low'])
        
        avg_match_score = sum(lead.match_score for lead in self.generated_leads) / total_leads
        
        # Industry distribution
        industries = [lead.industry for lead in self.generated_leads]
        industry_counts = {industry: industries.count(industry) for industry in set(industries)}
        
        # Size distribution
        sizes = [lead.estimated_size for lead in self.generated_leads]
        size_counts = {size: sizes.count(size) for size in set(sizes)}
        
        return {
            'total_leads': total_leads,
            'priority_distribution': {
                'high': high_priority,
                'medium': medium_priority,
                'low': low_priority
            },
            'average_match_score': round(avg_match_score, 2),
            'industry_distribution': industry_counts,
            'size_distribution': size_counts,
            'top_leads': [
                {
                    'name': lead.company_name,
                    'score': lead.match_score,
                    'priority': lead.priority_level
                } 
                for lead in sorted(self.generated_leads, key=lambda x: x.match_score, reverse=True)[:5]
            ]
        }