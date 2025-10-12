from flask import Flask, render_template, request, jsonify, send_file
import os
from PIL import Image, ImageEnhance
from werkzeug.utils import secure_filename
import sys
import io

# Add the library path for Waveshare e-paper (dynamic path)
sys.path.append(os.path.expanduser('~/e-Paper/RaspberryPi_JetsonNano/python/lib'))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.expanduser('~/eink_display/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(image_path, brightness=1.0, contrast=1.4, saturation=1.5):
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

def display_image(image_path, brightness=1.0, contrast=1.4, saturation=1.5):
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
    brightness = float(request.form.get('brightness', 1.0))
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

@app.route('/images', methods=['GET'])
def list_images():
    """Get list of uploaded images"""
    try:
        files = []
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                files.append({
                    'filename': filename,
                    'size': os.path.getsize(filepath),
                    'modified': os.path.getmtime(filepath)
                })
        # Sort by most recent first
        files.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({'images': files}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/display/<filename>', methods=['POST'])
def display_saved_image(filename):
    """Display a previously uploaded image"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Image not found'}), 404
        
        # Get optional enhancement parameters
        brightness = float(request.form.get('brightness', 1.0))
        contrast = float(request.form.get('contrast', 1.4))
        saturation = float(request.form.get('saturation', 1.5))
        
        print(f"Displaying {filename} with brightness={brightness}, contrast={contrast}, saturation={saturation}")
        
        success = display_image(filepath, brightness, contrast, saturation)
        
        if success:
            return jsonify({'message': 'Image displayed successfully'}), 200
        else:
            return jsonify({'error': 'Failed to display image'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_image(filename):
    """Delete a saved image"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Image not found'}), 404
        
        os.remove(filepath)
        return jsonify({'message': 'Image deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/thumbnail/<filename>')
def get_thumbnail(filename):
    """Generate and serve a thumbnail of the image"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Image not found'}), 404
        
        # Create thumbnail
        img = Image.open(filepath)
        img.thumbnail((150, 90), Image.Resampling.LANCZOS)
        
        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/jpeg')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/preview/<filename>')
def get_preview(filename):
    """Serve the full image for preview"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Image not found'}), 404
        
        return send_file(filepath)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/display/binary', methods=['POST'])
def display_binary():
    """Accept binary image data from external sources (like ESP32)"""
    try:
        # Import only when needed to avoid GPIO conflicts
        from waveshare_epd import epd7in3e
        
        # Check if binary data was sent as file upload
        if 'file' in request.files:
            binary_file = request.files['file']
            binary_data = binary_file.read()
        # Or as raw POST body
        elif request.data:
            binary_data = request.data
        else:
            return jsonify({'error': 'No binary data received'}), 400
        
        # Validate data size (should be 192000 bytes for 800x480 display)
        if len(binary_data) != 192000:
            return jsonify({'error': f'Invalid data size: {len(binary_data)} bytes (expected 192000)'}), 400
        
        print(f"Received {len(binary_data)} bytes of binary image data")
        
        epd = epd7in3e.EPD()
        epd.init()
        epd.display(binary_data)
        epd.sleep()
        
        return jsonify({'message': 'Binary image displayed successfully'}), 200
        
    except Exception as e:
        print(f"Error displaying binary image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Disable reloader to prevent GPIO conflicts
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
