# Release Notes - v0.5.0 "Multi-Provider Edition"

**Release Date:** December 15, 2025  
**Repository:** https://github.com/Buildly-Marketplace/FounderDashboard

## 🎉 What's New in v0.5.0

### 🔌 Multi-Provider Authentication System
The headline feature of v0.5.0 is comprehensive multi-provider support for email, calendar, and notes with a user-friendly authentication UI.

**Supported Providers:**
- **Google** (Gmail, Google Calendar, Google Drive/Docs)
- **Microsoft** (Outlook, Office 365 Calendar, OneNote)
- **Proton** (ProtonMail via Proton Bridge)

**Key Features:**
- ✅ OAuth2 authentication flows for Google and Microsoft
- ✅ User-facing provider management UI - zero code changes required
- ✅ Multi-account support (add multiple accounts per provider)
- ✅ Provider status indicators (Connected/Not Connected)
- ✅ Test connection functionality
- ✅ Unified data collection across all providers
- ✅ Add/remove providers through dashboard UI
- ✅ Secure credential storage in database

**User Experience:**
1. Navigate to "🔌 Email Providers" in dashboard
2. Click "Add Provider" → Choose provider type → Name your account
3. Click "Connect" → Authenticate via OAuth popup or credentials form
4. Provider status updates to "Connected"
5. All emails, calendar events, and notes automatically aggregated

### 🔐 Trust Layer Enhancement
- Changed email scanning from automatic to on-demand per user preference
- Users control when trust analysis runs
- Improved UX for trust scoring workflow

### 🏗️ Architecture Improvements
- **Provider Abstraction Layer:** BaseProvider interface enables easy addition of new providers
- **ProviderManager:** Orchestrates multi-provider data collection
- **API Endpoints:** Complete REST API at `/api/providers/*` for CRUD operations
- **Database Schema:** New `provider_configs` table for provider storage
- **OAuth Handling:** Microsoft OAuth callback at `/auth/microsoft/callback`

### 📱 Desktop App
- Updated to v0.5.0
- App renamed to "FounderDashboard"
- Includes all multi-provider features
- macOS app bundle with Buildly branding

## 🛠️ Technical Details

### New Files
- `src/__version__.py` - Version metadata
- `src/providers/base.py` (267 lines) - Provider abstraction layer
- `src/providers/manager.py` (229 lines) - Multi-provider orchestrator
- `src/providers/google_provider.py` (430 lines) - Google integration
- `src/providers/microsoft_provider.py` (425 lines) - Microsoft Graph API
- `src/providers/proton_provider.py` (264 lines) - Proton Bridge/IMAP
- `src/modules/providers/endpoints.py` (448 lines) - Provider API
- `src/modules/providers/oauth.py` (67 lines) - OAuth callbacks
- `src/static/provider_manager.js` (362 lines) - Provider UI controller
- `PROVIDER_SETUP.md` - User setup guide
- `devdocs/MULTI_PROVIDER_AUTH.md` - Technical documentation

### Updated Files
- `src/templates/dashboard_modern.html` - Added Email Providers section
- `config/settings.py` - Added MicrosoftSettings and ProtonSettings
- `src/main.py` - Registered provider routers
- `BUILDLY.yaml` - Updated version and repository
- `build_desktop.sh` - Updated for v0.5.0

### API Endpoints
- `GET /api/providers/list` - List all configured providers
- `POST /api/providers/add` - Add new provider
- `DELETE /api/providers/{id}` - Remove provider
- `GET /api/providers/{id}/auth-url` - Get OAuth URL
- `POST /api/providers/{id}/credentials` - Set Proton credentials
- `GET /api/providers/status` - Check authentication status
- `GET /api/providers/emails` - Collect emails from all providers
- `GET /api/providers/calendar` - Collect calendar events

### Database Schema
```sql
CREATE TABLE provider_configs (
    provider_id TEXT PRIMARY KEY,
    provider_name TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    capabilities TEXT,
    config_data TEXT,
    last_auth_date TEXT,
    created_at TEXT,
    updated_at TEXT
);
```

## 📋 Requirements

### Python Dependencies
No new Python packages required beyond existing `requirements.txt`.

### Environment Variables (Optional)
For Microsoft provider:
```bash
MICROSOFT_CLIENT_ID=your_azure_app_client_id
MICROSOFT_CLIENT_SECRET=your_azure_app_client_secret
```

For Proton provider:
- Requires Proton Bridge installed and running
- Bridge credentials configured through UI

## 🚀 Installation & Upgrade

### From Previous Version
```bash
cd dashboard
git pull origin main
./ops/startup.sh
```

### Fresh Installation
```bash
git clone https://github.com/Buildly-Marketplace/FounderDashboard.git
cd FounderDashboard
./ops/startup.sh
```

### Desktop App (macOS)
```bash
./build_desktop.sh
open dist/FounderDashboard.app
```

## 📚 Documentation

- **Provider Setup Guide:** [PROVIDER_SETUP.md](PROVIDER_SETUP.md)
- **Technical Documentation:** [devdocs/MULTI_PROVIDER_AUTH.md](devdocs/MULTI_PROVIDER_AUTH.md)
- **Operations Guide:** [devdocs/OPERATIONS.md](devdocs/OPERATIONS.md)
- **Setup Instructions:** [devdocs/SETUP.md](devdocs/SETUP.md)

## 🔧 Configuration

### Google Provider
Uses existing OAuth setup. No additional configuration needed if already using Gmail integration.

### Microsoft Provider
1. Register app in Azure Portal
2. Get Client ID and Secret
3. Add to `.env`:
   ```
   MICROSOFT_CLIENT_ID=your_client_id
   MICROSOFT_CLIENT_SECRET=your_client_secret
   ```
4. Set redirect URI: `http://localhost:8008/auth/microsoft/callback`

### Proton Provider
1. Install Proton Bridge from proton.me/mail/bridge
2. Start Proton Bridge application
3. Get Bridge password from settings
4. Add provider through dashboard UI using Bridge credentials

## 🐛 Bug Fixes
- Fixed import paths for provider modules
- Improved error handling in OAuth flows
- Enhanced database initialization for provider tables
- Fixed trust layer auto-scanning behavior

## 🔒 Security
- OAuth tokens stored securely in database
- Credentials encrypted at rest
- No plaintext password storage
- Secure callback handling for OAuth flows

## ⚠️ Breaking Changes
None. This is a feature-additive release.

## 🎯 Migration Notes
- Existing Google authentication continues to work
- No configuration file changes required
- Database automatically migrated on startup
- Provider tables created automatically

## 🙏 Acknowledgments
- Built on the Buildly Platform
- Uses Microsoft Graph API for Office 365 integration
- Leverages Proton Bridge for ProtonMail access

## 📝 License
Business Source License 1.1 (BSL-1.1)  
Converts to Apache-2.0 on November 5, 2027

## 🔗 Links
- **Repository:** https://github.com/Buildly-Marketplace/FounderDashboard
- **Issues:** https://github.com/Buildly-Marketplace/FounderDashboard/issues
- **Documentation:** https://github.com/Buildly-Marketplace/FounderDashboard/tree/main/devdocs
- **Buildly Marketplace:** https://buildly.io/marketplace

## 🚦 What's Next (v0.6.0 Roadmap)
- Additional provider support (Yahoo, iCloud, FastMail)
- CalDAV provider integration
- Cross-provider deduplication
- Advanced filtering and rules
- Scheduled sync intervals
- Provider analytics and insights

---

**Full Changelog:** https://github.com/Buildly-Marketplace/FounderDashboard/compare/v0.4.0...v0.5.0
