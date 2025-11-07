"""
GitHub data collector for fetching issues, commits, and activity.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

import httpx

# Import database functions
try:
    from database import get_credentials
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class GitHubCollector:
    """Collects data from GitHub using their API."""
    
    def __init__(self, settings):
        """Initialize GitHub collector with settings."""
        self.settings = settings
        self.base_url = "https://api.github.com"
        
    async def collect_issues(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Collect GitHub issues within the specified date range."""
        # Get credentials from database first, then settings
        token = None
        username = None
        
        if DATABASE_AVAILABLE:
            creds = get_credentials("github")
            if creds:
                token = creds.get("token")
                username = creds.get("username")
        
        if not token:
            token = getattr(self.settings.github, 'token', None)
        if not username:
            username = getattr(self.settings.github, 'username', None)
        
        if not token or not username:
            logger.warning("GitHub token or username not configured.")
            return []
        
        try:
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Format dates for GitHub API
            since = start_date.isoformat()
            
            async with httpx.AsyncClient() as client:
                # Get user's repositories
                repos_response = await client.get(
                    f"{self.base_url}/user/repos",
                    headers=headers,
                    params={"type": "all", "per_page": 100}
                )
                repos_response.raise_for_status()
                repos = repos_response.json()
                
                all_issues = []
                
                # Get issues from each repository
                for repo in repos[:20]:  # Limit to first 20 repos
                    try:
                        issues_response = await client.get(
                            f"{self.base_url}/repos/{repo['full_name']}/issues",
                            headers=headers,
                            params={
                                "state": "all",
                                "since": since,
                                "per_page": 50
                            }
                        )
                        
                        if issues_response.status_code == 200:
                            issues = issues_response.json()
                            
                            for issue in issues:
                                # Filter by date range
                                created_at = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
                                if start_date <= created_at <= end_date:
                                    issue_data = self._process_issue(issue, repo)
                                    if issue_data:
                                        all_issues.append(issue_data)
                    
                    except Exception as e:
                        logger.warning(f"Error fetching issues for {repo['full_name']}: {e}")
                        continue
                
                logger.info(f"Collected {len(all_issues)} GitHub issues")
                return all_issues
                
        except Exception as e:
            logger.error(f"Error collecting GitHub issues: {e}")
            return []
    
    async def collect_commits(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Collect GitHub commits within the specified date range."""
        # Get credentials from database first, then settings
        token = None
        username = None
        
        if DATABASE_AVAILABLE:
            creds = get_credentials("github")
            if creds:
                token = creds.get("token")
                username = creds.get("username")
        
        if not token:
            token = getattr(self.settings.github, 'token', None)
        if not username:
            username = getattr(self.settings.github, 'username', None)
        
        if not token or not username:
            logger.warning("GitHub token or username not configured.")
            return []
        
        try:
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Format dates for GitHub API
            since = start_date.isoformat()
            until = end_date.isoformat()
            
            async with httpx.AsyncClient() as client:
                # Get user's repositories
                repos_response = await client.get(
                    f"{self.base_url}/user/repos",
                    headers=headers,
                    params={"type": "all", "per_page": 100}
                )
                repos_response.raise_for_status()
                repos = repos_response.json()
                
                all_commits = []
                
                # Get commits from each repository
                for repo in repos[:20]:  # Limit to first 20 repos
                    try:
                        commits_response = await client.get(
                            f"{self.base_url}/repos/{repo['full_name']}/commits",
                            headers=headers,
                            params={
                                "author": self.settings.github.username,
                                "since": since,
                                "until": until,
                                "per_page": 100
                            }
                        )
                        
                        if commits_response.status_code == 200:
                            commits = commits_response.json()
                            
                            for commit in commits:
                                commit_data = self._process_commit(commit, repo)
                                if commit_data:
                                    all_commits.append(commit_data)
                    
                    except Exception as e:
                        logger.warning(f"Error fetching commits for {repo['full_name']}: {e}")
                        continue
                
                logger.info(f"Collected {len(all_commits)} GitHub commits")
                return all_commits
                
        except Exception as e:
            logger.error(f"Error collecting GitHub commits: {e}")
            return []
    
    def _process_issue(self, issue: Dict[str, Any], repo: Dict[str, Any]) -> Dict[str, Any]:
        """Process a GitHub issue into our standard format."""
        try:
            created_at = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
            updated_at = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00'))
            
            closed_at = None
            if issue.get('closed_at'):
                closed_at = datetime.fromisoformat(issue['closed_at'].replace('Z', '+00:00'))
            
            issue_data = {
                'id': issue['id'],
                'number': issue['number'],
                'title': issue['title'],
                'body': issue.get('body', ''),
                'state': issue['state'],
                'created_at': created_at,
                'updated_at': updated_at,
                'closed_at': closed_at,
                'assignees': [assignee['login'] for assignee in issue.get('assignees', [])],
                'labels': [label['name'] for label in issue.get('labels', [])],
                'repository': repo['full_name'],
                'repository_url': repo['html_url'],
                'url': issue['html_url'],
                'author': issue['user']['login'],
                'is_pull_request': 'pull_request' in issue,
                'is_important': self._is_important_issue(issue)
            }
            
            return issue_data
            
        except Exception as e:
            logger.error(f"Error processing GitHub issue: {e}")
            return None
    
    def _process_commit(self, commit: Dict[str, Any], repo: Dict[str, Any]) -> Dict[str, Any]:
        """Process a GitHub commit into our standard format."""
        try:
            commit_date = datetime.fromisoformat(
                commit['commit']['author']['date'].replace('Z', '+00:00')
            )
            
            commit_data = {
                'sha': commit['sha'],
                'message': commit['commit']['message'],
                'author': commit['commit']['author']['name'],
                'author_email': commit['commit']['author']['email'],
                'date': commit_date,
                'repository': repo['full_name'],
                'repository_url': repo['html_url'],
                'url': commit['html_url'],
                'additions': 0,  # Would need separate API call to get stats
                'deletions': 0,  # Would need separate API call to get stats
                'files_changed': 0,  # Would need separate API call to get stats
                'is_merge': len(commit.get('parents', [])) > 1
            }
            
            return commit_data
            
        except Exception as e:
            logger.error(f"Error processing GitHub commit: {e}")
            return None
    
    def _is_important_issue(self, issue: Dict[str, Any]) -> bool:
        """Determine if an issue is important."""
        # Check labels for importance
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        important_labels = ['bug', 'critical', 'urgent', 'high priority', 'important']
        
        if any(label in important_labels for label in labels):
            return True
        
        # Check title for important keywords
        title = issue['title'].lower()
        important_keywords = ['critical', 'urgent', 'important', 'blocker', 'security']
        
        return any(keyword in title for keyword in important_keywords)
