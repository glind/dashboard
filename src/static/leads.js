/**
 * Lead Generation Dashboard JavaScript
 * Handles lead display, filtering, generation, and analysis
 */

class LeadDashboard {
    constructor() {
        this.leads = [];
        this.filteredLeads = [];
        this.currentFilters = {};
        this.statistics = {};
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadLeads();
        this.updateScoreDisplay();
    }
    
    setupEventListeners() {
        // Generate leads button
        document.getElementById('generate-leads').addEventListener('click', () => this.generateLeads());
        
        // Refresh leads button
        document.getElementById('refresh-leads').addEventListener('click', () => this.loadLeads());
        
        // Analyze patterns button
        document.getElementById('analyze-patterns').addEventListener('click', () => this.analyzePatterns());
        
        // Filter controls
        document.getElementById('apply-filters').addEventListener('click', () => this.applyFilters());
        document.getElementById('clear-filters').addEventListener('click', () => this.clearFilters());
        
        // Score range slider
        const scoreSlider = document.getElementById('filter-score');
        scoreSlider.addEventListener('input', (e) => {
            document.getElementById('score-value').textContent = e.target.value + '%';
        });
        
        // Export leads
        document.getElementById('export-leads').addEventListener('click', () => this.exportLeads());
        
        // Modal controls
        document.getElementById('close-modal').addEventListener('click', () => this.closeModal());
        
        // Close modal on background click
        document.getElementById('lead-modal').addEventListener('click', (e) => {
            if (e.target.id === 'lead-modal') {
                this.closeModal();
            }
        });
        
        // ESC key to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }
    
    async loadLeads() {
        try {
            this.showLoading('Loading existing leads...');
            
            const response = await fetch('/api/leads');
            if (response.ok) {
                const data = await response.json();
                this.leads = data.leads || [];
                this.statistics = data.statistics || {};
                
                this.updateStatistics();
                this.updateFilterOptions();
                this.filterAndDisplayLeads();
            } else {
                console.error('Failed to load leads');
                this.showError('Failed to load leads');
            }
        } catch (error) {
            console.error('Error loading leads:', error);
            this.showError('Error loading leads: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    async generateLeads() {
        try {
            const targetCount = document.getElementById('target-count').value;
            const templateFocus = document.getElementById('template-focus').value;
            
            this.showLoading(`Generating ${targetCount} new leads...`);
            
            const requestBody = {
                target_count: parseInt(targetCount),
                template_focus: templateFocus || undefined,
                filters: this.currentFilters
            };
            
            const response = await fetch('/api/leads/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            if (response.ok) {
                const data = await response.json();
                this.leads = data.leads || [];
                this.statistics = data.statistics || {};
                
                this.updateStatistics();
                this.updateFilterOptions();
                this.filterAndDisplayLeads();
                
                this.showSuccess(`Generated ${this.leads.length} new leads!`);
            } else {
                const errorData = await response.json();
                this.showError('Failed to generate leads: ' + (errorData.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error generating leads:', error);
            this.showError('Error generating leads: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    async analyzePatterns() {
        try {
            this.showLoading('Analyzing interaction patterns...');
            
            const response = await fetch('/api/lead-patterns/analyze', {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showAnalysisResults(data);
            } else {
                this.showError('Failed to analyze patterns');
            }
        } catch (error) {
            console.error('Error analyzing patterns:', error);
            this.showError('Error analyzing patterns: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
    
    applyFilters() {
        const industry = document.getElementById('filter-industry').value;
        const size = document.getElementById('filter-size').value;
        const priority = document.getElementById('filter-priority').value;
        const minScore = document.getElementById('filter-score').value;
        
        this.currentFilters = {
            industry: industry || undefined,
            company_size: size || undefined,
            priority_level: priority || undefined,
            min_match_score: minScore > 0 ? parseFloat(minScore) / 100 : undefined
        };
        
        this.filterAndDisplayLeads();
    }
    
    clearFilters() {
        document.getElementById('filter-industry').value = '';
        document.getElementById('filter-size').value = '';
        document.getElementById('filter-priority').value = '';
        document.getElementById('filter-score').value = '0';
        document.getElementById('score-value').textContent = '0%';
        
        this.currentFilters = {};
        this.filterAndDisplayLeads();
    }
    
    filterAndDisplayLeads() {
        // Apply current filters
        this.filteredLeads = this.leads.filter(lead => {
            if (this.currentFilters.industry && 
                !lead.industry.toLowerCase().includes(this.currentFilters.industry.toLowerCase())) {
                return false;
            }
            
            if (this.currentFilters.company_size && 
                !lead.estimated_size.toLowerCase().includes(this.currentFilters.company_size.toLowerCase())) {
                return false;
            }
            
            if (this.currentFilters.priority_level && 
                lead.priority_level !== this.currentFilters.priority_level) {
                return false;
            }
            
            if (this.currentFilters.min_match_score && 
                lead.match_score < this.currentFilters.min_match_score) {
                return false;
            }
            
            return true;
        });
        
        this.displayLeads();
    }
    
    displayLeads() {
        const container = document.getElementById('leads-container');
        const leadsCount = document.getElementById('leads-count');
        
        if (this.filteredLeads.length === 0) {
            container.innerHTML = `
                <div id="no-leads-message" class="p-8 text-center">
                    <div class="text-gray-400 mb-4">
                        <svg class="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                        </svg>
                    </div>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">No leads generated yet</h3>
                    <p class="text-gray-500 mb-4">Click "Generate Leads" to start finding potential business opportunities based on your learned patterns.</p>
                    <button onclick="document.getElementById('generate-leads').click()" class="bg-lead-primary text-white px-4 py-2 rounded-lg hover:bg-lead-secondary transition-colors">
                        🎯 Generate Your First Leads
                    </button>
                </div>
            `;
            leadsCount.textContent = '0 leads';
            return;
        }
        
        leadsCount.textContent = `${this.filteredLeads.length} leads`;
        
        // Generate lead cards
        container.innerHTML = this.filteredLeads.map(lead => this.createLeadCard(lead)).join('');
        
        // Add event listeners to lead cards
        this.attachLeadEventListeners();
    }
    
    createLeadCard(lead) {
        const priorityColors = {
            high: 'bg-red-100 text-red-800',
            medium: 'bg-yellow-100 text-yellow-800',
            low: 'bg-green-100 text-green-800'
        };
        
        const priorityColor = priorityColors[lead.priority_level] || 'bg-gray-100 text-gray-800';
        const matchPercentage = Math.round(lead.match_score * 100);
        
        return `
            <div class="lead-card p-6 hover:bg-gray-50 cursor-pointer" data-lead-id="${lead.company_name}">
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <div class="flex items-center mb-2">
                            <h3 class="text-lg font-semibold text-gray-900">${lead.company_name}</h3>
                            <span class="ml-2 px-2 py-1 text-xs font-medium rounded-full ${priorityColor}">
                                ${lead.priority_level.toUpperCase()} PRIORITY
                            </span>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                            <div>
                                <p class="text-sm font-medium text-gray-500">Industry</p>
                                <p class="text-sm text-gray-900">${lead.industry}</p>
                            </div>
                            <div>
                                <p class="text-sm font-medium text-gray-500">Company Size</p>
                                <p class="text-sm text-gray-900">${lead.estimated_size}</p>
                            </div>
                            <div>
                                <p class="text-sm font-medium text-gray-500">Domain</p>
                                <p class="text-sm text-gray-900">${lead.domain}</p>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <p class="text-sm font-medium text-gray-500 mb-2">Match Reasons</p>
                            <div class="flex flex-wrap gap-2">
                                ${lead.match_reasons.slice(0, 3).map(reason => `
                                    <span class="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-md">${reason}</span>
                                `).join('')}
                                ${lead.match_reasons.length > 3 ? `
                                    <span class="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-md">+${lead.match_reasons.length - 3} more</span>
                                ` : ''}
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-4">
                                <div class="flex items-center">
                                    <span class="text-sm font-medium text-gray-500">Match Score:</span>
                                    <div class="ml-2 w-20 bg-gray-200 rounded-full h-2">
                                        <div class="h-2 rounded-full ${matchPercentage >= 80 ? 'bg-green-500' : matchPercentage >= 60 ? 'bg-yellow-500' : 'bg-red-500'}" 
                                             style="width: ${matchPercentage}%"></div>
                                    </div>
                                    <span class="ml-2 text-sm font-semibold text-gray-900">${matchPercentage}%</span>
                                </div>
                                
                                <div class="text-sm text-gray-500">
                                    📧 ${lead.contact_info.email ? '✓' : '✗'} Email
                                    📞 ${lead.contact_info.phone ? '✓' : '✗'} Phone
                                    💼 ${lead.contact_info.linkedin ? '✓' : '✗'} LinkedIn
                                </div>
                            </div>
                            
                            <div class="flex space-x-2">
                                <button class="view-lead-btn bg-blue-500 text-white px-3 py-1 rounded text-sm hover:bg-blue-600 transition-colors" 
                                        data-lead-id="${lead.company_name}">
                                    👁️ View Details
                                </button>
                                <button class="contact-lead-btn bg-green-500 text-white px-3 py-1 rounded text-sm hover:bg-green-600 transition-colors"
                                        data-lead-id="${lead.company_name}">
                                    📧 Contact
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    attachLeadEventListeners() {
        // View details buttons
        document.querySelectorAll('.view-lead-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const leadId = btn.getAttribute('data-lead-id');
                this.showLeadDetails(leadId);
            });
        });
        
        // Contact buttons
        document.querySelectorAll('.contact-lead-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const leadId = btn.getAttribute('data-lead-id');
                this.contactLead(leadId);
            });
        });
        
        // Lead card clicks
        document.querySelectorAll('.lead-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const leadId = card.getAttribute('data-lead-id');
                this.showLeadDetails(leadId);
            });
        });
    }
    
    showLeadDetails(leadId) {
        const lead = this.filteredLeads.find(l => l.company_name === leadId);
        if (!lead) return;
        
        document.getElementById('modal-company-name').textContent = lead.company_name;
        document.getElementById('modal-content').innerHTML = this.createLeadDetailsHTML(lead);
        document.getElementById('lead-modal').classList.remove('hidden');
    }
    
    createLeadDetailsHTML(lead) {
        const matchPercentage = Math.round(lead.match_score * 100);
        const techScore = Math.round(lead.technical_fit_score * 100);
        const businessScore = Math.round(lead.business_potential_score * 100);
        const contactScore = Math.round(lead.contact_accessibility_score * 100);
        
        return `
            <div class="space-y-6">
                <!-- Company Overview -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="space-y-4">
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-3">🏢 Company Information</h3>
                            <div class="space-y-2">
                                <div><span class="font-medium">Industry:</span> ${lead.industry}</div>
                                <div><span class="font-medium">Size:</span> ${lead.estimated_size}</div>
                                <div><span class="font-medium">Domain:</span> <a href="https://${lead.domain}" target="_blank" class="text-blue-600 hover:underline">${lead.domain}</a></div>
                                <div><span class="font-medium">Priority:</span> <span class="px-2 py-1 text-xs font-medium rounded-full ${lead.priority_level === 'high' ? 'bg-red-100 text-red-800' : lead.priority_level === 'medium' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}">${lead.priority_level.toUpperCase()}</span></div>
                            </div>
                        </div>
                        
                        <div>
                            <h4 class="font-semibold text-gray-900 mb-2">📞 Contact Information</h4>
                            <div class="space-y-1 text-sm">
                                ${lead.contact_info.email ? `<div>📧 <a href="mailto:${lead.contact_info.email}" class="text-blue-600 hover:underline">${lead.contact_info.email}</a></div>` : '<div class="text-gray-500">📧 No email available</div>'}
                                ${lead.contact_info.phone ? `<div>📞 <a href="tel:${lead.contact_info.phone}" class="text-blue-600 hover:underline">${lead.contact_info.phone}</a></div>` : '<div class="text-gray-500">📞 No phone available</div>'}
                                ${lead.contact_info.linkedin ? `<div>💼 <a href="${lead.contact_info.linkedin}" target="_blank" class="text-blue-600 hover:underline">LinkedIn Profile</a></div>` : '<div class="text-gray-500">💼 No LinkedIn available</div>'}
                            </div>
                        </div>
                    </div>
                    
                    <div class="space-y-4">
                        <div>
                            <h3 class="text-lg font-semibold text-gray-900 mb-3">📊 Match Analysis</h3>
                            <div class="space-y-3">
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium">Overall Match</span>
                                    <div class="flex items-center">
                                        <div class="w-24 bg-gray-200 rounded-full h-2 mr-2">
                                            <div class="h-2 rounded-full ${matchPercentage >= 80 ? 'bg-green-500' : matchPercentage >= 60 ? 'bg-yellow-500' : 'bg-red-500'}" style="width: ${matchPercentage}%"></div>
                                        </div>
                                        <span class="text-sm font-semibold">${matchPercentage}%</span>
                                    </div>
                                </div>
                                
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium">Technical Fit</span>
                                    <div class="flex items-center">
                                        <div class="w-24 bg-gray-200 rounded-full h-2 mr-2">
                                            <div class="h-2 rounded-full bg-blue-500" style="width: ${techScore}%"></div>
                                        </div>
                                        <span class="text-sm font-semibold">${techScore}%</span>
                                    </div>
                                </div>
                                
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium">Business Potential</span>
                                    <div class="flex items-center">
                                        <div class="w-24 bg-gray-200 rounded-full h-2 mr-2">
                                            <div class="h-2 rounded-full bg-purple-500" style="width: ${businessScore}%"></div>
                                        </div>
                                        <span class="text-sm font-semibold">${businessScore}%</span>
                                    </div>
                                </div>
                                
                                <div class="flex items-center justify-between">
                                    <span class="text-sm font-medium">Contact Access</span>
                                    <div class="flex items-center">
                                        <div class="w-24 bg-gray-200 rounded-full h-2 mr-2">
                                            <div class="h-2 rounded-full bg-orange-500" style="width: ${contactScore}%"></div>
                                        </div>
                                        <span class="text-sm font-semibold">${contactScore}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div>
                            <h4 class="font-semibold text-gray-900 mb-2">🎯 Template Matches</h4>
                            <div class="flex flex-wrap gap-2">
                                ${lead.template_matches.map(template => `
                                    <span class="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded-md">${template}</span>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Match Reasons -->
                <div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-3">✅ Why This Lead Matches</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                        ${lead.match_reasons.map(reason => `
                            <div class="flex items-center p-2 bg-green-50 rounded-md">
                                <span class="text-green-600 mr-2">✓</span>
                                <span class="text-sm text-green-800">${reason}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <!-- Recommended Approach -->
                <div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-3">🎯 Recommended Approach</h3>
                    <div class="bg-blue-50 p-4 rounded-lg">
                        <p class="text-blue-800">${lead.recommended_approach}</p>
                    </div>
                </div>
                
                <!-- Next Steps -->
                <div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-3">📋 Next Steps</h3>
                    <div class="space-y-2">
                        ${lead.next_steps.map((step, index) => `
                            <div class="flex items-start">
                                <span class="flex-shrink-0 w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-xs font-semibold mr-3 mt-0.5">${index + 1}</span>
                                <p class="text-sm text-gray-700">${step}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="flex space-x-4 pt-4 border-t">
                    <button onclick="window.leadDashboard.contactLead('${lead.company_name}')" class="flex-1 bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 transition-colors">
                        📧 Start Outreach
                    </button>
                    <button onclick="window.leadDashboard.scheduleMeeting('${lead.company_name}')" class="flex-1 bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors">
                        📅 Schedule Meeting
                    </button>
                    <button onclick="window.leadDashboard.addToTasks('${lead.company_name}')" class="flex-1 bg-purple-500 text-white px-4 py-2 rounded-lg hover:bg-purple-600 transition-colors">
                        ➕ Add to Tasks
                    </button>
                </div>
            </div>
        `;
    }
    
    closeModal() {
        document.getElementById('lead-modal').classList.add('hidden');
    }
    
    contactLead(leadId) {
        const lead = this.filteredLeads.find(l => l.company_name === leadId);
        if (!lead) return;
        
        if (lead.contact_info.email) {
            const subject = encodeURIComponent(`Partnership Opportunity with ${lead.company_name}`);
            const body = encodeURIComponent(`Hi,\n\nI hope this email finds you well. I came across ${lead.company_name} and was impressed by your work in ${lead.industry}.\n\nI believe there may be some interesting collaboration opportunities between our teams, particularly in areas like:\n\n${lead.match_reasons.slice(0, 3).map(reason => `• ${reason}`).join('\n')}\n\nWould you be open to a brief conversation to explore potential synergies?\n\nBest regards`);
            
            window.open(`mailto:${lead.contact_info.email}?subject=${subject}&body=${body}`);
        } else {
            this.showError('No email address available for this lead');
        }
    }
    
    scheduleMeeting(leadId) {
        const lead = this.filteredLeads.find(l => l.company_name === leadId);
        if (!lead) return;
        
        // This would integrate with a calendar system
        this.showInfo(`Meeting scheduling for ${lead.company_name} - integrate with your calendar system`);
    }
    
    addToTasks(leadId) {
        const lead = this.filteredLeads.find(l => l.company_name === leadId);
        if (!lead) return;
        
        // Add lead follow-up to task system
        const taskData = {
            title: `Follow up with ${lead.company_name}`,
            description: `Research and reach out to ${lead.company_name} (${lead.industry}). Match score: ${Math.round(lead.match_score * 100)}%. Recommended approach: ${lead.recommended_approach}`,
            priority: lead.priority_level,
            category: 'business_development'
        };
        
        // This would call the task creation API
        this.createTask(taskData);
    }
    
    async createTask(taskData) {
        try {
            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(taskData)
            });
            
            if (response.ok) {
                this.showSuccess('Task created successfully!');
            } else {
                this.showError('Failed to create task');
            }
        } catch (error) {
            console.error('Error creating task:', error);
            this.showError('Error creating task: ' + error.message);
        }
    }
    
    updateStatistics() {
        document.getElementById('total-leads').textContent = this.statistics.total_leads || 0;
        document.getElementById('high-priority-leads').textContent = this.statistics.priority_distribution?.high || 0;
        document.getElementById('avg-match-score').textContent = (this.statistics.average_match_score || 0) * 100 + '%';
        document.getElementById('total-industries').textContent = Object.keys(this.statistics.industry_distribution || {}).length;
    }
    
    updateFilterOptions() {
        // Update industry filter options
        const industrySelect = document.getElementById('filter-industry');
        const industries = Object.keys(this.statistics.industry_distribution || {});
        
        // Clear existing options except "All Industries"
        industrySelect.innerHTML = '<option value="">All Industries</option>';
        
        industries.forEach(industry => {
            const option = document.createElement('option');
            option.value = industry;
            option.textContent = industry;
            industrySelect.appendChild(option);
        });
    }
    
    updateScoreDisplay() {
        const scoreSlider = document.getElementById('filter-score');
        const scoreValue = document.getElementById('score-value');
        
        scoreSlider.addEventListener('input', (e) => {
            scoreValue.textContent = e.target.value + '%';
        });
    }
    
    exportLeads() {
        if (this.filteredLeads.length === 0) {
            this.showError('No leads to export');
            return;
        }
        
        // Convert leads to CSV format
        const headers = ['Company Name', 'Industry', 'Size', 'Domain', 'Priority', 'Match Score', 'Email', 'Phone'];
        const csvData = [headers.join(',')];
        
        this.filteredLeads.forEach(lead => {
            const row = [
                lead.company_name,
                lead.industry,
                lead.estimated_size,
                lead.domain,
                lead.priority_level,
                Math.round(lead.match_score * 100) + '%',
                lead.contact_info.email || '',
                lead.contact_info.phone || ''
            ].map(field => `"${field}"`);
            
            csvData.push(row.join(','));
        });
        
        // Create and download CSV file
        const csvContent = csvData.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `leads_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        this.showSuccess('Leads exported successfully!');
    }
    
    showAnalysisResults(data) {
        // This would show pattern analysis results
        console.log('Pattern analysis results:', data);
        this.showInfo('Pattern analysis completed. Check console for details.');
    }
    
    showLoading(message = 'Processing...') {
        document.getElementById('loading-message').textContent = message;
        document.getElementById('loading-overlay').classList.remove('hidden');
    }
    
    hideLoading() {
        document.getElementById('loading-overlay').classList.add('hidden');
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showInfo(message) {
        this.showNotification(message, 'info');
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 max-w-sm ${
            type === 'success' ? 'bg-green-500 text-white' :
            type === 'error' ? 'bg-red-500 text-white' :
            'bg-blue-500 text-white'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
        
        // Allow manual close
        notification.addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }
}

// Initialize dashboard when page loads
window.addEventListener('DOMContentLoaded', () => {
    window.leadDashboard = new LeadDashboard();
});