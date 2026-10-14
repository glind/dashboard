# Communications Module

> **LinkedIn, Slack, and Discord Integration with AI-Powered Prioritization**

The Communications module aggregates messages from multiple platforms and uses AI to prioritize them, helping you focus on what matters most.

## 🎯 Features

### Platform Integration
- **LinkedIn** - Messages and connection requests
- **Slack** - Direct messages and channel mentions
- **Discord** - DMs, mentions, and replies

### AI-Powered Features
- **Priority Analysis** - Urgent/High/Medium/Low classification
- **Action Suggestions** - AI recommendations for responses
- **Sentiment Detection** - Understand message tone
- **Smart Filtering** - Filter by platform, priority, or time

### Authentication Options
- 🔐 **OAuth 2.0** - Secure login flow (recommended)
- 🔑 **Manual Tokens** - Direct API token entry
- 💾 **Database Storage** - Credentials stored securely
- 🔄 **Auto-Refresh** - Tokens refresh automatically

### Key Capabilities
- 📱 Multi-platform aggregation
- 🤖 AI prioritization using your configured LLM
- 🔔 Real-time notifications for urgent messages
- 🔗 Direct links to reply on each platform
- 📊 Communication statistics and trends
- ⏱️ Time-based filtering (6h to 7 days)

---

## 🚀 Quick Start

### Option 1: OAuth Login (Recommended)

1. **Configure OAuth Apps** (one-time setup):
   - See [OAUTH_SETUP.md](./OAUTH_SETUP.md) for detailed instructions
   - Add `client_id` and `client_secret` to `config/credentials.yaml`

2. **Connect in Dashboard**:
   - Click **"Connections"** button in Communications widget
   - Click **"Connect with OAuth"** for each platform
   - Authorize when redirected
   - Done! ✅

### Option 2: Manual Token Entry

