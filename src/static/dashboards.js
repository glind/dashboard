/**
 * Dashboard Management Interface
 * ============================
 * 
 * Handles discovery, starting, stopping, and monitoring of marketing dashboards and websites.
 * Provides real-time status updates and one-click management for all projects.
 */

class DashboardManager {
    constructor() {
        this.projects = [];
        this.refreshInterval = null;
        this.autoRefreshEnabled = true;
        this.refreshRate = 30000; // 30 seconds
    }

    /**
     * Initialize the dashboard manager
     */
    async init() {
        console.log('🚀 Initializing Dashboard Manager...');
        await this.loadDashboards();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    /**
     * Load all dashboards from database
     */
    async loadDashboards() {
        try {
            const response = await fetch('/api/dashboards');
            const data = await response.json();
            
            if (data.success) {
                this.projects = data.projects || [];
                
                console.log(`📊 Loaded ${this.projects.length} dashboard projects`);
                this.renderDashboardOverview();
                this.renderProjectCards();
            } else {
                this.showError('Failed to load dashboards');
            }
        } catch (error) {
            console.error('Error loading dashboards:', error);
            this.showError('Error loading dashboards: ' + error.message);
        }
    }

    /**
     * Render dashboard overview statistics
     */
    renderDashboardOverview() {
        const activeProjects = this.projects.filter(p => p.is_active).length;
        const totalProjects = this.projects.length;

        const overviewHtml = `
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div class="bg-gradient-to-r from-green-500 to-green-600 p-4 rounded-lg text-white">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="text-lg font-semibold">Active Projects</h3>
                            <p class="text-2xl font-bold">${activeProjects}</p>
                        </div>
                        <div class="text-3xl">✅</div>
                    </div>
                </div>
                
                <div class="bg-gradient-to-r from-blue-500 to-blue-600 p-4 rounded-lg text-white">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="text-lg font-semibold">Inactive Projects</h3>
                            <p class="text-2xl font-bold">${totalProjects - activeProjects}</p>
                        </div>
                        <div class="text-3xl">⏸️</div>
                    </div>
                </div>
                
                <div class="bg-gradient-to-r from-purple-500 to-purple-600 p-4 rounded-lg text-white">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="text-lg font-semibold">Total Projects</h3>
                            <p class="text-2xl font-bold">${totalProjects}</p>
                        </div>
                        <div class="text-3xl">📊</div>
                    </div>
                </div>
            </div>
            
            ${totalProjects === 0 ? `
            <div class="bg-gradient-to-r from-orange-500 to-pink-600 p-4 rounded-lg mb-4 text-white">
                <div class="flex items-start gap-3">
                    <div class="text-3xl">🎨</div>
                    <div class="flex-1">
                        <h3 class="text-lg font-bold mb-2">Get Started with ForgeWeb Marketing Websites</h3>
                        <p class="text-sm mb-3 opacity-90">
                            Download professional marketing websites from The Forge marketplace and monitor them here!
                        </p>
                        <div class="flex gap-2">
                            <a href="https://collab.buildly.io/marketplace/app/forgeweb/" 
                               target="_blank"
                               class="bg-white text-orange-600 hover:bg-gray-100 px-4 py-2 rounded text-sm font-semibold inline-flex items-center gap-2">
                                🔥 Browse ForgeWeb Marketplace
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                </svg>
                            </a>
                            <button onclick="dashboardManager.showSetupInstructions()" 
                                    class="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded text-sm font-semibold">
                                📖 Setup Guide
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            ` : ''}
            
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-white">Dashboard Projects</h2>
                <div class="flex gap-2">
                    <button onclick="showAddDashboardModal()" 
                            class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded text-sm">
                        ➕ Add Dashboard
                    </button>
                    <button onclick="dashboardManager.loadDashboards()" 
                            class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm">
                        🔄 Refresh
                    </button>
                    <button onclick="dashboardManager.toggleAutoRefresh()" 
                            class="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded text-sm">
                        ${this.autoRefreshEnabled ? '⏸️ Pause' : '▶️ Resume'} Auto-refresh
                    </button>
                </div>
            </div>
        `;

        const container = document.getElementById('dashboard-overview');
        if (container) {
            container.innerHTML = overviewHtml;
        }
    }

    /**
     * Render project cards
     */
    renderProjectCards() {
        const container = document.getElementById('dashboard-projects');
        if (!container) return;

        if (this.projects.length === 0) {
            container.innerHTML = '<p class="text-gray-400">No projects discovered</p>';
            return;
        }

        const projectsHtml = this.projects.map(project => this.renderProjectCard(project)).join('');
        container.innerHTML = projectsHtml;
    }

    /**
     * Render individual project card
     */
    renderProjectCard(project) {
        const activeStatus = project.is_active ? 'active' : 'inactive';
        const statusColor = project.is_active ? 'bg-green-500' : 'bg-gray-500';

        return `
            <div class="bg-gray-800 p-4 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <h3 class="font-semibold text-white">${project.name}</h3>
                        <p class="text-sm text-gray-400">${project.description || 'No description'}</p>
                        ${project.brand ? `<span class="inline-block bg-purple-600 text-white text-xs px-2 py-1 rounded mt-1">${project.brand}</span>` : ''}
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="w-3 h-3 ${statusColor} rounded-full"></span>
                        <span class="text-sm text-gray-300 capitalize">${activeStatus}</span>
                    </div>
                </div>
                
                <div class="flex flex-wrap gap-2 mb-3 text-xs text-gray-400">
                    <span class="bg-gray-700 px-2 py-1 rounded">${project.type || 'unknown'}</span>
                    ${project.port ? `<span class="bg-blue-700 px-2 py-1 rounded">Port: ${project.port}</span>` : ''}
                </div>
                
                <div class="flex gap-2">
                    ${project.url ? `
                        <button onclick="window.open('${project.url}', '_blank')" 
                                class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm flex-1">
                            🌐 Local
                        </button>
                    ` : ''}
                    
                    ${project.production_url ? `
                        <button onclick="window.open('${project.production_url}', '_blank')" 
                                class="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm flex-1">
                            🚀 Production
                        </button>
                    ` : ''}
                    
                    ${project.github_pages_url ? `
                        <button onclick="window.open('${project.github_pages_url}', '_blank')" 
                                class="bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded text-sm flex-1">
                            📄 GitHub Pages
                        </button>
                    ` : ''}
                    
                    <button onclick="showAddDashboardModal(${JSON.stringify(project).replace(/"/g, '&quot;')})" 
                            class="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded text-sm"
                            title="Edit Configuration">
                        ✏️
                    </button>
                    
                    <button onclick="dashboardManager.deleteProject('${project.name}')" 
                            class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm"
                            title="Delete">
                        🗑️
                    </button>
                </div>
                
                <div class="mt-2 text-xs text-gray-500">
                    Path: ${project.path || 'Not specified'}
                </div>
            </div>
        `;
    }

    /**
     * Delete a project from the database
     */
    async deleteProject(projectName) {
        if (!confirm(`Are you sure you want to delete "${projectName}"? This cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/dashboards/${projectName}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess(`${projectName} deleted successfully`);
                await this.loadDashboards(); // Refresh list
            } else {
                this.showError(`Failed to delete ${projectName}: ${data.error || data.detail}`);
            }
        } catch (error) {
            console.error(`Error deleting ${projectName}:`, error);
            this.showError(`Error deleting ${projectName}: ${error.message}`);
        }
    }

    /**
     * Show setup instructions for ForgeWeb websites
     */
    showSetupInstructions() {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        
        modal.innerHTML = `
            <div class="bg-gray-800 rounded-lg p-6 max-w-3xl w-full max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold text-white">🎨 ForgeWeb Setup Guide</h2>
                    <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-white text-2xl">&times;</button>
                </div>
                
                <div class="space-y-4 text-gray-300">
                    <div class="bg-gradient-to-r from-orange-500 to-pink-600 p-4 rounded-lg text-white">
                        <h3 class="font-bold text-lg mb-2">What is ForgeWeb?</h3>
                        <p class="text-sm opacity-90">
                            ForgeWeb provides professional, ready-to-deploy marketing websites for various brands and industries. 
                            Each website is fully customizable and production-ready!
                        </p>
                    </div>
                    
                    <div class="bg-gray-700 p-4 rounded-lg">
                        <h3 class="font-bold text-lg mb-3 text-white">📥 Step 1: Download from The Forge</h3>
                        <ol class="list-decimal list-inside space-y-2 text-sm">
                            <li>Visit <a href="https://collab.buildly.io/marketplace/app/forgeweb/" target="_blank" class="text-blue-400 hover:underline">The Forge Marketplace</a></li>
                            <li>Browse available ForgeWeb marketing websites</li>
                            <li>Click "Download" or "Clone" on the website you want</li>
                            <li>Save to your local directory (e.g., <code class="bg-gray-900 px-2 py-1 rounded">~/marketing/websites/</code>)</li>
                        </ol>
                    </div>
                    
                    <div class="bg-gray-700 p-4 rounded-lg">
                        <h3 class="font-bold text-lg mb-3 text-white">⚙️ Step 2: Set Up Locally</h3>
                        <ol class="list-decimal list-inside space-y-2 text-sm">
                            <li>Navigate to the downloaded website directory</li>
                            <li>Install dependencies (if needed): <code class="bg-gray-900 px-2 py-1 rounded">npm install</code></li>
                            <li>Test locally: <code class="bg-gray-900 px-2 py-1 rounded">npm start</code> or open <code class="bg-gray-900 px-2 py-1 rounded">index.html</code></li>
                            <li>Customize branding, colors, and content as needed</li>
                        </ol>
                    </div>
                    
                    <div class="bg-gray-700 p-4 rounded-lg">
                        <h3 class="font-bold text-lg mb-3 text-white">📊 Step 3: Add to This Dashboard</h3>
                        <ol class="list-decimal list-inside space-y-2 text-sm">
                            <li>Click the <span class="bg-green-600 px-2 py-1 rounded text-xs">➕ Add Dashboard</span> button above</li>
                            <li>Fill in the project details:
                                <ul class="list-disc list-inside ml-4 mt-1 space-y-1">
                                    <li><strong>Name:</strong> e.g., "OpenBuild Website"</li>
                                    <li><strong>Path:</strong> Full path to the website directory</li>
                                    <li><strong>Type:</strong> Choose the framework (static, react, vue, etc.)</li>
                                    <li><strong>Port:</strong> Local development port (if applicable)</li>
                                    <li><strong>Production URL:</strong> Your live website URL</li>
                                    <li><strong>GitHub Pages URL:</strong> Your GitHub Pages URL (if using)</li>
                                </ul>
                            </li>
                            <li>Click <strong>Save</strong> to start monitoring!</li>
                        </ol>
                    </div>
                    
                    <div class="bg-gray-700 p-4 rounded-lg">
                        <h3 class="font-bold text-lg mb-3 text-white">🚀 Step 4: Deploy to Production</h3>
                        <ol class="list-decimal list-inside space-y-2 text-sm">
                            <li>Push your customized website to GitHub</li>
                            <li>Enable GitHub Pages in repository settings</li>
                            <li>Or deploy to Netlify, Vercel, or your own hosting</li>
                            <li>Update the Production URL in this dashboard</li>
                        </ol>
                    </div>
                    
                    <div class="bg-blue-900 bg-opacity-50 p-4 rounded-lg border border-blue-500">
                        <h3 class="font-bold text-lg mb-2 text-blue-300">💡 Pro Tips</h3>
                        <ul class="list-disc list-inside space-y-1 text-sm">
                            <li>Keep all websites in one directory for easy management</li>
                            <li>Use meaningful names that match your brands</li>
                            <li>Set custom domains for production deployments</li>
                            <li>Monitor both local and production URLs from this dashboard</li>
                        </ul>
                    </div>
                </div>
                
                <div class="flex gap-3 mt-6">
                    <a href="https://collab.buildly.io/marketplace/app/forgeweb/" 
                       target="_blank"
                       class="flex-1 bg-orange-600 hover:bg-orange-700 text-white px-4 py-3 rounded font-semibold text-center">
                        🔥 Browse ForgeWeb Marketplace
                    </a>
                    <button onclick="this.closest('.fixed').remove(); showAddDashboardModal();" 
                            class="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-3 rounded font-semibold">
                        ➕ Add Your First Dashboard
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    }

    /**
     * Toggle auto-refresh
     */
    toggleAutoRefresh() {
        if (this.autoRefreshEnabled) {
            this.stopAutoRefresh();
        } else {
            this.startAutoRefresh();
        }
        this.renderDashboardOverview(); // Update button text
    }

    /**
     * Start auto-refresh
     */
    startAutoRefresh() {
        this.autoRefreshEnabled = true;
        this.refreshInterval = setInterval(() => {
            console.log('🔄 Auto-refreshing dashboard status...');
            this.loadDashboards();
        }, this.refreshRate);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        this.autoRefreshEnabled = false;
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Listen for visibility changes to pause/resume auto-refresh
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopAutoRefresh();
            } else if (this.autoRefreshEnabled) {
                this.startAutoRefresh();
            }
        });
    }

    /**
     * Edit project configuration
     */
    /**
     * Show success message
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'error');
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const colors = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500'
        };

        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-4 py-2 rounded shadow-lg z-50`;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Global instance
let dashboardManager;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    dashboardManager = new DashboardManager();
    dashboardManager.init();
});