"""
Simple icon generator for Chrome extension
Creates basic colored squares as placeholders
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, color, text, filename):
    """Create a simple icon with text"""
    # Create image
    img = Image.new('RGBA', (size, size), color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", size // 3)
    except:
        font = ImageFont.load_default()
    
    # Draw text in center
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), text, fill='white', font=font)
    
    # Save image
    img.save(filename, 'PNG')
    print(f"Created: {filename}")

def main():
    # Create icons directory
    os.makedirs('icons', exist_ok=True)
    
    # Main icon - Blue with "200"
    main_color = (102, 126, 234, 255)  # Blue
    create_icon(16, main_color, "200", 'icons/icon16.png')
    create_icon(32, main_color, "200", 'icons/icon32.png')
    create_icon(48, main_color, "200", 'icons/icon48.png')
    create_icon(128, main_color, "200", 'icons/icon128.png')
    
    # Error icon - Red with "!"
    error_color = (220, 38, 38, 255)  # Red
    create_icon(128, error_color, "!", 'icons/error.png')
    
    # Warning icon - Yellow with "!"
    warning_color = (245, 158, 11, 255)  # Yellow/Orange
    create_icon(128, warning_color, "!", 'icons/warning.png')
    
    print("\nAll icons created successfully!")
    print("You can replace these with custom icons later.")

if __name__ == '__main__':
    main()
