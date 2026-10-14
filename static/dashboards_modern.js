/**
 * Modern Dashboard Manager for Sidebar Layout
 * Uses modal popovers for detailed views and editing
 */

class DashboardManager {
    constructor() {
        this.projects = [];
        this.websites = [];
    }

    async init() {
        await this.loadDashboards();
    }

    async loadDashboards() {
        try {
            const response = await fetch('/api/dashboards');
            const data = await response.json();
            
            if (data.success) {
                this.projects = data.projects || [];
                this.websites = [];
                
                this.updateCounts();
                this.renderDashboards();
            }
        } catch (error) {
            console.error('Error loading dashboards:', error);
        }
    }
    
    updateCounts() {
        // Count active projects
        const activeCount = this.projects.filter(p => p.is_active).length;
        
        const badge = document.getElementById('running-count');
        if (badge) {
            badge.textContent = activeCount;
        }
        
        const stat = document.getElementById('stat-projects');
        if (stat) {
            stat.textContent = activeCount;
        }
    }
    
    renderDashboards() {
        const grid = document.getElementById('dashboards-grid');
        if (!grid) return;
        
        if (this.projects.length === 0) {
            grid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <div class="text-6xl mb-4">🚀</div>
                    <h3 class="text-xl font-semibold mb-2">No dashboards found</h3>
                    <p class="text-gray-400">Marketing dashboards will appear here once discovered</p>
                </div>
            `;
            return;
        }
        
        const html = this.projects.map(project => this.renderProjectCard(project)).join('');
        grid.innerHTML = html;
    }
    
    renderProjectCard(project) {
        const statusColor = project.is_active ? 'bg-green-500' : 'bg-gray-500';
        const statusText = project.is_active ? 'active' : 'inactive';
        
        return `
            <div class="dashboard-card bg-gray-800 rounded-xl p-6 border border-gray-700 hover:border-gray-600 transition-colors cursor-pointer"
                 onclick="dashboardManager.showProjectDetail('${this.escapeHtml(project.name)}')">
                
                <div class="flex justify-between items-start mb-4">
                    <div class="flex-1">
                        <h3 class="text-lg font-bold text-white mb-1">${this.escapeHtml(project.name)}</h3>
                        <p class="text-sm text-gray-400">${this.escapeHtml(project.description || 'No description')}</p>
                    </div>
                    <div class="flex items-center gap-2 ml-3">
                        <span class="w-3 h-3 ${statusColor} rounded-full"></span>
                        <span class="text-sm text-gray-300 capitalize">${statusText}</span>
                    </div>
                </div>
                
                ${project.brand ? `
                    <div class="mb-3">
                        <span class="inline-block bg-purple-600 text-white text-xs px-2 py-1 rounded">${this.escapeHtml(project.brand)}</span>
                    </div>
                ` : ''}
                
                <div class="flex flex-wrap gap-2 mb-4 text-xs">
                    <span class="bg-gray-700 px-2 py-1 rounded">${project.type || 'unknown'}</span>
                    ${project.port ? `<span class="bg-blue-700 px-2 py-1 rounded">:${project.port}</span>` : ''}
                </div>
                
                <div class="flex gap-2 pt-3 border-t border-gray-700">
                    ${project.url ? `
                        <button onclick="event.stopPropagation(); window.open('${project.url}', '_blank')" 
                                class="flex-1 bg-blue-600 hover:bg-blue-700 py-2 rounded text-sm font-medium">
                            🌐 Local
                        </button>
                    ` : ''}
                    
                    ${project.production_url ? `
                        <button onclick="event.stopPropagation(); window.open('${project.production_url}', '_blank')" 
                                class="flex-1 bg-green-600 hover:bg-green-700 py-2 rounded text-sm font-medium">
                            🚀 Production
                        </button>
                    ` : ''}
                    
                    ${project.github_pages_url ? `
                        <button onclick="event.stopPropagation(); window.open('${project.github_pages_url}', '_blank')" 
                                class="flex-1 bg-purple-600 hover:bg-purple-700 py-2 rounded text-sm font-medium">
                            📄 Pages
                        </button>
                    ` : ''}
                </div>
                
                <!-- Dashboard Control Buttons -->
                <div class="flex gap-1 mt-3">
                    <button onclick="event.stopPropagation(); dashboardManager.startDashboard('${this.escapeHtml(project.name)}')" 
                            class="flex-1 bg-purple-600 hover:bg-purple-700 py-2 rounded text-xs font-medium"
                            id="start-btn-${project.name.replace(/\s+/g, '-').toLowerCase()}"
                            title="Start/Monitor Dashboard">
                        ▶️ Start
                    </button>
                    <button onclick="event.stopPropagation(); dashboardManager.checkStatus('${this.escapeHtml(project.name)}')" 
                            class="bg-yellow-600 hover:bg-yellow-700 py-2 px-3 rounded text-xs font-medium"
                            title="Check Status">
                        📊
                    </button>
                    <button onclick="event.stopPropagation(); dashboardManager.showLogs('${this.escapeHtml(project.name)}')" 
                            class="bg-indigo-600 hover:bg-indigo-700 py-2 px-3 rounded text-xs font-medium"
                            title="View Logs">
                        📝
                    </button>
                </div>
                
                <!-- Status Display Area -->
                <div id="status-${project.name.replace(/\s+/g, '-').toLowerCase()}" 
                     class="mt-2 text-xs text-center" style="display: none;"></div>
            </div>
        `;
    }
    
    showProjectDetail(projectName) {
        const project = this.projects.find(p => p.name === projectName);
        if (!project) return;
        
        // Simply open the edit modal for this project
        if (typeof showAddDashboardModal === 'function') {
            showAddDashboardModal(project);
        } else {
            console.error('showAddDashboardModal function not found');
        }
    }
    
    async startProject(projectName) {
        try {
            const response = await fetch(`/api/dashboards/${projectName}/start`, { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                alert(`${projectName} started successfully`);
                await this.loadDashboards();
            } else {
                alert(`Failed to start ${projectName}`);
            }
        } catch (error) {
            console.error('Error starting project:', error);
            alert('Error starting project: ' + error.message);
        }
    }
    
    async stopProject(projectName) {
        try {
            const response = await fetch(`/api/dashboards/${projectName}/stop`, { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                alert(`${projectName} stopped successfully`);
                await this.loadDashboards();
            } else {
                alert(`Failed to stop ${projectName}`);
            }
        } catch (error) {
            console.error('Error stopping project:', error);
            alert('Error stopping project: ' + error.message);
        }
    }
    
    async deleteProject(projectName) {
        if (!confirm(`Are you sure you want to permanently delete "${projectName}"?\n\nThis will remove it from your dashboard but will NOT delete the actual project files.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/dashboards/${projectName}`, { method: 'DELETE' });
            const data = await response.json();
            
            if (data.success) {
                alert(`${projectName} deleted successfully`);
                await this.loadDashboards();
            } else {
                alert(`Failed to delete ${projectName}: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error deleting project:', error);
            alert('Error deleting project: ' + error.message);
        }
    }
    
