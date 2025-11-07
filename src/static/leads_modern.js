/**
 * Modern Lead Manager for Sidebar Dashboard
 * Uses modal popovers for detailed views
 */

class LeadManager {
    constructor() {
        this.leads = [];
        this.statistics = {};
    }
    
    async init() {
        await this.loadLeads();
    }
    
    async loadLeads() {
        try {
            const response = await fetch('/api/leads');
            if (response.ok) {
                const data = await response.json();
                this.leads = data.leads || [];
                this.statistics = data.statistics || {};
                
                this.updateCounts();
                this.renderLeads();
            }
        } catch (error) {
            console.error('Error loading leads:', error);
        }
    }
    
    updateCounts() {
        // Update sidebar badge
        const badge = document.getElementById('leads-count');
        if (badge) {
            badge.textContent = this.leads.length;
        }
        
        // Update stat card
        const stat = document.getElementById('stat-leads');
        if (stat) {
            stat.textContent = this.leads.length;
        }
    }
    
    renderLeads() {
        const grid = document.getElementById('leads-grid');
        if (!grid) return;
        
        if (this.leads.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🎯</div>
                    <h3 class="text-xl font-semibold mb-2">No leads yet</h3>
                    <p class="text-gray-400 mb-4">Generate your first batch of startup leads</p>
                    <button onclick="leadManager.generateLeads()" 
                            class="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-semibold">
                        ✨ Generate Leads
                    </button>
                </div>
            `;
            return;
        }
        
        const html = this.leads.map(lead => this.renderLeadCard(lead)).join('');
        grid.innerHTML = html;
    }
    
    renderLeadCard(lead) {
        const scoreColor = lead.lead_score >= 80 ? 'text-green-400' : 
                          lead.lead_score >= 60 ? 'text-yellow-400' : 'text-gray-400';
        
        const dataSourceBadges = (lead.data_sources || []).map(source => 
            `<span class="text-xs bg-gray-700 px-2 py-1 rounded">${source}</span>`
        ).join('');
        
        return `
            <div class="dashboard-card bg-gray-800 rounded-xl p-6 border border-gray-700 cursor-pointer"
                 onclick="leadManager.showLeadDetail('${this.escapeHtml(lead.company_name)}')">
                
                <div class="flex justify-between items-start mb-3">
                    <h3 class="text-lg font-bold text-white">${this.escapeHtml(lead.company_name)}</h3>
                    <span class="text-2xl font-bold ${scoreColor}">${lead.lead_score}</span>
                </div>
                
                ${lead.industry ? `<p class="text-sm text-purple-400 mb-2">🏢 ${this.escapeHtml(lead.industry)}</p>` : ''}
                ${lead.website ? `<p class="text-sm text-blue-400 mb-2">🌐 ${this.escapeHtml(lead.website)}</p>` : ''}
                ${lead.location ? `<p class="text-sm text-gray-400 mb-2">📍 ${this.escapeHtml(lead.location)}</p>` : ''}
                
                ${lead.description ? `
                    <p class="text-sm text-gray-300 mb-3 line-clamp-2">${this.escapeHtml(lead.description)}</p>
                ` : ''}
                
                <div class="flex flex-wrap gap-2 mb-3">
                    ${dataSourceBadges}
                </div>
                
                <div class="flex gap-2 pt-3 border-t border-gray-700">
                    <button onclick="event.stopPropagation(); leadManager.likeLead('${this.escapeHtml(lead.company_name)}')" 
                            class="flex-1 bg-green-600 hover:bg-green-700 py-2 rounded text-sm font-medium">
                        👍 Interested
                    </button>
                    <button onclick="event.stopPropagation(); leadManager.dislikeLead('${this.escapeHtml(lead.company_name)}')" 
                            class="flex-1 bg-red-600 hover:bg-red-700 py-2 rounded text-sm font-medium">
                        👎 Not Interested
                    </button>
                </div>
            </div>
        `;
    }
    
    showLeadDetail(companyName) {
        const lead = this.leads.find(l => l.company_name === companyName);
        if (!lead) return;
        
        const content = `
            <div class="space-y-6">
                <!-- Header -->
                <div class="flex justify-between items-start">
                    <div>
                        <h1 class="text-3xl font-bold mb-2">${this.escapeHtml(lead.company_name)}</h1>
                        ${lead.industry ? `<p class="text-purple-400">🏢 ${this.escapeHtml(lead.industry)}</p>` : ''}
                    </div>
                    <div class="text-right">
                        <div class="text-4xl font-bold ${lead.lead_score >= 80 ? 'text-green-400' : 'text-yellow-400'}">
                            ${lead.lead_score}
                        </div>
                        <div class="text-sm text-gray-400">Lead Score</div>
                    </div>
                </div>
                
                <!-- Contact Info -->
                <div class="bg-gray-700 rounded-lg p-4 space-y-2">
                    ${lead.email ? `
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">📧</span>
                            <a href="mailto:${lead.email}" class="text-blue-400 hover:underline">${lead.email}</a>
                        </div>
                    ` : ''}
                    ${lead.website ? `
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">🌐</span>
                            <a href="${lead.website}" target="_blank" class="text-blue-400 hover:underline">${lead.website}</a>
                        </div>
                    ` : ''}
                    ${lead.phone ? `
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">📱</span>
                            <span class="text-white">${lead.phone}</span>
                        </div>
                    ` : ''}
                    ${lead.location ? `
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">📍</span>
                            <span class="text-white">${lead.location}</span>
                        </div>
                    ` : ''}
                </div>
                
                <!-- Description -->
                ${lead.description ? `
                    <div>
                        <h3 class="text-lg font-semibold mb-2">About</h3>
                        <p class="text-gray-300">${this.escapeHtml(lead.description)}</p>
                    </div>
                ` : ''}
                
                <!-- Data Sources -->
                ${lead.data_sources && lead.data_sources.length > 0 ? `
                    <div>
                        <h3 class="text-lg font-semibold mb-2">Data Sources</h3>
                        <div class="flex flex-wrap gap-2">
                            ${lead.data_sources.map(source => 
                                `<span class="bg-gray-700 px-3 py-1 rounded-lg">${source}</span>`
                            ).join('')}
                        </div>
                    </div>
                ` : ''}
                
                <!-- Key Info -->
                <div class="grid grid-cols-2 gap-4">
                    ${lead.employee_count ? `
                        <div class="bg-gray-700 rounded-lg p-4">
                            <div class="text-sm text-gray-400">Team Size</div>
                            <div class="text-xl font-bold">${lead.employee_count}</div>
                        </div>
                    ` : ''}
                    ${lead.funding_stage ? `
                        <div class="bg-gray-700 rounded-lg p-4">
                            <div class="text-sm text-gray-400">Funding Stage</div>
                            <div class="text-xl font-bold">${this.escapeHtml(lead.funding_stage)}</div>
                        </div>
                    ` : ''}
                    ${lead.technologies && lead.technologies.length > 0 ? `
                        <div class="bg-gray-700 rounded-lg p-4 col-span-2">
                            <div class="text-sm text-gray-400 mb-2">Technologies</div>
                            <div class="flex flex-wrap gap-2">
                                ${lead.technologies.map(tech => 
                                    `<span class="bg-blue-600 px-2 py-1 rounded text-sm">${tech}</span>`
                                ).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
                
                <!-- Reasons -->
                ${lead.reasons && lead.reasons.length > 0 ? `
                    <div>
                        <h3 class="text-lg font-semibold mb-2">Why This Lead?</h3>
                        <ul class="space-y-2">
                            ${lead.reasons.map(reason => 
                                `<li class="flex items-start gap-2">
                                    <span class="text-green-400">✓</span>
                                    <span class="text-gray-300">${this.escapeHtml(reason)}</span>
                                </li>`
                            ).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        `;
        
        const actions = [
            {
                label: '👍 Interested',
                class: 'bg-green-600 hover:bg-green-700',
                onclick: `leadManager.likeLead('${this.escapeHtml(companyName)}'); document.querySelector('.modal-backdrop').remove();`
            },
            {
                label: '👎 Not Interested',
                class: 'bg-red-600 hover:bg-red-700',
                onclick: `leadManager.dislikeLead('${this.escapeHtml(companyName)}'); document.querySelector('.modal-backdrop').remove();`
            }
        ];
        
        showModal(this.escapeHtml(lead.company_name), content, actions);
    }
    
    async generateLeads() {
        try {
            const response = await fetch('/api/leads/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_count: 10 })
            });
            
            if (response.ok) {
                const data = await response.json();
                alert(`Generated ${data.total_generated} new leads!`);
                await this.loadLeads();
            } else {
                alert('Failed to generate leads');
            }
        } catch (error) {
            console.error('Error generating leads:', error);
            alert('Error generating leads: ' + error.message);
        }
    }
    
    async likeLead(companyName) {
        try {
            await fetch('/api/leads/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_name: companyName,
                    feedback: 'like'
                })
            });
            console.log('Liked:', companyName);
        } catch (error) {
            console.error('Error liking lead:', error);
        }
    }
    
    async dislikeLead(companyName) {
        try {
            await fetch('/api/leads/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_name: companyName,
                    feedback: 'dislike'
                })
            });
            console.log('Disliked:', companyName);
            
            // Remove from view
            this.leads = this.leads.filter(l => l.company_name !== companyName);
            this.renderLeads();
            this.updateCounts();
        } catch (error) {
            console.error('Error disliking lead:', error);
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
const leadManager = new LeadManager();
