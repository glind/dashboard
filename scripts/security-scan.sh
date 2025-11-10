#!/bin/bash

# Security scanning script to detect potential secrets and vulnerabilities
# Run this before every commit to catch security issues

set -e

echo "🔒 Running security scan..."
echo "================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Flag to track if any issues are found
ISSUES_FOUND=0

# Function to print results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        ISSUES_FOUND=1
    fi
}

# 1. Check for common secret patterns
echo "🔍 Scanning for secret patterns..."
SECRET_PATTERNS=(
    "sk-[a-zA-Z0-9]{48}"           # OpenAI API keys
    "ghp_[a-zA-Z0-9]{36}"          # GitHub Personal Access Tokens
    "github_pat_[a-zA-Z0-9_]+"     # GitHub PAT (new format)
    "GOCSPX-[a-zA-Z0-9_-]+"        # Google OAuth Client Secret
    "AIza[a-zA-Z0-9_-]{35}"        # Google API keys
    "[a-f0-9]{32}"                 # 32-char hex keys
    "AKIA[0-9A-Z]{16}"             # AWS Access Key IDs
    "xoxb-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}"  # Slack Bot tokens
)

for pattern in "${SECRET_PATTERNS[@]}"; do
    if git ls-files | xargs grep -l "$pattern" 2>/dev/null | grep -v ".example\|.template\|.md\|URGENT_SECURITY"; then
        echo -e "${RED}❌ Found potential secret pattern: $pattern${NC}"
        ISSUES_FOUND=1
    fi
done

# 2. Check that sensitive files are not tracked
echo ""
echo "🔍 Checking sensitive file tracking..."
SENSITIVE_FILES=(
    "src/config/credentials.yaml"
    "src/config/google_oauth_config.json" 
    ".env"
    "config/credentials.yaml"
    "config/google_oauth_config.json"
)

for file in "${SENSITIVE_FILES[@]}"; do
    if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
        echo -e "${RED}❌ Sensitive file is tracked: $file${NC}"
        ISSUES_FOUND=1
    else
        echo -e "${GREEN}✅ Sensitive file not tracked: $file${NC}"
    fi
done

# 3. Check .gitignore coverage
echo ""
echo "🔍 Checking .gitignore coverage..."
REQUIRED_IGNORES=(
    "credentials.yaml"
    "google_oauth_config.json"
    ".env"
    "*.key"
    "*.pem"
)

for pattern in "${REQUIRED_IGNORES[@]}"; do
    if grep -q "$pattern" .gitignore; then
        echo -e "${GREEN}✅ .gitignore covers: $pattern${NC}"
    else
        echo -e "${YELLOW}⚠️  Consider adding to .gitignore: $pattern${NC}"
    fi
done

# 4. Check for common vulnerability patterns
echo ""
echo "🔍 Scanning for vulnerability patterns..."
VULN_PATTERNS=(
    "password.*=.*['\"][^'\"]+['\"]"     # Hardcoded passwords
    "eval\s*\("                          # Eval usage
    "exec\s*\("                          # Exec usage  
    "shell=True"                         # Shell injection risk
    "subprocess.*shell=True"             # Subprocess shell risk
)

for pattern in "${VULN_PATTERNS[@]}"; do
    matches=$(git ls-files -z | xargs -0 grep -l "$pattern" 2>/dev/null | grep -v ".example\|.template\|.md\|security-scan.sh" || true)
    if [ -n "$matches" ]; then
        echo -e "${YELLOW}⚠️  Potential vulnerability pattern found: $pattern${NC}"
        echo "   Files: $matches"
    fi
done

# 5. Check for TODO security items
echo ""
echo "🔍 Checking for security TODOs..."
if git ls-files | xargs grep -n -i "TODO.*security\|FIXME.*security\|XXX.*security" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Security TODOs found - review before deployment${NC}"
fi

# Summary
echo ""
echo "================================"
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}🎉 Security scan passed! No critical issues found.${NC}"
    echo -e "${GREEN}✅ Safe to commit and push${NC}"
    exit 0
else
    echo -e "${RED}🚨 Security issues found! Address before committing.${NC}"
    echo ""
    echo "🔧 Remediation steps:"
    echo "1. Remove or mask any exposed secrets"
    echo "2. Add sensitive files to .gitignore"
    echo "3. Use environment variables or secure vaults"
    echo "4. Run: git filter-branch to clean history if needed"
    exit 1
fi