/**
 * Provider Management UI
 * Handles authentication and configuration for Google, Microsoft, and Proton providers
 */

class ProviderManager {
    constructor() {
        this.providers = [];
        this.init();
    }

    async init() {
        await this.loadProviders();
    }

    async loadProviders() {
        try {
            const response = await fetch('/api/providers/list');
            const data = await response.json();
            this.providers = data.providers || [];
            this.renderProviders();
        } catch (error) {
            console.error('Error loading providers:', error);
            this.showNotification('Failed to load providers', 'error');
        }
    }

    renderProviders() {
        const container = document.getElementById('providers-list');
        if (!container) return;

        if (this.providers.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <p class="mb-4">No providers configured yet</p>
                    <button onclick="providerManager.showAddProviderModal()" 
                            class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">
                        Add Your First Provider
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = this.providers.map(provider => this.renderProviderCard(provider)).join('');
    }

    renderProviderCard(provider) {
        const statusColor = provider.authenticated ? 'bg-green-600' : 'bg-red-600';
        const statusText = provider.authenticated ? 'Connected' : 'Not Connected';
        const providerIcon = this.getProviderIcon(provider.type);
        const capabilities = provider.capabilities.map(cap => 
            `<span class="text-xs bg-gray-700 px-2 py-1 rounded">${cap}</span>`
        ).join(' ');

        return `
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-4">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-3">
                        <div class="text-3xl">${providerIcon}</div>
                        <div>
                            <h3 class="font-semibold text-white">${provider.name}</h3>
                            <p class="text-sm text-gray-400">${provider.type}</p>
                        </div>
                    </div>
                    <span class="text-xs ${statusColor} px-2 py-1 rounded">${statusText}</span>
                </div>
                
                <div class="flex gap-2 mb-3">
                    ${capabilities}
                </div>
                
                <div class="flex gap-2">
                    ${!provider.authenticated ? `
                        <button onclick="providerManager.authenticateProvider('${provider.id}', '${provider.type}')" 
                                class="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1 rounded">
                            Connect
                        </button>
                    ` : `
                        <button onclick="providerManager.testProvider('${provider.id}')" 
                                class="bg-green-600 hover:bg-green-700 text-white text-sm px-3 py-1 rounded">
                            Test
                        </button>
                    `}
                    <button onclick="providerManager.removeProvider('${provider.id}')" 
                            class="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded">
                        Remove
                    </button>
                </div>
                
                ${provider.last_auth ? `
                    <p class="text-xs text-gray-500 mt-2">Last authenticated: ${new Date(provider.last_auth).toLocaleString()}</p>
                ` : ''}
            </div>
        `;
    }

    getProviderIcon(type) {
        const icons = {
            'google': '📧',
            'microsoft': '📨',
            'proton': '🔒'
        };
        return icons[type] || '📬';
    }

    showAddProviderModal() {
        const modal = document.getElementById('add-provider-modal') || this.createAddProviderModal();
        modal.classList.remove('hidden');
    }

    createAddProviderModal() {
        const modal = document.createElement('div');
        modal.id = 'add-provider-modal';
        modal.className = 'hidden fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4';
        modal.innerHTML = `
            <div class="bg-gray-900 border border-gray-700 rounded-lg max-w-md w-full p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xl font-bold text-white">Add Email Provider</h2>
                    <button onclick="providerManager.closeAddProviderModal()" class="text-gray-400 hover:text-white">
                        ✕
                    </button>
                </div>
                
                <form id="add-provider-form" onsubmit="providerManager.submitAddProvider(event)">
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-300 mb-2">Provider Type</label>
                        <select id="provider-type" class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white" required>
                            <option value="">Select provider...</option>
                            <option value="google">Google (Gmail, Calendar, Drive)</option>
                            <option value="microsoft">Microsoft (Outlook, Office 365)</option>
                            <option value="proton">Proton (ProtonMail via Bridge)</option>
                        </select>
                    </div>
                    
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-300 mb-2">Name This Account</label>
                        <input type="text" id="provider-name" 
                               placeholder="e.g., Work Email, Personal Gmail"
                               class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white" required>
                        <p class="text-xs text-gray-500 mt-1">Give this account a name to identify it</p>
                    </div>
                    
                    <div class="flex gap-2">
                        <button type="submit" class="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">
                            Add Provider
                        </button>
                        <button type="button" onclick="providerManager.closeAddProviderModal()" 
                                class="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        `;
        document.body.appendChild(modal);
        return modal;
    }

    closeAddProviderModal() {
        const modal = document.getElementById('add-provider-modal');
        if (modal) modal.classList.add('hidden');
    }

    async submitAddProvider(event) {
        event.preventDefault();
        
        const type = document.getElementById('provider-type').value;
        const name = document.getElementById('provider-name').value;
        
        try {
            const response = await fetch('/api/providers/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider_type: type,
                    provider_name: name,
                    config: {}
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                // Show detailed error if available
                if (data.detail && typeof data.detail === 'object') {
                    if (window.showDetailedError) {
                        window.showDetailedError(data.detail);
                        return;
                    }
                }
                throw new Error(typeof data.detail === 'string' ? data.detail : 'Failed to add provider');
            }
            
            this.showNotification('Provider added successfully!', 'success');
            this.closeAddProviderModal();
            await this.loadProviders();
            
            // Immediately prompt for authentication
            setTimeout(() => {
                this.authenticateProvider(data.provider_id, type);
            }, 500);
            
        } catch (error) {
            console.error('Error adding provider:', error);
            this.showNotification(error.message, 'error');
        }
    }

    async authenticateProvider(providerId, type) {
        try {
            const response = await fetch(`/api/providers/${providerId}/auth-url`);
            const data = await response.json();
            
            if (!response.ok) {
                // Show detailed error if available
                if (data.detail && typeof data.detail === 'object') {
                    if (window.showDetailedError) {
                        window.showDetailedError(data.detail);
                        return;
                    }
                }
                throw new Error(typeof data.detail === 'string' ? data.detail : 'Failed to get auth URL');
            }
            
            if (data.requires_credentials) {
                // Show Proton credentials form
                this.showProtonCredentialsModal(providerId);
            } else if (data.auth_url) {
                // Show instructions and open OAuth flow
                this.showNotification(data.instructions, 'info');
                
                // Open OAuth URL
                if (data.auth_url.startsWith('http')) {
                    window.location.href = data.auth_url;
                } else {
                    // Relative URL (Google)
                    window.location.href = data.auth_url;
                }
            }
            
        } catch (error) {
            console.error('Error authenticating provider:', error);
            this.showNotification(error.message, 'error');
        }
    }

    showProtonCredentialsModal(providerId) {
        const modal = document.getElementById('proton-credentials-modal') || this.createProtonCredentialsModal(providerId);
        modal.classList.remove('hidden');
        document.getElementById('proton-provider-id').value = providerId;
    }

    createProtonCredentialsModal(providerId) {
        const modal = document.createElement('div');
        modal.id = 'proton-credentials-modal';
        modal.className = 'hidden fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4';
        modal.innerHTML = `
            <div class="bg-gray-900 border border-gray-700 rounded-lg max-w-md w-full p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xl font-bold text-white">Proton Bridge Credentials</h2>
                    <button onclick="providerManager.closeProtonCredentialsModal()" class="text-gray-400 hover:text-white">
                        ✕
                    </button>
                </div>
                
                <div class="mb-4 bg-yellow-900 border border-yellow-700 rounded p-3 text-sm text-yellow-200">
                    <p class="font-semibold mb-1">⚠️ Proton Bridge Required</p>
                    <p>Make sure Proton Bridge is installed and running. Use the Bridge password, not your web password.</p>
                </div>
                
                <form id="proton-credentials-form" onsubmit="providerManager.submitProtonCredentials(event)">
                    <input type="hidden" id="proton-provider-id">
                    
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-300 mb-2">ProtonMail Email</label>
                        <input type="email" id="proton-username" 
                               placeholder="your@proton.me"
                               class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white" required>
                    </div>
                    
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-300 mb-2">Bridge Password</label>
                        <input type="password" id="proton-password" 
                               placeholder="Get from Bridge app settings"
                               class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white" required>
                        <p class="text-xs text-gray-500 mt-1">This is NOT your ProtonMail web password</p>
                    </div>
                    
                    <div class="flex gap-2">
                        <button type="submit" class="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">
                            Connect
                        </button>
                        <button type="button" onclick="providerManager.closeProtonCredentialsModal()" 
                                class="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        `;
        document.body.appendChild(modal);
        return modal;
    }

    closeProtonCredentialsModal() {
        const modal = document.getElementById('proton-credentials-modal');
        if (modal) modal.classList.add('hidden');
    }

    async submitProtonCredentials(event) {
        event.preventDefault();
        
        const providerId = document.getElementById('proton-provider-id').value;
        const username = document.getElementById('proton-username').value;
        const password = document.getElementById('proton-password').value;
        
        try {
            const response = await fetch(`/api/providers/${providerId}/credentials`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.detail || 'Failed to set credentials');
            
            this.showNotification('Proton connected successfully!', 'success');
            this.closeProtonCredentialsModal();
            await this.loadProviders();
            
        } catch (error) {
            console.error('Error setting Proton credentials:', error);
            this.showNotification(error.message, 'error');
        }
    }

    async removeProvider(providerId) {
        if (!confirm('Are you sure you want to remove this provider? This will delete all authentication data.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/providers/${providerId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Failed to remove provider');
            
            this.showNotification('Provider removed', 'success');
            await this.loadProviders();
            
        } catch (error) {
            console.error('Error removing provider:', error);
            this.showNotification(error.message, 'error');
        }
    }

    async testProvider(providerId) {
        try {
            this.showNotification('Testing connection...', 'info');
            
            const response = await fetch('/api/providers/emails?days=1');
            const data = await response.json();
            
            const providerEmails = data.by_provider[providerId] || 0;
            
            this.showNotification(`✅ Connected! Found ${providerEmails} recent emails`, 'success');
            
        } catch (error) {
            console.error('Error testing provider:', error);
            this.showNotification('Connection test failed', 'error');
        }
    }

    showNotification(message, type = 'info') {
        if (window.showNotification) {
            window.showNotification(message, type);
        } else {
            alert(message);
        }
    }
}

// Initialize provider manager
let providerManager;
document.addEventListener('DOMContentLoaded', () => {
    providerManager = new ProviderManager();
});
