# GitHub Integration

## Overview
GitHub integration shows your assigned issues, pull requests, and review requests directly on the dashboard.

## Features
- **Assigned Issues** - Issues assigned to you across all repositories
- **Pull Request Reviews** - PRs waiting for your review
- **Repository Activity** - Your recent activity and contributions
- **Organization Integration** - Works with personal and org repositories

## Setup

### 1. Personal Access Token
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with scopes:
   - `repo` - Full repository access
   - `read:user` - User information
   - `notifications` - Access to notifications

### 2. Configuration
Add to `config/credentials.yaml`:
```yaml
github:
  token: "ghp_your_token_here"
  username: "your_github_username"
```

Or store in database:
```python
from database import store_credentials
store_credentials('github', {
    'token': 'ghp_your_token_here',
    'username': 'your_username'
})
```

## API Endpoints

### GitHub Activity
```http
GET /api/github
```

Response:
```json
{
  "items": [
    {
      "type": "Review Requested",
      "title": "Add new authentication system",
      "repo": "my-project",
      "number": 42,
      "url": "https://github.com/user/my-project/pull/42"
    },
    {
      "type": "Issue Assigned", 
      "title": "Fix login bug",
      "repo": "webapp",
      "number": 15,
      "url": "https://github.com/user/webapp/issues/15"
    }
  ]
}
```

## Dashboard Display
Shows actionable GitHub items:
```
🐙 Review Requested: Add new auth system (my-project #42)
🐙 Issue Assigned: Fix login bug (webapp #15)  
🐙 Review Requested: Update documentation (docs #8)
```

## Search Queries Used

### Review Requests
```
review-requested:{username} is:open is:pr
```

### Assigned Issues  
```
assignee:{username} is:open
```

### Your Pull Requests
```
author:{username} is:open is:pr
```

## Data Processing
- Truncates long titles to 60 characters
- Extracts repository name from URL
- Orders by most recent activity
- Limits to most important 10 items

## Rate Limiting
- GitHub API: 5,000 requests/hour for authenticated users
- Dashboard caches results for 5 minutes
- Graceful fallback if rate limited

## Troubleshooting

### Common Issues
- **No data showing**: Check token permissions and username
- **"API rate limit exceeded"**: Wait or check token usage
- **Authentication failed**: Verify token is valid and not expired
- **Wrong repository data**: Check if token has repository access

### Debug Commands
```bash
# Test GitHub API directly
curl -H "Authorization: token YOUR_TOKEN" \
  "https://api.github.com/search/issues?q=assignee:USERNAME+is:open"

# Check token permissions
curl -H "Authorization: token YOUR_TOKEN" \
  "https://api.github.com/user"
```

### Token Management
```bash
# Check current token
cat config/credentials.yaml | grep github -A 2

# Test token validity  
curl -I -H "Authorization: token YOUR_TOKEN" \
  "https://api.github.com/user"
```

## Security Notes
- Store tokens securely (never commit to git)
- Use minimal required permissions
- Rotate tokens regularly
- Monitor token usage in GitHub settings

## Future Enhancements
- Notification badges for urgent items
- Direct action buttons (approve, merge)
- Repository health metrics
- Contribution streaks and statistics
