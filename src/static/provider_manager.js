/**
 * Provider Manager for Email and Calendar Providers
 * Handles Google and Microsoft OAuth connections
 */

class ProviderManager {
    constructor() {
        this.providers = [];
        this.currentProvider = null;
    }

    async init() {
        console.log('Initializing ProviderManager...');
        await this.loadProviders();
        console.log('ProviderManager initialized');
    }

    async loadProviders() {
        try {
            const response = await fetch('/api/email/accounts');
            if (!response.ok) {
                console.warn('Could not load email accounts');
                this.providers = [];
                this.renderProviders();
                return;
            }
            const data = await response.json();
            
            // Flatten providers into a single array with type
            this.providers = [];
            ['google', 'microsoft'].forEach(type => {
                (data[type] || []).forEach(acc => {
                    this.providers.push({
                        name: acc.name,
                        type: type,
                        authenticated: true
                    });
                });
            });
            this.renderProviders();
        } catch (error) {
            console.error('Error loading providers:', error);
            this.providers = [];
            this.renderProviders();
        }
    }

    renderProviders() {
        const container = document.getElementById('providers-list');
        if (!container) return;

        if (this.providers.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <p class="mb-4">No email providers configured yet</p>
                    <p class="text-sm mb-4">Connect Google to sync your emails and calendar</p>
                    <button onclick="window.location.href='/auth/google'" 
                            class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">
                        Connect Google Account
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
                <div class="flex gap-2">
                    <button onclick="window.providerManager.switchToProvider('${provider.type}', '${provider.name}')" 
                            class="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1 rounded">
                        Switch
                    </button>
                    <button onclick="window.providerManager.testProvider('${provider.type}', '${provider.name}')" 
                            class="bg-gray-600 hover:bg-gray-700 text-white text-sm px-3 py-1 rounded">
                        Test
                    </button>
                    <button onclick="window.providerManager.disconnectProvider('${provider.type}', '${provider.name}')" 
                            class="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded">
                        Disconnect
                    </button>
                </div>
            </div>
        `;
    }

    getProviderIcon(type) {
        const icons = {
            'google': '📧',
            'microsoft': '📬',
            'icloud': '☁️'
        };
        return icons[type] || '📧';
    }

    async switchToProvider(type, name) {
        try {
            const response = await fetch('/api/email/switch-account', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: type, account_name: name })
            });
            
            if (response.ok) {
                this.currentProvider = { type, name };
                this.showNotification(`Switched to ${name}`, 'success');
                
                // Reload emails with new provider
                if (window.dataLoader && typeof window.dataLoader.loadEmails === 'function') {
                    window.dataLoader.loadEmails();
                }
            } else {
                this.showNotification('Failed to switch provider', 'error');
            }
        } catch (error) {
            console.error('Error switching provider:', error);
            this.showNotification('Error switching provider', 'error');
        }
    }

    async disconnectProvider(type, name) {
        if (!confirm(`Disconnect ${name}? This will remove the account connection.`)) {
            return;
        }
        
        try {
            const response = await fetch('/api/email/accounts', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: type, account_name: name })
            });
            
            if (response.ok) {
                this.showNotification(`Disconnected ${name}`, 'success');
                await this.loadProviders();
            } else {
                this.showNotification('Failed to disconnect provider', 'error');
            }
        } catch (error) {
            console.error('Error disconnecting provider:', error);
            this.showNotification('Error disconnecting provider', 'error');
        }
    }

    async testProvider(type, name) {
        try {
            this.showNotification('Testing connection...', 'info');
            
            const response = await fetch('/api/email/test-account', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: type, account_name: name })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`✅ Connection successful! Found ${data.email_count || 0} emails`, 'success');
            } else {
                this.showNotification(`❌ Connection failed: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            console.error('Error testing provider:', error);
            this.showNotification('Connection test failed', 'error');
        }
    }

    showNotification(message, type = 'info') {
        if (window.showNotification) {
            window.showNotification(message, type);
        } else {
            console.log(`[${type}] ${message}`);
            if (type === 'error') {
                alert(message);
            }
        }
    }
}

// Initialize provider manager immediately so it's available when needed
window.providerManager = new ProviderManager();

// Also initialize on DOMContentLoaded to attach event listeners
document.addEventListener('DOMContentLoaded', () => {
    if (window.providerManager) {
        window.providerManager.init();
    }
});

