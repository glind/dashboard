#!/usr/bin/env python3
"""
Create a Buildly logo icon for the macOS app
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_buildly_icon():
    """Create a Buildly logo icon with rabbit logo and orange branding"""
    # Create a 1024x1024 image (standard for macOS icons)
    size = 1024
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Official Buildly brand colors (from the logos)
    buildly_orange = "#FF8C42"  # Buildly orange from logo
    darker_orange = "#E67935"   # Slightly darker for depth
    white = "#ffffff"
    black = "#2B2B2B"
    
    # Create rounded rectangle background (modern app icon style)
    corner_radius = int(size * 0.18)  # 18% corner radius for modern look
    
    # Draw rounded rectangle background
    draw.rounded_rectangle([0, 0, size, size], radius=corner_radius, 
                          fill=buildly_orange, outline=darker_orange, width=4)
    
    # Create the rabbit logo (simplified version inspired by Buildly rabbit)
    center = size // 2
    rabbit_size = int(size * 0.35)
    
    # Draw rabbit body (oval)
    body_width = int(rabbit_size * 0.8)
    body_height = int(rabbit_size * 0.9)
    body_x = center - body_width // 2
    body_y = center - body_height // 4
    
    draw.ellipse([body_x, body_y, body_x + body_width, body_y + body_height], 
                fill=white, outline=black, width=6)
    
    # Draw rabbit head (circle)
    head_radius = int(rabbit_size * 0.35)
    head_x = center - head_radius
    head_y = body_y - head_radius + 20
    
    draw.ellipse([head_x, head_y, head_x + head_radius*2, head_y + head_radius*2], 
                fill=white, outline=black, width=6)
    
    # Draw ears
    ear_width = int(rabbit_size * 0.15)
    ear_height = int(rabbit_size * 0.4)
    
    # Left ear
    left_ear_x = head_x + head_radius//2 - ear_width//2
    left_ear_y = head_y - ear_height + 10
    draw.ellipse([left_ear_x, left_ear_y, left_ear_x + ear_width, left_ear_y + ear_height], 
                fill=white, outline=black, width=4)
    
    # Right ear
    right_ear_x = head_x + head_radius + head_radius//2 - ear_width//2
    right_ear_y = head_y - ear_height + 10
    draw.ellipse([right_ear_x, right_ear_y, right_ear_x + ear_width, right_ear_y + ear_height], 
                fill=white, outline=black, width=4)
    
    # Draw eye
    eye_radius = int(rabbit_size * 0.05)
    eye_x = head_x + head_radius + head_radius//3 - eye_radius
    eye_y = head_y + head_radius//2 - eye_radius
    draw.ellipse([eye_x, eye_y, eye_x + eye_radius*2, eye_y + eye_radius*2], 
                fill=black)
    
    # Draw nose (small triangle)
    nose_size = int(rabbit_size * 0.03)
    nose_x = head_x + head_radius + head_radius//4
    nose_y = head_y + head_radius//2 + head_radius//4
    draw.polygon([(nose_x, nose_y - nose_size), 
                  (nose_x - nose_size, nose_y + nose_size), 
                  (nose_x + nose_size, nose_y + nose_size)], 
                 fill=black)
    
    # Add "buildly" text at bottom
    try:
        # Try to use a clean system font
        font_size = int(size * 0.08)
        font = ImageFont.truetype("/System/Library/Fonts/SF-Pro-Text-Bold.otf", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            font = ImageFont.load_default()
    
    text = "buildly"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    
    text_x = center - text_width // 2
    text_y = size - int(size * 0.15)  # 15% from bottom
    
    # Draw text with slight shadow for depth
    shadow_offset = 2
    draw.text((text_x + shadow_offset, text_y + shadow_offset), text, fill=darker_orange, font=font)
    draw.text((text_x, text_y), text, fill=white, font=font)
    
    return img

def create_icns_file():
    """Create .icns file for macOS"""
    # Create the base image
    base_img = create_buildly_icon()
    
    # Create different sizes needed for .icns
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    
    # Save as PNG first (for backup)
    base_img.save('buildly_icon.png', 'PNG')
    print("✅ Created buildly_icon.png")
    
    # For .icns creation, we'll use the iconutil command (macOS specific)
    # First create iconset directory
    iconset_dir = 'buildly_icon.iconset'
    if not os.path.exists(iconset_dir):
        os.makedirs(iconset_dir)
    
    # Generate all required sizes
    for size in sizes:
        img = base_img.resize((size, size), Image.Resampling.LANCZOS)
        img.save(f'{iconset_dir}/icon_{size}x{size}.png', 'PNG')
        
        # Also create @2x versions for retina
        if size <= 512:
            img2x = base_img.resize((size*2, size*2), Image.Resampling.LANCZOS)
            img2x.save(f'{iconset_dir}/icon_{size}x{size}@2x.png', 'PNG')
    
    print(f"✅ Created iconset directory: {iconset_dir}")
    return iconset_dir

if __name__ == "__main__":
    print("🎨 Creating Buildly logo icon...")
    
    try:
        iconset_dir = create_icns_file()
        print("🚀 Icon files created successfully!")
        print(f"📁 Iconset directory: {iconset_dir}")
        print("💡 To create .icns file, run:")
        print(f"   iconutil -c icns {iconset_dir}")
    except Exception as e:
        print(f"❌ Error creating icon: {e}")