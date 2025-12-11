# OAuth Setup Guide for Communications Module

This guide walks you through setting up OAuth authentication for LinkedIn, Slack, and Discord.

## 🔐 Why OAuth?

OAuth provides:
- **Security**: No need to store long-lived passwords
- **Controlled Access**: Grant only the permissions you need
- **Easy Revocation**: Disconnect anytime from the dashboard
- **Automatic Refresh**: Tokens refresh automatically when possible

## 🎯 Quick Start

1. **Configure OAuth Apps** (one-time setup per platform)
2. **Add credentials to config** (`config/credentials.yaml`)
3. **Click "Connect"** in dashboard Communications widget
4. **Authorize** the app when redirected to platform
5. **Done!** You'll be redirected back to dashboard

---

## 📘 Slack OAuth Setup

### Step 1: Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Enter:
   - **App Name**: `Personal Dashboard` (or your choice)
   - **Workspace**: Select your workspace
4. Click **"Create App"**

### Step 2: Configure OAuth & Permissions

1. In left sidebar, click **"OAuth & Permissions"**
2. Scroll to **"Redirect URLs"** section
3. Click **"Add New Redirect URL"**
4. Enter: `http://localhost:8008/api/modules/comms/auth/slack/callback`
5. Click **"Add"** then **"Save URLs"**

### Step 3: Add User Token Scopes

Scroll to **"Scopes"** → **"User Token Scopes"** section and add:

- `channels:history` - View messages in public channels
- `channels:read` - View basic channel info
- `groups:history` - View messages in private channels
- `im:history` - View direct messages
- `im:read` - View DM info
- `mpim:history` - View group DM messages
- `search:read` - Search workspace messages
- `users:read` - View user info

### Step 4: Install to Workspace

1. Scroll to top and click **"Install to Workspace"**
2. Review permissions and click **"Allow"**
3. You'll see the **User OAuth Token** (starts with `xoxp-`)

### Step 5: Get OAuth Credentials

1. In left sidebar, click **"Basic Information"**
2. Under **"App Credentials"**, find:
   - **Client ID**: Copy this
   - **Client Secret**: Click "Show" then copy

### Step 6: Add to Config

Edit `config/credentials.yaml`:

```yaml
slack:
  client_id: "1234567890.1234567890"
  client_secret: "abc123def456ghi789jkl012mno345pq"
```

### Step 7: Connect in Dashboard

1. Open dashboard
2. Click **"Connections"** button in Communications widget
3. Click **"Connect with OAuth"** for Slack
4. Authorize the app
5. You'll be redirected back - connected! ✅

---

## 💬 Discord OAuth Setup

### Step 1: Create Discord Application

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Enter name: `Personal Dashboard` (or your choice)
4. Accept terms and click **"Create"**

### Step 2: Configure OAuth2

1. In left sidebar, click **"OAuth2"** → **"General"**
2. Under **"Redirects"**, click **"Add Redirect"**
3. Enter: `http://localhost:8008/api/modules/comms/auth/discord/callback`
4. Click **"Save Changes"**

### Step 3: Get OAuth Credentials

On the same OAuth2 page:
- **Client ID**: Copy this
- **Client Secret**: Click "Reset Secret" then copy the new secret

### Step 4: Create Bot (Optional but Recommended)

1. In left sidebar, click **"Bot"**
2. Click **"Add Bot"** → **"Yes, do it!"**
3. Enable these Privileged Gateway Intents:
   - **Message Content Intent** ✓
4. Click **"Save Changes"**

### Step 5: Add to Config

Edit `config/credentials.yaml`:

```yaml
discord:
  client_id: "1234567890123456789"
  client_secret: "ABC123def456GHI789jkl012MNO345pqr"
```

### Step 6: Connect in Dashboard

1. Open dashboard
2. Click **"Connections"** in Communications widget
3. Click **"Connect with OAuth"** for Discord
4. Select servers and click **"Authorize"**
5. Complete CAPTCHA if prompted
6. Connected! ✅

---

## 💼 LinkedIn OAuth Setup

### Step 1: Create LinkedIn App

