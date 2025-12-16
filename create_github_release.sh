#!/bin/bash

# GitHub Release Instructions for v0.5.0
# This script provides instructions for creating the release on GitHub

echo "=================================================="
echo "🚀 Founder Dashboard v0.5.0 Release Instructions"
echo "=================================================="
echo ""
echo "✅ Completed:"
echo "  - Version updated to 0.5.0"
echo "  - Desktop app built: dist/FounderDashboard.app"
echo "  - Code pushed to: https://github.com/Buildly-Marketplace/FounderDashboard"
echo "  - Tag v0.5.0 created and pushed"
echo "  - Release artifact created: dist/FounderDashboard-v0.5.0-macOS.zip"
echo ""
echo "📋 Next Steps to Complete GitHub Release:"
echo ""
echo "1. Go to: https://github.com/Buildly-Marketplace/FounderDashboard/releases/new"
echo ""
echo "2. Select tag: v0.5.0"
echo ""
echo "3. Release title: v0.5.0 - Multi-Provider Edition"
echo ""
echo "4. Copy release notes from: RELEASE_NOTES_v0.5.0.md"
echo "   Or use this summary:"
echo ""
echo "   ---START RELEASE NOTES---"
echo ""
cat << 'EOF'
# Release v0.5.0 - Multi-Provider Edition

**Release Date:** December 15, 2025

## 🎉 What's New

### 🔌 Multi-Provider Authentication System
- **Google** (Gmail, Google Calendar, Google Drive/Docs)
- **Microsoft** (Outlook, Office 365 Calendar, OneNote)  
- **Proton** (ProtonMail via Proton Bridge)

### Key Features
✅ OAuth2 authentication flows for Google and Microsoft
✅ User-facing provider management UI - zero code changes required
✅ Multi-account support (add multiple accounts per provider)
✅ Provider status indicators (Connected/Not Connected)
✅ Test connection functionality
✅ Unified data collection across all providers
✅ Add/remove providers through dashboard UI
✅ Secure credential storage in database

### 🔐 Trust Layer Enhancement
- Changed email scanning from automatic to on-demand
- Improved UX for trust scoring workflow

### 📱 Desktop App
- Updated to v0.5.0
- App renamed to "FounderDashboard"
- Includes all multi-provider features
- macOS app bundle with Buildly branding

## 📥 Installation

### Web Application
```bash
git clone https://github.com/Buildly-Marketplace/FounderDashboard.git
cd FounderDashboard
./ops/startup.sh
```

### Desktop App (macOS)
Download `FounderDashboard-v0.5.0-macOS.zip`, extract, and run `FounderDashboard.app`

## 📚 Documentation
- [Provider Setup Guide](PROVIDER_SETUP.md)
- [Technical Documentation](devdocs/MULTI_PROVIDER_AUTH.md)
- [Operations Guide](devdocs/OPERATIONS.md)

## 🔗 Links
- **Repository:** https://github.com/Buildly-Marketplace/FounderDashboard
- **Issues:** https://github.com/Buildly-Marketplace/FounderDashboard/issues
- **Buildly Marketplace:** https://buildly.io/marketplace

---

**Full Changelog:** https://github.com/Buildly-Marketplace/FounderDashboard/compare/v0.4.0...v0.5.0
EOF
echo ""
echo "   ---END RELEASE NOTES---"
echo ""
echo "5. Upload release assets:"
echo "   - dist/FounderDashboard-v0.5.0-macOS.zip (Desktop App for macOS)"
echo ""
echo "6. Check 'Set as the latest release'"
echo ""
echo "7. Click 'Publish release'"
echo ""
echo "=================================================="
echo ""
echo "📦 Release Artifacts Location:"
echo "  - Desktop App: $(pwd)/dist/FounderDashboard-v0.5.0-macOS.zip"
echo "  - Release Notes: $(pwd)/RELEASE_NOTES_v0.5.0.md"
echo ""
echo "🌟 After Publishing:"
echo "  - Update Buildly Marketplace listing"
echo "  - Announce on social media/blog"
echo "  - Send email to users about new features"
echo ""
echo "=================================================="
