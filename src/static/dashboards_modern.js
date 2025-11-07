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
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
const dashboardManager = new DashboardManager();
