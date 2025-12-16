# Branch Protection Setup for FounderDashboard

## GitHub Plan Requirements

### ✅ Free Plan (Public Repositories)
GitHub Free now includes branch protection for **public repositories**! You can:
- Require pull requests before merging
- Require status checks
- Restrict who can push
- All the features below work on public repos

### 💰 Paid Plan Required (Private Repositories)
For **private repositories**, branch protection with PR requirements needs:
- GitHub Team ($4/user/month)
- GitHub Enterprise

### 🎯 Recommendation for FounderDashboard
Since this is going to the **Buildly Marketplace**, make the repository **public**. This gives you:
- ✅ Free branch protection
- ✅ Community contributions
- ✅ Better visibility in marketplace
- ✅ No cost for protection features

## Protecting the Main Branch

To require pull requests for the main branch on GitHub, follow these steps:

### Step 1: Navigate to Repository Settings
1. Go to: https://github.com/Buildly-Marketplace/FounderDashboard
2. Click on **Settings** tab (requires admin access)

### Step 2: Access Branch Protection Rules
1. In the left sidebar, click **Branches** (under "Code and automation")
2. Under "Branch protection rules", click **Add rule** or **Add classic branch protection rule**

### Step 3: Configure Protection Rules
1. **Branch name pattern**: Enter `master` (or `main` if using main branch)

2. **Protect matching branches** - Enable these settings:
   - ✅ **Require a pull request before merging**
     - ✅ Require approvals: 1 (or more, depending on team size)
     - ✅ Dismiss stale pull request approvals when new commits are pushed
     - ☐ Require review from Code Owners (optional)
     
   - ✅ **Require status checks to pass before merging** (optional)
     - If you have CI/CD set up, select required checks
     
   - ✅ **Require conversation resolution before merging** (recommended)
     - Ensures all comments are addressed
     
   - ✅ **Require signed commits** (optional, for extra security)
     
   - ✅ **Require linear history** (optional)
     - Prevents merge commits, forces rebase or squash
     
   - ✅ **Include administrators**
     - Even admins must follow these rules (recommended)
     
   - ☐ **Allow force pushes** (keep disabled)
     
   - ☐ **Allow deletions** (keep disabled)

3. Click **Create** or **Save changes**

### Recommended Configuration for FounderDashboard

```
Branch name pattern: master

✅ Require a pull request before merging
   ✅ Require approvals: 1
   ✅ Dismiss stale pull request approvals when new commits are pushed
   
✅ Require conversation resolution before merging

✅ Include administrators

❌ Allow force pushes (disabled)
❌ Allow deletions (disabled)
```

### After Setup

Once branch protection is enabled:

1. **Direct pushes to master are blocked**
   ```bash
   # This will fail:
   git push buildly-marketplace master
   # Error: Protected branch 'master' cannot be updated
   ```

2. **Create feature branches instead**
   ```bash
   git checkout -b feature/new-provider-support
   git add .
   git commit -m "Add new provider support"
   git push buildly-marketplace feature/new-provider-support
   ```

3. **Open pull request on GitHub**
   - Go to: https://github.com/Buildly-Marketplace/FounderDashboard/pulls
   - Click "New pull request"
   - Select your feature branch
   - Add description and submit
   - Request review from team member
   - Merge after approval

### Workflow Example

```bash
# 1. Create and switch to feature branch
git checkout -b feature/add-yahoo-provider

# 2. Make changes
# ... edit files ...

# 3. Commit changes
git add .
git commit -m "Add Yahoo provider support"

# 4. Push feature branch (not main/master)
git push buildly-marketplace feature/add-yahoo-provider

# 5. Open PR on GitHub web interface
# 6. Wait for review and approval
# 7. Merge via GitHub interface (Squash and merge recommended)

# 8. Update local master
git checkout master
git pull buildly-marketplace master

# 9. Delete feature branch
git branch -d feature/add-yahoo-provider
git push buildly-marketplace --delete feature/add-yahoo-provider
```

### Quick Access
- **Branch Protection Settings**: https://github.com/Buildly-Marketplace/FounderDashboard/settings/branches
- **Pull Requests**: https://github.com/Buildly-Marketplace/FounderDashboard/pulls

### Benefits of Branch Protection

✅ Code review requirement ensures quality
✅ Prevents accidental direct pushes to main branch
✅ Creates audit trail of all changes
✅ Encourages discussion and collaboration
✅ Reduces bugs through peer review
✅ Maintains clean git history

### Alternative: No-Cost Branch Protection Workarounds

If you have a **private repository** and don't want to pay for GitHub Team, here are alternatives:

#### Option 1: Make Repository Public (Recommended)
```bash
# Repository Settings → General → Danger Zone → Change visibility → Make public
```
**Pros**: Free branch protection, community contributions, marketplace visibility
**Cons**: Code is public (but it's open source anyway per BSL-1.1 license)

#### Option 2: Use GitHub Actions to Enforce PR Workflow
Create `.github/workflows/enforce-pr.yml`:
```yaml
name: Enforce PR Workflow
on:
  push:
    branches: [master]

jobs:
  check-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Check if push is from PR
        run: |
          if [ -z "${{ github.event.pull_request }}" ]; then
            echo "❌ Direct pushes to master are not allowed!"
            echo "Please create a pull request instead."
            exit 1
          fi
```

#### Option 3: Git Hooks (Local Enforcement)
Create `.git/hooks/pre-push`:
```bash
#!/bin/bash
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" = "master" ]; then
    echo "❌ Direct push to master is not allowed!"
    echo "Please create a feature branch and pull request."
    exit 1
fi
```

**Note**: Git hooks are local only and can be bypassed.

#### Option 4: Use GitLab (Free Alternative)
GitLab offers branch protection on free plans for private repos:
- Mirror your GitHub repo to GitLab
- Use GitLab for development (free branch protection)
- Auto-sync to GitHub for releases

#### Option 5: Team Process Agreement
For small teams without paid plans:
1. Agree to always use feature branches
2. Self-review checklist before merging
3. Document process in CONTRIBUTING.md
4. Use PR templates to standardize reviews

### Troubleshooting

**Q: My repository is private and I can't enable branch protection**
A: Either make it public (recommended for marketplace) or use the workarounds above.

**Q: I accidentally pushed directly to master before protection was set up**
A: That's okay! Protection only applies going forward. Past commits remain.

**Q: I need to make an urgent hotfix**
A: Still use a branch. You can mark PR as urgent and merge immediately after quick review.

**Q: Can I bypass protection rules?**
A: Only if "Include administrators" is unchecked, but this is not recommended for production repositories.

**Q: What if I'm the only developer?**
A: Branch protection is still valuable! It enforces good habits and provides rollback safety.