    async editProject(projectName) {
        const project = this.projects.find(p => p.name === projectName);
        if (!project) return;
        
        const content = `
            <form id="edit-project-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-1">Path</label>
                    <input type="text" name="path" value="${this.escapeHtml(project.path || '')}" 
                           class="w-full bg-gray-700 px-3 py-2 rounded border border-gray-600">
                </div>
                
                <div>
                    <label class="block text-sm font-medium mb-1">Custom Domain / URL</label>
                    <input type="text" name="custom_domain" value="${this.escapeHtml(project.url || '')}" 
                           placeholder="https://example.com"
                           class="w-full bg-gray-700 px-3 py-2 rounded border border-gray-600">
                </div>
                
                <div>
                    <label class="block text-sm font-medium mb-1">Start Command</label>
                    <input type="text" name="start_command" value="${this.escapeHtml(project.start_command || '')}" 
                           class="w-full bg-gray-700 px-3 py-2 rounded border border-gray-600">
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-1">Port</label>
                        <input type="number" name="port" value="${project.port || ''}" 
                               class="w-full bg-gray-700 px-3 py-2 rounded border border-gray-600">
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-1">Brand</label>
                        <input type="text" name="brand" value="${this.escapeHtml(project.brand || '')}" 
                               class="w-full bg-gray-700 px-3 py-2 rounded border border-gray-600">
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium mb-1">Description</label>
                    <textarea name="description" rows="2" 
                              class="w-full bg-gray-700 px-3 py-2 rounded border border-gray-600">${this.escapeHtml(project.description || '')}</textarea>
                </div>
            </form>
        `;
        
        const actions = [
            {
                label: '💾 Save',
                class: 'bg-blue-600 hover:bg-blue-700',
                onclick: `dashboardManager.saveProjectEdit('${this.escapeHtml(projectName)}');`
            },
            {
                label: 'Cancel',
                class: 'bg-gray-600 hover:bg-gray-700',
                onclick: `document.querySelector('.modal-backdrop').remove();`
            }
        ];
        
        showModal(`Edit: ${this.escapeHtml(projectName)}`, content, actions);
    }
    
