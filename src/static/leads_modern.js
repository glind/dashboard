/**
 * Modern Lead Manager for Sidebar Dashboard
 * Uses modal popovers for detailed views
 */

class LeadManager {
    constructor() {
        this.leads = [];
        this.statistics = {};
        this.filter = 'all'; // all, potential, confirmed
    }
    
    async init() {
        console.log('Initializing leadManager...');
        await this.loadLeads();
        this.updateLastCollectionTime();
        
        // Update time display every minute
        setInterval(() => this.updateLastCollectionTime(), 60000);
        console.log('LeadManager initialized successfully');
    }
    
    async loadLeads() {
        try {
            console.log('Loading leads...');
            const response = await fetch('/api/leads/list?limit=100');
            if (response.ok) {
                const data = await response.json();
                this.leads = data.leads || [];
                console.log(`Loaded ${this.leads.length} leads`, this.leads);
                
                this.updateCounts();
                this.renderLeads();
            } else {
                console.error('Failed to load leads:', response.status);
                this.showNotification('error', 'Failed to load leads');
            }
        } catch (error) {
            console.error('Error loading leads:', error);
            this.showNotification('error', 'Error loading leads: ' + error.message);
        }
    }
    
    updateCounts() {
        // Count potential vs confirmed leads
        const potentialCount = this.leads.filter(l => l.status === 'potential').length;
        const confirmedCount = this.leads.filter(l => l.status !== 'potential').length;
        
        // Update sidebar badge (show potential leads)
        const badge = document.getElementById('leads-count');
        if (badge) {
            badge.textContent = potentialCount;
        }
        
        // Update stat card (show total)
        const stat = document.getElementById('stat-leads');
        if (stat) {
            stat.textContent = this.leads.length;
        }
    }
    
