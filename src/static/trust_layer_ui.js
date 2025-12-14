/**
 * Trust Layer UI Integration
 * 
 * Provides UI components for displaying email trust reports
 */

class TrustLayerUI {
    constructor() {
        this.trustReports = new Map();
        this.loadingReports = new Set();
    }

    /**
     * Get or generate trust report for an email
     */
    async getTrustReport(emailData) {
        const reportKey = emailData.thread_id || emailData.id;
        
        // Return cached if available
        if (this.trustReports.has(reportKey)) {
            return this.trustReports.get(reportKey);
        }

        // Prevent duplicate requests
        if (this.loadingReports.has(reportKey)) {
            return null;
        }

        try {
            this.loadingReports.add(reportKey);

            // Try to get existing report first
            let response = await fetch(`/api/v1/trust/reports/${reportKey}`);
            
            if (!response.ok && response.status === 404) {
                // Generate new report
                response = await fetch('/api/v1/trust/reports', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        sender_email: emailData.sender || emailData.from,
                        sender_domain: (emailData.sender || emailData.from).split('@')[1],
                        subject: emailData.subject,
                        body_text: emailData.snippet || emailData.body || '',
                        body_html: emailData.body_html || '',
                        snippet: emailData.snippet || ''
                    })
                });
            }

            if (response.ok) {
                const report = await response.json();
                this.trustReports.set(reportKey, report);
                return report;
            }
        } catch (error) {
            console.error('Error fetching trust report:', error);
        } finally {
            this.loadingReports.delete(reportKey);
        }

        return null;
    }

    /**
     * Get trust badge HTML for email list
     */
    getTrustBadge(score, riskLevel) {
        if (score === null || score === undefined) {
            return '<button class="text-xs bg-gray-600 hover:bg-gray-500 px-2 py-1 rounded" onclick="trustUI.showTrustReport(this)" title="Click to scan this email for security issues">🛡️ Scan</button>';
        }

        let color = 'bg-green-600';
        let text = 'Trusted';
        let icon = '✅';

        if (riskLevel === 'high_risk' || score < 55) {
            color = 'bg-red-600';
            text = 'High Risk';
            icon = '⚠️';
        } else if (riskLevel === 'caution' || score < 80) {
            color = 'bg-yellow-600';
            text = 'Caution';
            icon = '⚡';
        }

        return `<button class="text-xs ${color} hover:opacity-80 px-2 py-1 rounded" 
                      onclick="trustUI.showTrustReport(this)" 
                      title="Trust Score: ${score}/100 - Click for details">${icon} ${text} (${score})</button>`;
    }

    /**
     * Show detailed trust report modal
     */
    async showTrustReport(buttonElement) {
        // Get email data from parent card
        const card = buttonElement.closest('[onclick*="showEmailDetail"]');
        if (!card) return;

        const emailId = card.onclick.toString().match(/'([^']+)'/)[1];
        const email = window.dataLoader.emails.find(e => e.id === emailId);
        if (!email) return;

        try {
            const report = await this.getTrustReport(email);
            this.showDetailedReport(report);
        } catch (error) {
            console.error('Error fetching trust report:', error);
            if (window.showNotification) {
                window.showNotification('Failed to load trust report. Please try again.', 'error');
            }
        }
    }

    /**
     * Show detailed report modal (internal helper)
     */
    showDetailedReport(report) {
        if (!report) {
            if (window.showNotification) {
                window.showNotification('Could not generate trust report', 'error');
            }
            return;
        }

        // Create modal if it doesn't exist
        const modal = document.getElementById('trust-report-modal') || this.createTrustModal();
        
        // Populate modal with report data
        document.getElementById('trust-modal-sender').textContent = report.email_data?.sender || 'Unknown';
        document.getElementById('trust-modal-subject').textContent = report.email_data?.subject || 'No subject';
        document.getElementById('trust-modal-score').textContent = report.score;
        document.getElementById('trust-modal-risk').textContent = this.formatRiskLevel(report.risk_level);
        document.getElementById('trust-modal-risk').className = `text-2xl font-bold ${this.getRiskColor(report.risk_level)}`;
        document.getElementById('trust-modal-summary').textContent = report.summary || 'No summary available';

        // Render findings
        this.renderFindings(report.findings);

        // Render signals/claims
        this.renderClaims(report.signals);

        // Show modal
        modal.classList.remove('hidden');
    }

    /**
     * Create trust report modal
     */
    createTrustModal() {
        const modal = document.createElement('div');
        modal.id = 'trust-report-modal';
        modal.className = 'hidden fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4';
        modal.innerHTML = `
            <div class="bg-gray-900 border border-gray-700 rounded-lg max-w-4xl w-full max-h-[90vh] flex flex-col">
                <!-- Header -->
                <div class="flex items-center justify-between p-6 border-b border-gray-700">
                    <div class="flex-1">
                        <h3 class="text-2xl font-bold text-white mb-1">🛡️ Trust Report</h3>
                        <div class="text-sm text-gray-400">
                            <div class="font-medium" id="trust-modal-sender"></div>
                            <div class="text-xs" id="trust-modal-subject"></div>
                        </div>
                    </div>
                    <button onclick="trustUI.closeTrustModal()" class="text-gray-400 hover:text-white text-3xl leading-none">&times;</button>
                </div>

                <!-- Content -->
                <div class="p-6 overflow-y-auto flex-1">
                    <!-- Score Card -->
                    <div class="bg-gray-800 rounded-lg p-6 mb-6 text-center">
                        <div class="text-6xl font-bold mb-2" id="trust-modal-score">--</div>
                        <div class="text-lg mb-2" id="trust-modal-risk">--</div>
                        <div class="text-sm text-gray-400">out of 100</div>
                    </div>

                    <!-- Summary -->
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold text-white mb-2">📝 Summary</h4>
                        <p class="text-gray-300" id="trust-modal-summary"></p>
                    </div>

                    <!-- Findings -->
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold text-white mb-3">🔍 Findings</h4>
                        <div id="trust-modal-findings" class="space-y-2"></div>
                    </div>

                    <!-- Technical Signals -->
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold text-white mb-3">🔧 Technical Signals</h4>
                        <div id="trust-modal-signals" class="space-y-2"></div>
                    </div>

                    <!-- Playbook Actions -->
                    <div class="bg-blue-900 bg-opacity-30 border border-blue-600 rounded-lg p-4">
                        <h4 class="text-lg font-semibold text-blue-300 mb-2">📋 Recommended Actions</h4>
                        <div id="trust-modal-actions" class="space-y-2 text-sm text-blue-200"></div>
                    </div>
                </div>

                <!-- Footer -->
                <div class="p-4 border-t border-gray-700 flex gap-2 justify-end">
                    <button onclick="trustUI.requestVerification()" 
                            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm">
                        Request LinkedIn Verification
                    </button>
                    <button onclick="trustUI.closeTrustModal()" 
                            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm">
                        Close
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
                this.closeTrustModal();
            }
        });

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeTrustModal();
            }
        });

        return modal;
    }

    /**
     * Render findings list
     */
    renderFindings(findings) {
        const container = document.getElementById('trust-modal-findings');
        if (!findings || findings.length === 0) {
            container.innerHTML = '<div class="text-gray-400 text-sm">No issues detected</div>';
            return;
        }

        container.innerHTML = findings.map(finding => {
            const severityColor = {
                high: 'bg-red-900 border-red-600 text-red-200',
                medium: 'bg-yellow-900 border-yellow-600 text-yellow-200',
                low: 'bg-blue-900 border-blue-600 text-blue-200'
            }[finding.severity] || 'bg-gray-800 border-gray-600 text-gray-300';

            const severityIcon = {
                high: '🚨',
                medium: '⚠️',
                low: 'ℹ️'
            }[finding.severity] || '•';

            return `
                <div class="border rounded p-3 ${severityColor}">
                    <div class="flex items-start gap-2">
                        <span class="text-lg">${severityIcon}</span>
                        <div class="flex-1">
                            <div class="font-semibold mb-1">${this.escapeHtml(finding.rule_name || 'Finding')}</div>
                            <div class="text-sm mb-2">${this.escapeHtml(finding.description)}</div>
                            ${finding.evidence ? `<div class="text-xs opacity-75 font-mono bg-black bg-opacity-30 p-2 rounded">${this.escapeHtml(finding.evidence)}</div>` : ''}
                            <div class="text-xs mt-2 opacity-75">Impact: ${finding.points_delta} points</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Render technical signals/claims
     */
    renderClaims(signals) {
        const container = document.getElementById('trust-modal-signals');
        if (!signals || (Array.isArray(signals) && signals.length === 0) || (typeof signals === 'object' && Object.keys(signals).length === 0)) {
            container.innerHTML = '<div class="text-gray-400 text-sm">No technical signals available</div>';
            return;
        }

        // Handle both array and object formats
        const signalsArray = Array.isArray(signals) ? signals : Object.entries(signals).map(([key, value]) => ({
            provider: key,
            claim_type: key,
            evidence: typeof value === 'object' ? value : {value}
        }));

        container.innerHTML = signalsArray.map(signal => {
            return `
                <div class="bg-gray-800 border border-gray-700 rounded p-3">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="text-sm font-semibold text-gray-300">${this.escapeHtml(signal.provider || signal.claim_type)}</span>
                        ${signal.confidence ? `<span class="text-xs bg-gray-700 px-2 py-0.5 rounded">${Math.round(signal.confidence * 100)}% confidence</span>` : ''}
                    </div>
                    <div class="text-sm text-gray-400">
                        ${this.formatSignalEvidence(signal.evidence)}
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Format signal evidence for display
     */
    formatSignalEvidence(evidence) {
        if (!evidence) return 'No details available';
        if (typeof evidence === 'string') return this.escapeHtml(evidence);
        
        return Object.entries(evidence).map(([key, value]) => {
            return `<div class="flex gap-2"><span class="text-gray-500">${this.escapeHtml(key)}:</span><span class="text-gray-300">${this.escapeHtml(String(value))}</span></div>`;
        }).join('');
    }

    /**
     * Close trust modal
     */
    closeTrustModal() {
        const modal = document.getElementById('trust-report-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    /**
     * Request verification (placeholder)
     */
    requestVerification() {
        this.showNotification('Verification request feature coming soon', 'info');
    }

    /**
     * Format risk level for display
     */
    formatRiskLevel(level) {
        const levels = {
            likely_ok: 'Likely OK',
            caution: 'Caution',
            high_risk: 'High Risk'
        };
        return levels[level] || level;
    }

    /**
     * Get color class for risk level
     */
    getRiskColor(level) {
        const colors = {
            likely_ok: 'text-green-400',
            caution: 'text-yellow-400',
            high_risk: 'text-red-400'
        };
        return colors[level] || 'text-gray-400';
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const colors = {
            success: 'bg-green-600',
            error: 'bg-red-600',
            info: 'bg-blue-600'
        };

        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-4 py-2 rounded shadow-lg z-50`;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => notification.remove(), 3000);
    }

    /**
     * Escape HTML
     */
    escapeHtml(unsafe) {
        if (!unsafe) return '';
        return String(unsafe)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Global instance
window.trustUI = new TrustLayerUI();
