# Communications Module - Quick Reference

## 🚀 Quick Setup

### Option 1: OAuth (3 minutes)
1. Create app at platform developer portal
2. Copy `client_id` and `client_secret`
3. Add to `config/credentials.yaml`
4. Dashboard → Connections → Connect

### Option 2: Manual Token (1 minute)
1. Get token from platform
2. Dashboard → Connections → Enter Token Manually
3. Paste and save

## 🔗 Platform Links

| Platform | Developer Portal | Docs |
|----------|-----------------|------|
| **Slack** | [api.slack.com/apps](https://api.slack.com/apps) | [OAuth Guide](https://api.slack.com/authentication/oauth-v2) |
| **Discord** | [discord.com/developers](https://discord.com/developers/applications) | [OAuth Docs](https://discord.com/developers/docs/topics/oauth2) |
| **LinkedIn** | [linkedin.com/developers](https://www.linkedin.com/developers/apps) | [Auth Guide](https://docs.microsoft.com/en-us/linkedin/shared/authentication/authentication) |

## 📝 Required Scopes

### Slack
- `channels:history` - View messages in public channels
- `channels:read` - View basic channel info
- `im:history` - View direct messages
- `search:read` - Search workspace messages
- `users:read` - View user info

### Discord
- `identify` - View user info
- `email` - Access email
- `messages.read` - Read messages

### LinkedIn
- `r_liteprofile` - Basic profile
- `r_emailaddress` - Email address
- `r_messaging` - Read messages

## 🔐 Redirect URLs

Add these exact URLs to your OAuth apps:

```
Slack:    http://localhost:8008/api/modules/comms/auth/slack/callback
Discord:  http://localhost:8008/api/modules/comms/auth/discord/callback
LinkedIn: http://localhost:8008/api/modules/comms/auth/linkedin/callback
```

For production, replace `localhost:8008` with your domain.

## ⚙️ Configuration

### OAuth Setup (Recommended)
```yaml
# config/credentials.yaml
slack:
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"

discord:
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"

linkedin:
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"
```

### Manual Token Setup (Alternative)
```yaml
# config/credentials.yaml
slack:
  token: "xoxp-YOUR-TOKEN"

discord:
  token: "YOUR_BOT_TOKEN"

linkedin:
  access_token: "YOUR_TOKEN"
```

## 🎯 API Endpoints

### Check Connection Status
```bash
curl http://localhost:8008/api/modules/comms/auth/status
```

### Get Messages
```bash
curl "http://localhost:8008/api/modules/comms/data?hours_back=24"
```

### Disconnect Platform
```bash
curl -X DELETE http://localhost:8008/api/modules/comms/auth/slack/disconnect
```

### Manual Token Entry
```bash
curl -X POST http://localhost:8008/api/modules/comms/auth/slack/manual \
  -H "Content-Type: application/json" \
  -d '{"access_token": "xoxp-your-token"}'
```

## 🔍 Troubleshooting

### "OAuth not configured"
→ Add `client_id` and `client_secret` to credentials.yaml

### Redirect URL Mismatch
→ Check URL is exactly: `http://localhost:8008/api/modules/comms/auth/{platform}/callback`

### No Messages Showing
→ Check connection indicator is green
→ Try longer timeframe (72 hours)
→ Check browser console for errors

### Token Expired
→ Disconnect and reconnect
→ OAuth tokens auto-refresh (if supported)
→ Manual tokens need renewal

## 📊 Priority Levels

| Level | Meaning | Examples |
|-------|---------|----------|
| 🔴 **Urgent** | Immediate attention | "URGENT:", "ASAP", from boss |
| 🟡 **High** | Important, respond soon | Direct questions, meetings |
| 🟢 **Medium** | Normal priority | General updates, FYI messages |
| ⚪ **Low** | Can wait | Notifications, bot messages |

## 🎨 UI Features

- **Green dot (●)** = Connected
- **Red dot (●)** = Not connected
- **Message count** = Total messages in timeframe
- **Priority bar** = Visual distribution
- **Filters** = Click to filter by platform/priority
- **Reply links** = Open native app to respond

## 📚 Full Documentation

- **Complete Setup Guide**: `src/modules/comms/OAUTH_SETUP.md`
- **Module README**: `src/modules/comms/README.md`
- **Config Template**: `config/credentials.yaml.example`

## 🆘 Getting Help

1. Check `dashboard.log` for error messages
2. Verify credentials in dashboard "Connections" modal
3. Test with manual token first (simpler)
4. Review platform API documentation
5. Check OAuth redirect URLs match exactly

## ✅ Success Checklist

- [ ] Created app on platform developer portal
- [ ] Added redirect URL to app config
- [ ] Added credentials to credentials.yaml
- [ ] Restarted dashboard
- [ ] Clicked "Connect" in dashboard
- [ ] Authorized app on platform
- [ ] See green connection indicator
- [ ] Messages appear in widget

---

**Dashboard URL**: http://localhost:8008
**Module Path**: `src/modules/comms/`
**Server Control**: `./ops/startup.sh restart`