    async saveProjectEdit(projectName) {
        const form = document.getElementById('edit-project-form');
        const formData = new FormData(form);
        
        const updates = {
            path: formData.get('path'),
            custom_domain: formData.get('custom_domain'),
            start_command: formData.get('start_command'),
            port: formData.get('port') ? parseInt(formData.get('port')) : null,
            brand: formData.get('brand'),
            description: formData.get('description')
        };
        
        try {
            const response = await fetch(`/api/dashboards/${projectName}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            
            if (response.ok) {
                alert('Configuration saved successfully');
                document.querySelector('.modal-backdrop').remove();
                await this.loadDashboards();
            } else {
                alert('Failed to save configuration');
            }
        } catch (error) {
            console.error('Error saving configuration:', error);
            alert('Error saving configuration: ' + error.message);
        }
    }
    
    // New dashboard control methods
    async startDashboard(projectName) {
        const buttonId = `start-btn-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
        const statusId = `status-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
        const button = document.getElementById(buttonId);
        const statusDiv = document.getElementById(statusId);
        
        if (!button || !statusDiv) {
            console.error('Dashboard control elements not found');
            return;
        }
        
        try {
            // Update button to show starting state
            button.innerHTML = '⏳ Starting...';
            button.disabled = true;
            
            // Show status area
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '<div class="text-yellow-400 bg-yellow-900/20 p-2 rounded">🚀 Starting dashboard...</div>';
            
            // Start the dashboard
            const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/start`, {
                method: 'POST'
            });
            const result = await response.json();
            
            if (result.success) {
                // Update button to monitoring state
                button.innerHTML = '👁️ Monitor';
                button.disabled = false;
                
                // Show success status
                statusDiv.innerHTML = `
                    <div class="text-green-400 bg-green-900/20 p-2 rounded">
                        ✅ Dashboard started successfully
                        ${result.process_id ? `<br><small>Process ID: ${result.process_id}</small>` : ''}
                        ${result.port ? `<br><small>Port: ${result.port}</small>` : ''}
                    </div>
                `;
                
                // Start monitoring
                this.monitorDashboard(projectName);
                
                // Refresh the project list to update status
                setTimeout(() => this.loadDashboards(), 2000);
                
            } else {
                throw new Error(result.error || 'Failed to start dashboard');
            }
            
        } catch (error) {
            console.error(`Error starting dashboard ${projectName}:`, error);
            
            // Reset button
            button.innerHTML = '▶️ Start';
            button.disabled = false;
            
            // Show error status
            statusDiv.innerHTML = `<div class="text-red-400 bg-red-900/20 p-2 rounded">❌ Error: ${error.message}</div>`;
        }
    }
    
    async checkStatus(projectName) {
        const statusId = `status-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
        const statusDiv = document.getElementById(statusId);
        
        if (!statusDiv) return;
        
        statusDiv.style.display = 'block';
        statusDiv.innerHTML = '<div class="text-yellow-400 bg-yellow-900/20 p-2 rounded">🔍 Checking status...</div>';
        
        try {
            const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/status`);
            const status = await response.json();
            
