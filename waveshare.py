from flask import Flask, render_template, request, jsonify
import os
from PIL import Image, ImageEnhance
from werkzeug.utils import secure_filename
import sys

# Add the library path for Waveshare e-paper (dynamic path)
sys.path.append(os.path.expanduser('~/e-Paper/RaspberryPi_JetsonNano/python/lib'))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/eink_uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(image_path, brightness=1.3, contrast=1.4, saturation=1.5):
    """Process image to fit 800x480 display - crop to fill with enhancement"""
    img = Image.open(image_path)
    
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Auto-rotate portrait to landscape
    if img.height > img.width:
        img = img.rotate(90, expand=True)
        print(f"Rotated portrait image to landscape")
    
    # Downscale very large images first
    if img.width > 2400 or img.height > 1440:
        img.thumbnail((2400, 1440), Image.Resampling.LANCZOS)
        print(f"Pre-scaled large image to {img.width}x{img.height}")
    
    # Calculate crop-to-fill dimensions
    img_ratio = img.width / img.height
    display_ratio = 800 / 480
    
    if img_ratio > display_ratio:
        new_height = 480
        new_width = int(480 * img_ratio)
    else:
        new_width = 800
        new_height = int(800 / img_ratio)
    
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - 800) // 2
    top = (new_height - 480) // 2
    img = img.crop((left, top, left + 800, top + 480))
    
    # Enhance image for E Ink display
    print(f"Enhancing: brightness={brightness}, contrast={contrast}, saturation={saturation}")
    
    # Increase brightness
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness)
    
    # Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)
    
    # Increase color saturation
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(saturation)
    
    return img

def display_image(image_path, brightness=1.3, contrast=1.4, saturation=1.5):
    """Send image to e-paper display using Waveshare's built-in conversion"""
    try:
        # Import only when needed to avoid GPIO conflicts
        from waveshare_epd import epd7in3e
        
        print("Initializing display...")
        epd = epd7in3e.EPD()
        epd.init()
        
        print("Processing image...")
        img = process_image(image_path, brightness, contrast, saturation)
        
        print("Converting and sending to display...")
        # Use Waveshare's getbuffer method for color conversion
        epd.display(epd.getbuffer(img))
        
        print("Putting display to sleep...")
        epd.sleep()
        
        print("Display complete!")
        return True
    except Exception as e:
        print(f"Error displaying image: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Get optional enhancement parameters
    brightness = float(request.form.get('brightness', 1.3))
    contrast = float(request.form.get('contrast', 1.4))
    saturation = float(request.form.get('saturation', 1.5))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Display on e-paper with custom enhancements
        success = display_image(filepath, brightness, contrast, saturation)
        
        if success:
            return jsonify({'message': 'Image displayed successfully', 'filename': filename}), 200
        else:
            return jsonify({'error': 'Failed to display image'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/clear', methods=['POST'])
def clear_display():
    """Clear the e-paper display"""
    try:
        # Import only when needed to avoid GPIO conflicts
        from waveshare_epd import epd7in3e
        
        epd = epd7in3e.EPD()
        epd.init()
        epd.Clear()
        epd.sleep()
        return jsonify({'message': 'Display cleared'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Disable reloader to prevent GPIO conflicts
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