1. Go to [https://www.linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Click **"Create app"**
3. Fill in:
   - **App name**: `Personal Dashboard`
   - **LinkedIn Page**: Select or create one
   - **Privacy policy URL**: Your URL (required)
   - **App logo**: Upload logo (256x256px min)
4. Check agreement box and click **"Create app"**

### Step 2: Request API Products

1. Go to **"Products"** tab
2. Request access to:
   - **Sign In with LinkedIn** - Click "Request access"
   - **Messaging API** - Click "Request access"
3. Wait for approval (usually instant for Sign In, may take time for Messaging)

### Step 3: Configure OAuth 2.0

1. Go to **"Auth"** tab
2. Under **"OAuth 2.0 settings"**, find **"Redirect URLs"**
3. Click **"Add redirect URL"**
4. Enter: `http://localhost:8008/api/modules/comms/auth/linkedin/callback`
5. Click **"Update"**

### Step 4: Get OAuth Credentials

On the Auth tab:
- **Client ID**: Copy this
- **Client Secret**: Copy this (click eye icon to reveal)

### Step 5: Configure Scopes

Ensure these scopes are selected:
- `r_liteprofile` - View basic profile
- `r_emailaddress` - View email
- `r_messaging` - Read messages

### Step 6: Add to Config

Edit `config/credentials.yaml`:

```yaml
linkedin:
  client_id: "abcdefghijk123"
  client_secret: "ABCDefgh123456"
```

### Step 7: Connect in Dashboard

1. Open dashboard
2. Click **"Connections"** in Communications widget
3. Click **"Connect with OAuth"** for LinkedIn
4. Sign in to LinkedIn and authorize
5. Connected! ✅

---

## 🔑 Manual Token Entry (Alternative)

If OAuth setup is too complex, you can manually enter API tokens:

### Slack Manual Token

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Create app → OAuth & Permissions → Install to workspace
3. Copy **User OAuth Token** (starts with `xoxp-`)
4. In dashboard, click **"Enter Token Manually"**
5. Paste token and save

### Discord Manual Token

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Create app → Bot → Copy token
3. Invite bot to your servers
4. In dashboard, click **"Enter Token Manually"**
5. Paste token and save

### LinkedIn Manual Token

1. Go to [https://www.linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Create app → Request Messaging API access
3. Use OAuth 2.0 tools to generate access token
4. In dashboard, click **"Enter Token Manually"**
5. Paste token and save

**Note**: Manual tokens may expire and need to be renewed.

---

## 🛠️ Troubleshooting

### "OAuth not configured" Error

**Problem**: OAuth credentials not set in config.

**Solution**: Add `client_id` and `client_secret` to `config/credentials.yaml`

### Redirect URL Mismatch

**Problem**: OAuth redirect URL doesn't match what's configured in app.

**Solution**: Ensure redirect URL is exactly:
- Slack: `http://localhost:8008/api/modules/comms/auth/slack/callback`
- Discord: `http://localhost:8008/api/modules/comms/auth/discord/callback`
- LinkedIn: `http://localhost:8008/api/modules/comms/auth/linkedin/callback`

### "Invalid state token" Error

**Problem**: CSRF token expired or modified.

**Solution**: Try connecting again. State tokens expire after 10 minutes.

### No Messages Showing

**Problem**: Connected but no messages appear.

**Solution**: 
1. Check connection indicator is green
2. Adjust timeframe (try "Last 72 hours")
3. Verify you have messages/mentions in that timeframe
4. Check browser console for errors

### Token Expired

**Problem**: Token no longer works.

**Solution**:
1. Click "Disconnect" in dashboard
2. Click "Connect" again to refresh token
3. Or manually enter a new token

---

## 🔒 Security Best Practices

1. **Never commit** `credentials.yaml` to version control
2. **Use OAuth** instead of long-lived tokens when possible
3. **Grant minimum permissions** - only add scopes you actually need
4. **Rotate tokens** periodically for manual entries
5. **Revoke access** from platform settings if you suspect compromise

---

## 📚 Additional Resources

- **Slack API Docs**: [https://api.slack.com/docs](https://api.slack.com/docs)
- **Discord Developer Portal**: [https://discord.com/developers/docs](https://discord.com/developers/docs)
- **LinkedIn API Docs**: [https://docs.microsoft.com/en-us/linkedin/](https://docs.microsoft.com/en-us/linkedin/)

---

## ✅ Verification Checklist

After setup, verify everything works:

- [ ] Connection indicator shows green dot
- [ ] Platform stats show message counts
- [ ] Messages appear in the list
- [ ] Can filter by platform
- [ ] Priority levels are assigned
- [ ] Reply links work
- [ ] Can disconnect/reconnect successfully

---

**Need Help?** Check the logs in `dashboard.log` for detailed error messages.
