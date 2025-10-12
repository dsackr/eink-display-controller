from flask import Flask, render_template, request, jsonify, send_file
import os
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
from datetime import datetime
import sys
import io
import json

# Add the library path for Waveshare e-paper (dynamic path)
sys.path.append(os.path.expanduser('~/e-Paper/RaspberryPi_JetsonNano/python/lib'))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.expanduser('~/eink_display/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Safety Tracker Configuration
SAFETY_DATA_FILE = os.path.expanduser('~/eink_display/safety_data.json')
SAFETY_BACKGROUND = os.path.expanduser('~/eink_display/static/safety_background.png')
SAFETY_OUTPUT = os.path.expanduser('~/eink_display/static/current_safety_sign.png')

# Create static folder
os.makedirs(os.path.expanduser('~/eink_display/static'), exist_ok=True)

# Safety tracker font sizes and positions
FONT_SIZE_DAYS = 400
FONT_SIZE_PRIOR_COUNT = 150
FONT_SIZE_INCIDENT = 100
FONT_SIZE_CHECKMARK = 80
DAYS_Y_POSITION = 160
DAYS_X_OFFSET = 0
PRIOR_COUNT_X = 220
PRIOR_COUNT_Y = 630
INCIDENT_X_OFFSET = 70
INCIDENT_Y = 650
CHECKMARK_X = 940
CHECKMARK_CHANGE_Y = 575
CHECKMARK_DEPLOY_Y = 645
CHECKMARK_MISSED_Y = 705

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(image_path, brightness=1.0, contrast=1.4, saturation=1.5, rotate_180=False):
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
    
    # Rotate 180 degrees if requested
    if rotate_180:
        img = img.rotate(180)
        print(f"Rotated image 180 degrees")
    
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

def display_image(image_path, brightness=1.0, contrast=1.4, saturation=1.5, rotate_180=False):
    """Send image to e-paper display using Waveshare's built-in conversion"""
    try:
        # Import only when needed to avoid GPIO conflicts
        from waveshare_epd import epd7in3e
        
        print("Initializing display...")
        epd = epd7in3e.EPD()
        epd.init()
        
        print("Processing image...")
        img = process_image(image_path, brightness, contrast, saturation, rotate_180)
        
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
    rotate_180 = request.form.get('rotate_180', 'false').lower() == 'true'
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Display on e-paper with custom enhancements
        success = display_image(filepath, brightness, contrast, saturation, rotate_180)
        
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
        rotate_180 = request.form.get('rotate_180', 'false').lower() == 'true'
        
        print(f"Displaying {filename} with brightness={brightness}, contrast={contrast}, saturation={saturation}, rotate_180={rotate_180}")
        
        success = display_image(filepath, brightness, contrast, saturation, rotate_180)
        
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

# ============ SAFETY TRACKER FUNCTIONS ============

def load_safety_data():
    """Load safety tracking data from JSON file"""
    if os.path.exists(SAFETY_DATA_FILE):
        with open(SAFETY_DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        'days_since': 1,
        'prior_count': 2,
        'incident_number': '540',
        'incident_date': '2025-10-03',
        'prior_incident_date': '2025-10-01',
        'reason': 'Deploy',
        'last_reset': datetime.now().isoformat()
    }

def save_safety_data(data):
    """Save safety tracking data to JSON file"""
    with open(SAFETY_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def generate_safety_sign(auto_display=False):
    """Generate the safety sign with current data"""
    data = load_safety_data()
    
    # Calculate days since current incident date
    if 'incident_date' in data:
        incident_date = datetime.fromisoformat(data['incident_date'])
        today = datetime.now()
        days_since = (today.date() - incident_date.date()).days
    else:
        days_since = data.get('days_since', 0)
    
    # Calculate prior count
    if 'prior_incident_date' in data and 'incident_date' in data:
        prior_date = datetime.fromisoformat(data['prior_incident_date'])
        current_date = datetime.fromisoformat(data['incident_date'])
        prior_count = (current_date.date() - prior_date.date()).days
    else:
        prior_count = data.get('prior_count', 0)
    
    data['days_since'] = days_since
    data['prior_count'] = prior_count
    
    # Check if background exists
    if not os.path.exists(SAFETY_BACKGROUND):
        print(f"WARNING: Safety sign background not found at {SAFETY_BACKGROUND}")
        print("Please upload a background image named 'safety_background.png' to the static folder")
        return False
    
    # Open background image
    img = Image.open(SAFETY_BACKGROUND)
    draw = ImageDraw.Draw(img)
    
    img_width, img_height = img.size
    
    # Load fonts
    try:
        days_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', FONT_SIZE_DAYS)
        count_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', FONT_SIZE_PRIOR_COUNT)
        inc_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', FONT_SIZE_INCIDENT)
        check_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', FONT_SIZE_CHECKMARK)
    except:
        days_font = ImageFont.load_default()
        count_font = ImageFont.load_default()
        inc_font = ImageFont.load_default()
        check_font = ImageFont.load_default()
    
    # Draw main days count
    days_text = str(data['days_since'])
    days_bbox = draw.textbbox((0, 0), days_text, font=days_font)
    days_width = days_bbox[2] - days_bbox[0]
    days_x = (img_width - days_width) // 2 + DAYS_X_OFFSET
    days_y = DAYS_Y_POSITION
    draw.text((days_x, days_y), days_text, font=days_font, fill='black')
    
    # Draw prior count
    prior_text = str(data['prior_count'])
    prior_bbox = draw.textbbox((0, 0), prior_text, font=count_font)
    prior_width = prior_bbox[2] - prior_bbox[0]
    prior_x = PRIOR_COUNT_X - (prior_width // 2)
    prior_y = PRIOR_COUNT_Y
    draw.text((prior_x, prior_y), prior_text, font=count_font, fill='white')
    
    # Draw incident number
    inc_text = data['incident_number']
    inc_bbox = draw.textbbox((0, 0), inc_text, font=inc_font)
    inc_width = inc_bbox[2] - inc_bbox[0]
    inc_x = (img_width // 2) - (inc_width // 2) + INCIDENT_X_OFFSET
    inc_y = INCIDENT_Y
    draw.text((inc_x, inc_y), inc_text, font=inc_font, fill='white')
    
    # Draw checkmark
    reason_positions = {
        'Change': (CHECKMARK_X, CHECKMARK_CHANGE_Y),
        'Deploy': (CHECKMARK_X, CHECKMARK_DEPLOY_Y),
        'Missed': (CHECKMARK_X, CHECKMARK_MISSED_Y)
    }
    
    if data['reason'] in reason_positions:
        check_x, check_y = reason_positions[data['reason']]
        draw.text((check_x, check_y), '✓', font=check_font, fill='blue')
    
    # Save the generated image
    img.save(SAFETY_OUTPUT)
    
    # Auto display to e-paper if requested
    if auto_display:
        display_image(SAFETY_OUTPUT, brightness=1.0, contrast=1.4, saturation=1.5, rotate_180=True)
    
    return True

# ============ SAFETY TRACKER ROUTES ============

@app.route('/safety')
def safety_tracker():
    """Safety tracker page"""
    data = load_safety_data()
    
    if 'incident_date' in data:
        incident_date = datetime.fromisoformat(data['incident_date'])
        today = datetime.now()
        data['days_since'] = (today.date() - incident_date.date()).days
    
    if 'prior_incident_date' in data and 'incident_date' in data:
        prior_date = datetime.fromisoformat(data['prior_incident_date'])
        current_date = datetime.fromisoformat(data['incident_date'])
        data['prior_count'] = (current_date.date() - prior_date.date()).days
    
    return render_template('safety.html', data=data)

@app.route('/safety/update', methods=['POST'])
def update_safety():
    """Update safety tracker data"""
    data = load_safety_data()
    
    if 'incident_date' in data:
        data['prior_incident_date'] = data['incident_date']
    
    data['incident_number'] = request.form.get('incident_number', '')
    data['incident_date'] = request.form.get('incident_date', '')
    data['reason'] = request.form.get('reason', 'Change')
    data['last_reset'] = datetime.now().isoformat()
    
    incident_date = datetime.fromisoformat(data['incident_date'])
    today = datetime.now()
    data['days_since'] = (today.date() - incident_date.date()).days
    
    if 'prior_incident_date' in data:
        prior_date = datetime.fromisoformat(data['prior_incident_date'])
        current_date = datetime.fromisoformat(data['incident_date'])
        data['prior_count'] = (current_date.date() - prior_date.date()).days
    
    save_safety_data(data)
    
    if generate_safety_sign():
        return jsonify({'success': True, 'message': 'Safety sign updated'}), 200
    else:
        return jsonify({'success': False, 'error': 'Failed to generate sign'}), 500

@app.route('/safety/display', methods=['POST'])
def display_safety_sign():
    """Display the safety sign on e-paper"""
    if not os.path.exists(SAFETY_OUTPUT):
        generate_safety_sign()
    
    if display_image(SAFETY_OUTPUT, brightness=1.0, contrast=1.4, saturation=1.5, rotate_180=True):
        return jsonify({'success': True, 'message': 'Safety sign displayed'}), 200
    else:
        return jsonify({'success': False, 'error': 'Failed to display sign'}), 500

@app.route('/safety/preview')
def preview_safety_sign():
    """Serve the safety sign preview image"""
    if not os.path.exists(SAFETY_OUTPUT):
        generate_safety_sign()
    
    return send_file(SAFETY_OUTPUT, mimetype='image/png')

@app.route('/safety/auto_update', methods=['POST'])
def auto_update_safety():
    """Auto-update safety sign (for cronjob) - generates and displays"""
    if generate_safety_sign(auto_display=True):
        return jsonify({'success': True, 'message': 'Safety sign auto-updated and displayed'}), 200
    else:
        return jsonify({'success': False, 'error': 'Failed to auto-update'}), 500

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
