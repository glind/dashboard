# Multi-Provider Email & Calendar Setup

## Quick Start

Your dashboard now supports multiple email and calendar providers! No code changes needed - everything is managed through the UI.

### Supported Providers

1. **Google** (Gmail, Google Calendar, Google Drive)
2. **Microsoft** (Outlook, Office 365 Calendar, OneNote)  
3. **Proton** (ProtonMail via Bridge)

### How to Add a Provider

1. **Open Dashboard**: http://localhost:8008
2. **Go to Email Providers**: Click "🔌 Email Providers" in the sidebar
3. **Click "Add Provider"**
4. **Choose provider type** and give it a name (e.g., "Work Email", "Personal Gmail")
5. **Click "Add Provider"** - you'll be prompted to authenticate

### Provider-Specific Setup

#### Google (Already Working!)
- Your existing Google authentication works as-is
- Just add a provider and click "Connect"

#### Microsoft Office 365

**First Time Setup:**
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **Azure Active Directory → App registrations → New registration**
3. **Application name**: Personal Dashboard
4. **Redirect URI**: `http://localhost:8008/auth/microsoft/callback`
5. Copy the **Application (client) ID**
6. Go to **Certificates & secrets** → Create new client secret
7. **Add to your `.env` file**:
   ```bash
   MICROSOFT_CLIENT_ID=your_client_id_here
   MICROSOFT_CLIENT_SECRET=your_client_secret_here
   ```
8. In Azure, go to **API permissions** → Add permissions → Microsoft Graph:
   - `Mail.Read`
   - `Calendars.Read`
   - `Notes.Read`
   - `offline_access`
9. Restart dashboard: `./ops/startup.sh stop && ./ops/startup.sh`

**Then in the dashboard:**
1. Add a new provider (type: Microsoft)
2. Click "Connect"
3. Authorize in the popup window

#### Proton Mail

**First Time Setup:**
1. Download & install [Proton Bridge](https://proton.me/mail/bridge)
2. Open Proton Bridge app
3. Log in with your ProtonMail account
4. Go to Bridge **Settings** → Note your Bridge IMAP password (different from web password!)

**Then in the dashboard:**
1. Add a new provider (type: Proton)
2. Click "Connect"
3. Enter your ProtonMail address and Bridge password
4. The dashboard will connect via IMAP

### Multiple Accounts

You can add multiple accounts from the same provider! Examples:
- "Personal Gmail" + "Work Gmail"
- "Work Outlook" + "School Outlook"
- Each account is tracked separately

### Using Your Connected Accounts

Once connected, your providers automatically:
- ✅ Collect emails (shown in "📧 Emails" section)
- ✅ Collect calendar events (shown in "📅 Calendar" section)
- ✅ Collect notes/documents (if supported)
- ✅ Show unified view of all accounts
- ✅ Auto-refresh tokens (no re-authentication needed)

### Troubleshooting

**"Failed to authenticate"**
- Google: Delete `tokens/google_credentials.json` and try again
- Microsoft: Check your client ID and secret in `.env`
- Proton: Make sure Bridge is running and use the Bridge password, not web password

**"Connection test failed"**
- Check your internet connection
- For Proton: Verify Bridge is running (`ps aux | grep proton`)
- Try removing and re-adding the provider

**"Provider not showing emails"**
- Click the provider's "Test" button
- Check the provider is marked as "Connected" (green badge)
- Look at browser console (F12) for errors

### Security Notes

- OAuth tokens are stored securely in the database
- All providers use read-only access (no sending/deleting)
- Microsoft and Google use industry-standard OAuth2
- Proton requires Bridge for security (keeps credentials on your machine)

### Environment Variables

Add these to your `.env` file:

```bash
# Microsoft Office 365
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret

# Proton (if using)
PROTON_USERNAME=your@proton.me
PROTON_PASSWORD=bridge_password_from_app
```

**Note**: Google credentials are handled automatically through the existing OAuth flow.

## API Endpoints

For developers, the provider system exposes these APIs:

- `GET /api/providers/list` - List all configured providers
- `GET /api/providers/status` - Authentication status
- `POST /api/providers/add` - Add new provider
- `DELETE /api/providers/{id}` - Remove provider
- `GET /api/providers/emails` - Collect emails from all providers
- `GET /api/providers/calendar` - Collect events from all providers
- `GET /auth/microsoft/callback` - Microsoft OAuth callback

## Need Help?

Check the full documentation: `devdocs/MULTI_PROVIDER_AUTH.md`
