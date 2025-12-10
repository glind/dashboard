#!/usr/bin/env python3
"""
Create the Buildly logo icon for the desktop app.
Based on the metal plate with bunny logo design - improved version.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Create a 1024x1024 icon (high resolution for macOS)
size = 1024
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background color - dark blue from the Buildly brand
bg_color = (45, 75, 105)  # Deeper blue

# Draw rounded rectangle background with gradient effect
corner_radius = 180
for i in range(20):
    offset = i * 3
    shade = bg_color[0] - i*2, bg_color[1] - i*2, bg_color[2] - i*2
    draw.rounded_rectangle(
        [(50 + offset, 50 + offset), (size-50 - offset, size-50 - offset)],
        radius=corner_radius - offset,
        outline=shade,
        width=2
    )

draw.rounded_rectangle(
    [(50, 50), (size-50, size-50)],
    radius=corner_radius,
    fill=bg_color
)

# Metal plate effect (lighter grey rectangle with more depth)
plate_margin = 140
plate_color = (110, 110, 115)
# Add depth with shadow
shadow_offset = 8
shadow_color = (30, 30, 35)
draw.rounded_rectangle(
    [(plate_margin + shadow_offset, plate_margin + shadow_offset), 
     (size-plate_margin + shadow_offset, size-plate_margin + shadow_offset)],
    radius=70,
    fill=shadow_color
)
# Main plate
draw.rounded_rectangle(
    [(plate_margin, plate_margin), (size-plate_margin, size-plate_margin)],
    radius=70,
    fill=plate_color,
    outline=(80, 80, 85),
    width=4
)

# Draw rivets/bolts in corners with more detail
rivet_positions = [
    (plate_margin + 50, plate_margin + 50),
    (size - plate_margin - 50, plate_margin + 50),
    (plate_margin + 50, size - plate_margin - 50),
    (size - plate_margin - 50, size - plate_margin - 50),
]
for x, y in rivet_positions:
    # Outer rivet
    draw.ellipse([(x-18, y-18), (x+18, y+18)], fill=(90, 90, 95), outline=(70, 70, 75), width=2)
    # Inner rivet
    draw.ellipse([(x-12, y-12), (x+12, y+12)], fill=(140, 140, 145))
    # Screw cross
    draw.line([(x-8, y), (x+8, y)], fill=(100, 100, 105), width=3)
    draw.line([(x, y-8), (x, y+8)], fill=(100, 100, 105), width=3)

# Draw bunny silhouette (cleaner, more recognizable)
bunny_color = (200, 200, 205)
center_x = size // 2
bunny_y = 280

# Bunny ears - more defined
# Left ear
ear_left = [
    (center_x - 85, bunny_y + 110),
    (center_x - 75, bunny_y + 10),
    (center_x - 50, bunny_y + 20),
    (center_x - 45, bunny_y + 100)
]
draw.polygon(ear_left, fill=bunny_color, outline=(180, 180, 185))

# Right ear  
ear_right = [
    (center_x + 45, bunny_y + 100),
    (center_x + 50, bunny_y + 20),
    (center_x + 75, bunny_y + 10),
    (center_x + 85, bunny_y + 110)
]
draw.polygon(ear_right, fill=bunny_color, outline=(180, 180, 185))

# Bunny head (more rounded)
head_y = bunny_y + 130
draw.ellipse(
    [(center_x - 70, head_y - 55), (center_x + 70, head_y + 75)],
    fill=bunny_color,
    outline=(180, 180, 185),
    width=2
)

# Eye - larger and more visible
draw.ellipse(
    [(center_x + 10, head_y + 5), (center_x + 35, head_y + 25)],
    fill=(50, 50, 55)
)
# Eye highlight
draw.ellipse(
    [(center_x + 20, head_y + 8), (center_x + 26, head_y + 14)],
    fill=(220, 220, 225)
)

# Bunny body - more proportional
body_y = head_y + 85
draw.ellipse(
    [(center_x - 80, body_y), (center_x + 80, body_y + 150)],
    fill=bunny_color,
    outline=(180, 180, 185),
    width=2
)

# Draw "buildly" text on the plate with better styling
try:
    # Try to use a system font
    font_size = 150
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", font_size)
        except:
            font = ImageFont.truetype("/System/Library/Fonts/SF-Pro.ttf", font_size)
except:
    # Fallback to default font
    font = ImageFont.load_default()

text = "buildly"
# Text shadow for depth
text_shadow_color = (50, 50, 55)
text_color = (220, 220, 225)

# Get text bounding box
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]

text_x = (size - text_width) // 2
text_y = body_y + 175

# Draw shadow
draw.text((text_x + 3, text_y + 3), text, fill=text_shadow_color, font=font)
# Draw main text
draw.text((text_x, text_y), text, fill=text_color, font=font)

# Save the icon
output_path = 'assets/buildly_logo.png'
os.makedirs('assets', exist_ok=True)
img.save(output_path)
print(f"✅ Created Buildly logo icon: {output_path}")
print(f"   Size: {size}x{size} pixels")