1. **Get API Tokens**:
   - Follow instructions in [OAUTH_SETUP.md](./OAUTH_SETUP.md#-manual-token-entry-alternative)

2. **Enter in Dashboard**:
   - Click **"Connections"** button
   - Click **"Enter Token Manually"**
   - Paste your token
   - Save! ✅

---

## 📝 Configuration

### OAuth Configuration (Recommended)

Edit `config/credentials.yaml`:

```yaml
# LinkedIn OAuth
linkedin:
  client_id: "YOUR_LINKEDIN_CLIENT_ID"
  client_secret: "YOUR_LINKEDIN_CLIENT_SECRET"

# Slack OAuth
slack:
  client_id: "YOUR_SLACK_CLIENT_ID"
  client_secret: "YOUR_SLACK_CLIENT_SECRET"

# Discord OAuth
discord:
  client_id: "YOUR_DISCORD_CLIENT_ID"
  client_secret: "YOUR_DISCORD_CLIENT_SECRET"
```

### Manual Token Configuration (Alternative)

```yaml
# LinkedIn Manual Token
linkedin:
  access_token: "YOUR_LINKEDIN_ACCESS_TOKEN"

# Slack Manual Token
slack:
  token: "xoxp-YOUR-SLACK-USER-TOKEN"

# Discord Manual Token
discord:
  token: "YOUR_DISCORD_BOT_TOKEN"
```

**See [OAUTH_SETUP.md](./OAUTH_SETUP.md) for complete setup instructions!**

---

## 🎨 Usage

### Dashboard Widget

The Communications widget shows:
- **Connection Status** - Green/red indicator for each platform
- **Message Counts** - Total messages per platform
- **Priority Bar** - Visual distribution of urgency levels
- **Message List** - All messages with smart filtering
- **Quick Actions** - AI-suggested response priorities

### Filtering Messages

Click filter buttons to view:
- **All** - All messages across platforms
- **Urgent** - Requires immediate attention
- **High** - Important, respond soon
- **Platform** - Filter by LinkedIn, Slack, or Discord

### Connecting Accounts

1. Click **"Connections"** button
2. Choose OAuth (secure) or Manual token entry
3. Follow the prompts
4. See green indicator when connected

### Disconnecting

1. Click **"Connections"** button
2. Click **"Disconnect"** for any platform
3. Credentials are removed from database

---

## 🔧 API Endpoints

### Authentication

```bash
# Get connection status
GET /api/modules/comms/auth/status

# Initiate OAuth flow
GET /api/modules/comms/auth/{platform}/connect

# OAuth callbacks (automatic)
GET /api/modules/comms/auth/slack/callback
GET /api/modules/comms/auth/discord/callback
GET /api/modules/comms/auth/linkedin/callback

# Manual token entry
POST /api/modules/comms/auth/{platform}/manual
{
  "access_token": "token_here",
  "refresh_token": "refresh_token_here"  // optional
}

# Disconnect platform
DELETE /api/modules/comms/auth/{platform}/disconnect
```

### Data Collection

```bash
# Get all messages
GET /api/modules/comms/data?hours_back=24

# Get prioritized messages
POST /api/modules/comms/analyze
{
  "linkedin": [...],
  "slack": [...],
  "discord": [...]
}

# Analyze single message
POST /api/modules/comms/analyze-single
{
  "message_id": "123",
  "platform": "slack",
  "from_user": "john",
  "text": "Message text",
  "channel": "general"
}

# Health check
GET /api/modules/comms/health
```

---

## 🎓 How It Works

### 1. Authentication Flow

**OAuth (Recommended)**:
1. User clicks "Connect" in dashboard
2. Redirected to platform OAuth page
3. User authorizes access
4. Platform redirects back with authorization code
5. System exchanges code for access token
6. Token stored securely in database
7. Auto-refresh when expired (if supported)

**Manual Token**:
1. User obtains token from platform
2. Enters token in dashboard UI
3. Token stored in database
4. Works immediately

### 2. Data Collection
3. Select timeframe (default: 24 hours)
4. Click **Refresh** to load messages

### Priority Levels

Messages are automatically categorized:

- **🔴 Urgent** - Requires immediate attention
  - Questions from leadership
  - Time-sensitive requests
  - Critical notifications

- **🟠 High** - Important but not critical
  - Direct messages
  - @mentions from key people
  - Recent activity (< 6 hours)

- **🟡 Medium** - Regular priority
  - Channel mentions
  - General messages
  - Updates and information

- **⚪ Low** - Can wait
  - Non-urgent updates
  - FYI messages
  - Old notifications

### Filtering

Use the filter buttons to focus on specific messages:
- **All** - Show everything
- **Urgent** - Only urgent messages
- **High** - High priority only
- **LinkedIn** - LinkedIn messages only
- **Slack** - Slack messages only
- **Discord** - Discord messages only

### Reply to Messages

Click the **"Reply"** button on any message to open it in the native platform where you can respond.

---

## 🤖 AI Features

### Automatic Prioritization

The AI analyzes each message considering:
- **Sender importance** - Who sent it?
- **Time sensitivity** - When was it sent?
- **Action requirements** - Does it need a response?
- **Business impact** - How important is it?
- **Context** - Channel, conversation thread, etc.

### Suggested Actions

For top-priority messages, the AI suggests:
- **Immediate actions** - What to do right now
- **Response approach** - How to reply
- **Key points** - What to address

### Single Message Analysis

Click any message to get detailed AI insights:
- Sentiment analysis
- Key topics
- Questions/action items
- Response suggestions

---

## 🔧 API Endpoints

### Get All Communications
```bash
GET /api/modules/comms/data?hours_back=24
```

### Analyze with AI
```bash
POST /api/modules/comms/analyze?hours_back=24
```

### Platform-Specific
```bash
GET /api/modules/comms/platforms/linkedin?hours_back=24
GET /api/modules/comms/platforms/slack?hours_back=24
GET /api/modules/comms/platforms/discord?hours_back=24
```

### Analyze Single Message
```bash
POST /api/modules/comms/analyze-single
{
  "message_id": "123",
  "platform": "slack",
  "from_user": "john.doe",
  "text": "Can you review the proposal?",
  "channel": "#general"
}
```

---

## 📊 Data Structure

### Message Object
```json
{
  "id": "unique-message-id",
  "platform": "slack",
  "type": "mention",
  "from_user": "John Doe",
  "from_id": "U12345",
  "channel": "#engineering",
  "channel_id": "C67890",
  "text": "Message content...",
  "timestamp": "2025-12-10T14:30:00",
  "link": "https://slack.com/...",
  "priority": "high",
  "priority_reason": "Direct question from team lead",
  "action_needed": "Respond with status update",
  "raw": {...}
}
```

---

## 🛠️ Troubleshooting

### No Messages Appearing

1. **Check credentials**:
   ```bash
   cat config/credentials.yaml | grep -A 2 "linkedin\|slack\|discord"
   ```

2. **Verify API tokens**:
   - LinkedIn: Token must have messaging scope
   - Slack: Use User token (xoxp-), not Bot token
   - Discord: Bot must be in your servers

3. **Check logs**:
   ```bash
   tail -f dashboard.log | grep -i comms
   ```

### Authentication Errors

**LinkedIn**: Token expired (valid for 60 days)
- Regenerate token in LinkedIn Developer portal

**Slack**: Invalid scopes
- Add missing scopes in Slack App settings
- Reinstall app to workspace

**Discord**: Bot not in server
- Use OAuth URL to invite bot
- Grant required permissions

### Messages Not Prioritized

- **AI not configured**: Check AI settings in dashboard
- **Ollama not running**: Start Ollama if using local LLM
- **Fallback mode**: Basic rules used if AI fails

---

## 🔒 Security & Privacy

### Token Security
- Tokens stored in `config/credentials.yaml` (gitignored)
- Never commit credentials to git
- Rotate tokens regularly

### Data Handling
- Messages cached temporarily for AI analysis
- No permanent storage of message content
- Links point to original platforms

### Best Practices
- Use read-only tokens when possible
- Limit bot permissions to necessary channels
- Review OAuth scopes regularly
- Enable 2FA on all accounts

---

## 🚀 Advanced Usage

### Customize Priority Rules

Edit `src/modules/comms/processor.py` to adjust:
- Priority keywords
- Sender importance
- Time sensitivity thresholds
- Action detection patterns

### Add More Platforms

Follow the module pattern to add:
1. Create collector method in `collector.py`
2. Add credentials to `credentials.yaml`
3. Update frontend to display new platform

### Webhook Integration

Configure webhooks for real-time notifications:
- Slack: Incoming webhooks
- Discord: Webhook URLs
- Custom: POST to `/api/modules/comms/webhook`

---

## 📈 Future Enhancements

Planned features:
- [ ] Auto-reply suggestions
- [ ] Message templates
- [ ] Scheduled sending
- [ ] Team collaboration
- [ ] Analytics dashboard
- [ ] Email integration
- [ ] WhatsApp/Telegram support
- [ ] Mobile push notifications

---

## 🤝 Contributing

To improve the Communications module:

1. Add new platform integrations
2. Enhance AI prioritization logic
3. Improve UI/UX
4. Add tests
5. Update documentation

---

## 📄 License

Part of Personal Dashboard project - see main LICENSE.md

---

## 🆘 Support

- Check logs: `tail -f dashboard.log | grep comms`
- Test endpoint: `curl http://localhost:8008/api/modules/comms/health`
- Review credentials: `config/credentials.yaml`

For issues, check the main project documentation or create an issue.