    renderLeads() {
        const grid = document.getElementById('leads-grid');
        if (!grid) {
            console.error('leads-grid element not found!');
            return;
        }
        
        console.log(`Rendering ${this.leads.length} leads with filter: ${this.filter}`);
        
        if (this.leads.length === 0) {
            console.log('No leads to display, showing empty state');
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🎯</div>
                    <h3 class="text-xl font-semibold mb-2">No leads yet</h3>
                    <p class="text-gray-400 mb-4">Collect leads from your emails, calendar, and notes</p>
                    <button onclick="leadManager.generateLeads()" 
                            class="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-semibold">
                        ✨ Collect Leads
                    </button>
                </div>
            `;
            return;
        }
        
        // Filter leads
        let filteredLeads = this.leads;
        if (this.filter === 'potential') {
            filteredLeads = this.leads.filter(l => l.status === 'potential');
        } else if (this.filter === 'confirmed') {
            filteredLeads = this.leads.filter(l => l.status !== 'potential');
        }
        
        console.log(`After filtering: ${filteredLeads.length} leads to display`);
        console.log('First lead sample:', filteredLeads[0]);
        
        // Add filter tabs
        const filterHtml = `
            <div class="col-span-full flex gap-4 mb-4 border-b border-gray-700 pb-4">
                <button onclick="leadManager.setFilter('all')" 
                        class="px-4 py-2 rounded ${this.filter === 'all' ? 'bg-purple-600' : 'bg-gray-700 hover:bg-gray-600'}">
                    All (${this.leads.length})
                </button>
                <button onclick="leadManager.setFilter('potential')" 
                        class="px-4 py-2 rounded ${this.filter === 'potential' ? 'bg-purple-600' : 'bg-gray-700 hover:bg-gray-600'}">
                    Potential (${this.leads.filter(l => l.status === 'potential').length})
                </button>
                <button onclick="leadManager.setFilter('confirmed')" 
                        class="px-4 py-2 rounded ${this.filter === 'confirmed' ? 'bg-purple-600' : 'bg-gray-700 hover:bg-gray-600'}">
                    Confirmed (${this.leads.filter(l => l.status !== 'potential').length})
                </button>
            </div>
        `;
        
        try {
            const leadsHtml = filteredLeads.map((lead, index) => {
                if (index === 0) console.log('Rendering first lead card:', lead);
                return this.renderLeadCard(lead);
            }).join('');
            console.log(`Generated HTML for ${filteredLeads.length} lead cards`);
            grid.innerHTML = filterHtml + leadsHtml;
            console.log('Grid updated successfully');
        } catch (error) {
            console.error('Error rendering lead cards:', error);
            this.showNotification('error', 'Error displaying leads: ' + error.message);
        }
    }
    
    setFilter(filter) {
        this.filter = filter;
        this.renderLeads();
    }
    
    renderLeadCard(lead) {
        const scoreColor = lead.score >= 80 ? 'text-green-400' : 
                          lead.score >= 60 ? 'text-yellow-400' : 'text-gray-400';
        
        // Get lead type emoji and color
        const typeInfo = {
            'customer': { emoji: '💰', color: 'bg-green-600' },
            'investor': { emoji: '💼', color: 'bg-blue-600' },
            'partner': { emoji: '🤝', color: 'bg-purple-600' }
        };
        const type = typeInfo[lead.lead_type] || { emoji: '📧', color: 'bg-gray-600' };
        
        // Status badge
        const isPotential = lead.status === 'potential';
        const statusBadge = isPotential ? 
            '<span class="text-xs bg-yellow-600 px-2 py-1 rounded font-semibold">REVIEW NEEDED</span>' :
            `<span class="text-xs bg-green-600 px-2 py-1 rounded">${lead.status.toUpperCase()}</span>`;
        
        // Parse signals if they're a string
        let signals = lead.signals;
        if (typeof signals === 'string') {
            try {
                signals = JSON.parse(signals.replace(/'/g, '"'));
            } catch {
                signals = signals.split(',').map(s => s.trim());
            }
        }
        signals = signals || [];
        
        return `
            <div class="dashboard-card bg-gray-800 rounded-xl p-6 border ${isPotential ? 'border-yellow-500' : 'border-gray-700'} cursor-pointer hover:border-purple-500 transition-all"
                 onclick="leadManager.showLeadDetail('${lead.lead_id}')">
                
                <div class="flex justify-between items-start mb-3">
                    <div class="flex-1">
                        <div class="flex items-center gap-2 mb-1">
                            <span class="${type.color} px-2 py-1 rounded text-xs">${type.emoji} ${lead.lead_type.toUpperCase()}</span>
                            ${statusBadge}
                        </div>
                        <h3 class="text-lg font-bold text-white">${this.escapeHtml(lead.contact_name || 'Unknown')}</h3>
                        <p class="text-sm text-gray-400">${this.escapeHtml(lead.contact_email)}</p>
                        ${lead.company ? `<p class="text-sm text-purple-400">🏢 ${this.escapeHtml(lead.company)}</p>` : ''}
                    </div>
                    <div class="text-center">
                        <span class="text-2xl font-bold ${scoreColor}">${lead.score}</span>
                        <div class="text-xs text-gray-400">score</div>
                    </div>
                </div>
                
                <div class="flex items-center gap-2 text-xs text-gray-400 mb-3">
                    <span>📊 ${lead.source}</span>
                    <span>•</span>
                    <span>🕒 ${new Date(lead.first_seen).toLocaleDateString()}</span>
                </div>
                
                ${signals.length > 0 ? `
                    <div class="flex flex-wrap gap-1 mb-3">
                        ${signals.slice(0, 3).map(signal => 
                            `<span class="text-xs bg-gray-700 px-2 py-1 rounded">${this.escapeHtml(signal).substring(0, 30)}</span>`
                        ).join('')}
                        ${signals.length > 3 ? `<span class="text-xs text-gray-400">+${signals.length - 3} more</span>` : ''}
                    </div>
                ` : ''}
                
                ${isPotential ? `
                    <div class="flex gap-2 pt-3 border-t border-gray-700">
                        <button onclick="event.stopPropagation(); leadManager.confirmLead('${lead.lead_id}')" 
                                class="flex-1 bg-green-600 hover:bg-green-700 py-2 rounded text-sm font-medium">
                            ✓ Confirm Lead
                        </button>
                        <button onclick="event.stopPropagation(); leadManager.deleteLead('${lead.lead_id}')" 
                                class="flex-1 bg-red-600 hover:bg-red-700 py-2 rounded text-sm font-medium">
                            ✗ Not a Lead
                        </button>
                    </div>
                ` : `
                    <div class="pt-3 border-t border-gray-700 text-center text-sm text-gray-400">
                        Click to view details
                    </div>
                `}
            </div>
        `;
    }
    
    showLeadDetail(leadId) {
        const lead = this.leads.find(l => l.lead_id === leadId);
        if (!lead) return;
        
        // Parse signals
        let signals = lead.signals;
        if (typeof signals === 'string') {
            try {
                signals = JSON.parse(signals.replace(/'/g, '"'));
            } catch {
                signals = signals.split(',').map(s => s.trim());
            }
        }
        signals = signals || [];
        
        // Parse metadata
        let metadata = {};
        if (lead.metadata) {
            try {
                metadata = typeof lead.metadata === 'string' ? JSON.parse(lead.metadata.replace(/'/g, '"')) : lead.metadata;
            } catch {
                metadata = {};
            }
        }
        
        const isPotential = lead.status === 'potential';
        const scoreColor = lead.score >= 80 ? 'text-green-400' : lead.score >= 60 ? 'text-yellow-400' : 'text-gray-400';
        
        const content = `
            <div class="space-y-6 max-h-[600px] overflow-y-auto pr-2">
                <!-- Header -->
                <div class="flex justify-between items-start sticky top-0 bg-gray-800 pb-4 border-b border-gray-700">
                    <div>
                        <h1 class="text-2xl font-bold mb-1">${this.escapeHtml(lead.contact_name || 'Unknown')}</h1>
                        <p class="text-blue-400 mb-1">📧 ${this.escapeHtml(lead.contact_email)}</p>
                        ${lead.company ? `<p class="text-purple-400">🏢 ${this.escapeHtml(lead.company)}</p>` : ''}
                        <div class="flex items-center gap-2 mt-2">
                            <span class="text-xs bg-${lead.lead_type === 'customer' ? 'green' : lead.lead_type === 'investor' ? 'blue' : 'purple'}-600 px-2 py-1 rounded">
                                ${lead.lead_type.toUpperCase()}
                            </span>
                            <span class="text-xs bg-gray-700 px-2 py-1 rounded">${lead.source}</span>
                            <span class="text-xs ${isPotential ? 'bg-yellow-600' : 'bg-green-600'} px-2 py-1 rounded">${lead.status.toUpperCase()}</span>
                        </div>
                    </div>
                    <div class="text-center">
                        <div class="text-4xl font-bold ${scoreColor}">${lead.score}</div>
                        <div class="text-xs text-gray-400">confidence: ${(lead.confidence * 100).toFixed(0)}%</div>
                    </div>
                </div>
                
                <!-- Original Context -->
                ${lead.context ? `
                    <div class="bg-gray-700 rounded-lg p-4">
                        <h3 class="text-lg font-semibold mb-2 flex items-center gap-2">
                            <span>📄</span> Original Content
                        </h3>
                        <div class="text-sm text-gray-300 whitespace-pre-wrap max-h-48 overflow-y-auto border border-gray-600 rounded p-3 bg-gray-900">
                            ${this.escapeHtml(lead.context).substring(0, 1000)}${lead.context.length > 1000 ? '...' : ''}
                        </div>
                    </div>
                ` : ''}
                
                <!-- Detected Signals -->
                ${signals.length > 0 ? `
                    <div>
                        <h3 class="text-lg font-semibold mb-2 flex items-center gap-2">
                            <span>🎯</span> Detected Signals
                        </h3>
                        <div class="flex flex-wrap gap-2">
                            ${signals.map(signal => 
                                `<span class="bg-blue-600 px-3 py-1 rounded text-sm">${this.escapeHtml(signal)}</span>`
                            ).join('')}
                        </div>
                    </div>
                ` : ''}
                
                <!-- Risk Assessment -->
                ${lead.foundershield_score !== null ? `
                    <div class="bg-gray-700 rounded-lg p-4">
                        <h3 class="text-lg font-semibold mb-2 flex items-center gap-2">
                            <span>🛡️</span> Risk Assessment
                        </h3>
                        <div class="flex items-center gap-4">
                            <div>
                                <div class="text-2xl font-bold ${lead.risk_level === 'low' ? 'text-green-400' : lead.risk_level === 'medium' ? 'text-yellow-400' : 'text-red-400'}">
                                    ${lead.foundershield_score}
                                </div>
                                <div class="text-xs text-gray-400">FounderShield Score</div>
                            </div>
                            <div class="flex-1">
                                <span class="text-sm px-3 py-1 rounded ${lead.risk_level === 'low' ? 'bg-green-600' : lead.risk_level === 'medium' ? 'bg-yellow-600' : 'bg-red-600'}">
                                    ${lead.risk_level ? lead.risk_level.toUpperCase() : 'UNKNOWN'} RISK
                                </span>
                            </div>
                        </div>
                    </div>
                ` : ''}
                
                <!-- Timeline -->
                <div class="bg-gray-700 rounded-lg p-4">
                    <h3 class="text-lg font-semibold mb-2 flex items-center gap-2">
                        <span>🕒</span> Timeline
                    </h3>
                    <div class="space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span class="text-gray-400">First Seen:</span>
                            <span class="text-white">${new Date(lead.first_seen).toLocaleString()}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Last Contact:</span>
                            <span class="text-white">${new Date(lead.last_contact).toLocaleString()}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Conversation Count:</span>
                            <span class="text-white">${lead.conversation_count}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Next Action -->
                ${lead.next_action ? `
                    <div class="bg-purple-900/30 border border-purple-500 rounded-lg p-4">
                        <h3 class="text-lg font-semibold mb-2 flex items-center gap-2">
                            <span>📋</span> Suggested Next Action
                        </h3>
                        <p class="text-gray-300">${this.escapeHtml(lead.next_action)}</p>
                    </div>
                ` : ''}
                
                <!-- Metadata -->
                ${Object.keys(metadata).length > 0 ? `
                    <div class="bg-gray-700 rounded-lg p-4">
                        <h3 class="text-sm font-semibold mb-2 text-gray-400">Additional Information</h3>
                        <div class="space-y-1 text-xs">
                            ${Object.entries(metadata).map(([key, value]) => 
                                `<div class="flex justify-between">
                                    <span class="text-gray-400">${key}:</span>
                                    <span class="text-white">${this.escapeHtml(String(value).substring(0, 50))}</span>
                                </div>`
                            ).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        const actions = isPotential ? [
            {
                label: '✓ Confirm Lead',
                class: 'bg-green-600 hover:bg-green-700',
                onclick: `leadManager.confirmLead('${leadId}'); document.querySelector('.modal-backdrop').remove();`
            },
            {
                label: '✗ Not a Lead',
                class: 'bg-red-600 hover:bg-red-700',
                onclick: `leadManager.deleteLead('${leadId}'); document.querySelector('.modal-backdrop').remove();`
            }
        ] : [
            {
                label: 'Close',
                class: 'bg-gray-600 hover:bg-gray-700',
                onclick: `document.querySelector('.modal-backdrop').remove();`
            }
        ];
        
        showModal(`Lead Details: ${this.escapeHtml(lead.contact_name || 'Unknown')}`, content, actions);
    }
    
    async generateLeads() {
        try {
            // Show loading state
            const btn = document.getElementById('collect-leads-btn');
            const icon = document.getElementById('collect-leads-icon');
            const text = document.getElementById('collect-leads-text');
            
            if (!btn) return;
            
            btn.disabled = true;
            btn.classList.add('opacity-75', 'cursor-not-allowed');
            if (icon) icon.innerHTML = '⏳';
            if (text) text.textContent = 'Collecting...';
            
            // Show starting notification
            this.showNotification('info', '🔍 Searching emails, calendar, and notes for leads...');
            
            const response = await fetch('/api/leads/collect?days_back=7&sources=email,calendar,notes', {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update last collection time
                const now = new Date();
                localStorage.setItem('lastLeadCollection', now.toISOString());
                this.updateLastCollectionTime();
                
                // Show success notification
                const stats = data.statistics.by_type;
                const statsText = Object.entries(stats)
                    .map(([type, count]) => `${count} ${type}`)
                    .join(', ');
                
                const message = data.leads_collected > 0 
                    ? `✅ Found ${data.leads_collected} new leads! (${statsText})`
                    : '✓ Collection complete. No new leads found.';
                
                this.showNotification('success', message);
                
                // Reload leads
                await this.loadLeads();
            } else {
                const error = await response.json();
                this.showNotification('error', '❌ Failed to collect leads: ' + (error.detail || 'Unknown error'));
            }
            
            // Restore button
            btn.disabled = false;
            btn.classList.remove('opacity-75', 'cursor-not-allowed');
            if (icon) icon.innerHTML = '📥';
            if (text) text.textContent = 'Collect New Leads';
            
        } catch (error) {
            console.error('Error collecting leads:', error);
            this.showNotification('error', '❌ Error collecting leads: ' + error.message);
            
            // Restore button on error
            const btn = document.getElementById('collect-leads-btn');
            const icon = document.getElementById('collect-leads-icon');
            const text = document.getElementById('collect-leads-text');
            
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('opacity-75', 'cursor-not-allowed');
            }
            if (icon) icon.innerHTML = '📥';
            if (text) text.textContent = 'Collect New Leads';
        }
    }
    
    showNotification(type, message) {
        const notification = document.getElementById('leads-notification');
        const notificationText = document.getElementById('leads-notification-text');
        const notificationIcon = document.getElementById('leads-notification-icon');
        
        if (!notification || !notificationText) return;
        
        // Set styles based on type
        notification.className = 'mb-4 p-4 rounded-lg';
        
        if (type === 'success') {
            notification.classList.add('bg-green-900', 'border', 'border-green-700');
            if (notificationIcon) notificationIcon.innerHTML = '<div class="w-6 h-6 text-green-400">✓</div>';
        } else if (type === 'error') {
            notification.classList.add('bg-red-900', 'border', 'border-red-700');
            if (notificationIcon) notificationIcon.innerHTML = '<div class="w-6 h-6 text-red-400">✗</div>';
        } else if (type === 'info') {
            notification.classList.add('bg-blue-900', 'border', 'border-blue-700');
            if (notificationIcon) notificationIcon.innerHTML = '<div class="w-6 h-6 text-blue-400 animate-pulse">ℹ</div>';
        }
        
        notificationText.textContent = message;
        notification.classList.remove('hidden');
        
        // Auto-hide after 5 seconds for success/info
        if (type !== 'error') {
            setTimeout(() => {
                notification.classList.add('hidden');
            }, 5000);
        }
    }
    
    updateLastCollectionTime() {
        const timeElement = document.getElementById('last-collection-time');
        if (!timeElement) return;
        
        const lastCollection = localStorage.getItem('lastLeadCollection');
        if (!lastCollection) {
            timeElement.textContent = 'Never';
            return;
        }
        
        const date = new Date(lastCollection);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        let timeAgo;
        if (diffMins < 1) {
            timeAgo = 'Just now';
        } else if (diffMins < 60) {
            timeAgo = `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            timeAgo = `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        } else if (diffDays < 7) {
            timeAgo = `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        } else {
            timeAgo = date.toLocaleDateString();
        }
        
        timeElement.textContent = timeAgo;
        timeElement.title = date.toLocaleString();
    }
    
    async confirmLead(leadId) {
        try {
            const response = await fetch(`/api/leads/${leadId}/confirm`, {
                method: 'POST'
            });
            
            if (response.ok) {
                console.log('Lead confirmed:', leadId);
                // Update local state
                const lead = this.leads.find(l => l.lead_id === leadId);
                if (lead) {
                    lead.status = 'new';
                }
                this.renderLeads();
                this.updateCounts();
            } else {
                alert('Failed to confirm lead');
            }
        } catch (error) {
            console.error('Error confirming lead:', error);
            alert('Error confirming lead: ' + error.message);
        }
    }
    
    async deleteLead(leadId) {
        try {
            const reason = prompt('Why is this not a lead?\n\nOptions:\n- spam\n- not_relevant\n- wrong_contact\n- duplicate', 'not_relevant');
            if (!reason) return;
            
            const response = await fetch(`/api/leads/${leadId}?reason=${encodeURIComponent(reason)}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                console.log('Lead deleted:', leadId);
                // Remove from view
                this.leads = this.leads.filter(l => l.lead_id !== leadId);
                this.renderLeads();
                this.updateCounts();
            } else {
                alert('Failed to delete lead');
            }
        } catch (error) {
            console.error('Error deleting lead:', error);
            alert('Error deleting lead: ' + error.message);
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