            if (status.success) {
                const isRunning = status.status === 'running';
                const statusClass = isRunning ? 'text-green-400 bg-green-900/20' : 'text-red-400 bg-red-900/20';
                const statusIcon = isRunning ? '🟢' : '🔴';
                
                statusDiv.innerHTML = `
                    <div class="${statusClass} p-2 rounded">
                        ${statusIcon} ${status.status || 'unknown'}
                        ${status.uptime ? `<br><small>Uptime: ${status.uptime}</small>` : ''}
                        ${status.port ? `<br><small>Port: ${status.port}</small>` : ''}
                        ${status.process_id ? `<br><small>PID: ${status.process_id}</small>` : ''}
                    </div>
                `;
            } else {
                statusDiv.innerHTML = `<div class="text-red-400 bg-red-900/20 p-2 rounded">❌ ${status.error}</div>`;
            }
            
        } catch (error) {
            console.error(`Error checking dashboard status:`, error);
            statusDiv.innerHTML = `<div class="text-red-400 bg-red-900/20 p-2 rounded">❌ Status check failed</div>`;
        }
    }
    
    async showLogs(projectName) {
        try {
            const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/logs`);
            const logsData = await response.json();
            
            if (logsData.success) {
                // Create modal to show logs
                const modal = document.createElement('div');
                modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
                
                modal.innerHTML = `
                    <div class="bg-gray-800 rounded-lg p-6 max-w-4xl max-h-3/4 overflow-auto m-4">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-xl font-bold text-white">📝 ${projectName} Logs</h3>
                            <button onclick="this.closest('.fixed').remove()" 
                                    class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded">
                                ✕ Close
                            </button>
                        </div>
                        <div class="bg-black p-4 rounded font-mono text-sm text-green-400 max-h-96 overflow-y-auto whitespace-pre-wrap">
${logsData.logs || 'No logs available'}
                        </div>
                        <div class="mt-4 text-right text-sm text-gray-400">
                            Last updated: ${new Date().toLocaleTimeString()}
                        </div>
                    </div>
                `;
                
                document.body.appendChild(modal);
                
                // Close modal on background click
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        modal.remove();
                    }
                });
                
            } else {
                alert(`Error getting logs: ${logsData.error}`);
            }
            
        } catch (error) {
            console.error(`Error showing logs for ${projectName}:`, error);
            alert('Failed to load logs');
        }
    }
    
    async monitorDashboard(projectName) {
        const buttonId = `start-btn-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
        const statusId = `status-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
        const button = document.getElementById(buttonId);
        const statusDiv = document.getElementById(statusId);
        
        if (!button || !statusDiv) return;
        
        try {
            const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/status`);
            const status = await response.json();
            
            if (status.success) {
                const isRunning = status.status === 'running';
                
                if (isRunning) {
                    button.innerHTML = '🔄 Running';
                    button.style.backgroundColor = '#059669'; // green-600
                    
                    statusDiv.innerHTML = `
                        <div class="text-green-400 bg-green-900/20 p-2 rounded">
                            🟢 Running (${status.uptime || '0s'})
                            ${status.cpu_usage ? `<br><small>CPU: ${status.cpu_usage}%</small>` : ''}
                            ${status.memory_usage ? `<br><small>Memory: ${status.memory_usage}MB</small>` : ''}
                        </div>
                    `;
                    
                    // Continue monitoring every 30 seconds
                    setTimeout(() => this.monitorDashboard(projectName), 30000);
                    
                } else {
                    // Dashboard stopped
                    button.innerHTML = '▶️ Start';
                    button.style.backgroundColor = '#7c3aed'; // purple-600
                    
                    statusDiv.innerHTML = `
                        <div class="text-yellow-400 bg-yellow-900/20 p-2 rounded">
                            ⏹️ Stopped
                            ${status.reason ? `<br><small>Reason: ${status.reason}</small>` : ''}
                        </div>
                    `;
                }
            } else {
                statusDiv.innerHTML = `<div class="text-red-400 bg-red-900/20 p-2 rounded">❌ Monitoring error: ${status.error}</div>`;
            }
            
        } catch (error) {
            console.error(`Error monitoring dashboard ${projectName}:`, error);
            statusDiv.innerHTML = `<div class="text-red-400 bg-red-900/20 p-2 rounded">❌ Monitoring error</div>`;
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
const dashboardManager = new DashboardManager();
