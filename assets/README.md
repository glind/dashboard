# Asset Placeholders

This directory should contain:

## Required Assets

### 1. Logo
**File:** `logo-512.png`
- **Size:** 512x512 pixels
- **Format:** PNG with transparency
- **Style:** Dashboard icon with AI/productivity theme
- **Colors:** Match dark theme (blues, purples, teals)

### 2. Screenshots

#### screenshot-overview.png
- **Content:** Dashboard overview page showing all sections
- **Features to highlight:**
  - Multiple data cards (emails, calendar, tasks, weather)
  - Dark theme aesthetic
  - Clean, modern UI
  - Data visualization

#### screenshot-ai-assistant.png
- **Content:** AI Assistant page
- **Features to highlight:**
  - 5-minute overview summary at top (purple gradient card)
  - Personalized suggestions (green gradient card)
  - Task suggestions with like/dislike buttons
  - Chat interface

#### screenshot-tasks.png
- **Content:** Task management section
- **Features to highlight:**
  - Task cards with priority badges
  - Filter options (priority, source, status)
  - Started/Done checkboxes
  - Email-to-task integration indicator

## Specifications

- **Resolution:** Minimum 1920x1080
- **Format:** PNG (compressed for web)
- **Content:** Real or realistic data (avoid lorem ipsum)
- **Theme:** Dark mode (bg-gray-900)
- **Quality:** High resolution, clear text, professional appearance

## Creation Tips

1. **Use the running dashboard** - Take actual screenshots of the application
2. **Populate with sample data** - Ensure each section has content
3. **Highlight key features** - Show the most impressive capabilities
4. **Consistent branding** - Use the same color scheme throughout
5. **Clean and clear** - Avoid clutter, focus on main features

## To Create Assets

### Option 1: Screenshot the Running App
```bash
# Start dashboard
./ops/startup.sh

# Open in browser
open http://localhost:8008

# Take screenshots using:
# - macOS: Cmd+Shift+4
# - Windows: Win+Shift+S
# - Linux: Screenshot tool
```

### Option 2: Use Design Tool
- Figma, Sketch, or Photoshop
- Create mockups based on actual UI
- Export at 2x resolution for clarity

### Option 3: Commission Assets
- Fiverr, Upwork, or 99designs
- Provide this README and running dashboard URL
- Request deliverables matching specifications above

## Validation

Before committing, verify:
- [ ] logo-512.png exists and is exactly 512x512px
- [ ] All 3 screenshots exist and are high quality
- [ ] Screenshots show actual dashboard features
- [ ] Files are optimized (<500KB each)
- [ ] Images match dark theme aesthetic
- [ ] BUILDLY.yaml references are correct

## Current Status

🟡 **Placeholders only** - Real assets needed for marketplace listing

Replace this README with actual asset files before deploying to production or submitting to Buildly Forge.
