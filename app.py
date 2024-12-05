import os
import shutil
import zipfile
import pandas as pd
from flask import Flask, request, jsonify, send_file,render_template
from datetime import datetime

app = Flask(__name__)

# Directories to save images and BME680 data
BASE_IMAGE_DIR = "images"
CSV_FILE_PATH = "sensor_data.csv"

# Ensure image directory exists
if not os.path.exists(BASE_IMAGE_DIR):
    os.makedirs(BASE_IMAGE_DIR)

# Initialize BME680 CSV file if it doesn't exist
if not os.path.exists(CSV_FILE_PATH):
    df = pd.DataFrame(columns=["timestamp", "unique_id", "temperature", "humidity", "pressure", "gas_resistance"])
    df.to_csv(CSV_FILE_PATH, index=False)

# Route to receive BME680 sensor data and save it to CSV
@app.route('/upload_bme680/<unique_id>', methods=['POST'])
def upload_bme680_data(unique_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    pressure = data.get("pressure")
    gas_resistance = data.get("gas_resistance")

    if not all([temperature, humidity, pressure, gas_resistance]):
        return jsonify({"error": "Missing required fields"}), 400

    # Save sensor data to CSV
    new_data = pd.DataFrame([[timestamp, unique_id, temperature, humidity, pressure, gas_resistance]], 
                            columns=["timestamp", "unique_id", "temperature", "humidity", "pressure", "gas_resistance"])
    new_data.to_csv(CSV_FILE_PATH, mode='a', header=False, index=False)

    return jsonify({"message": "BME680 data received and saved"}), 200

# Route to receive image from ESP32 camera
@app.route('/upload_image/<unique_id>', methods=['POST'])
def upload_image(unique_id):
    # Ensure the unique ID folder exists
    image_folder = os.path.join(BASE_IMAGE_DIR, unique_id)
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    # Get the image from the request
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Generate a unique filename based on the timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"{timestamp}_{image.filename}"
    image_path = os.path.join(image_folder, image_filename)
    
    # Save the image
    image.save(image_path)
    
    return jsonify({"message": f"Image uploaded and saved as {image_filename}"}), 200

# Route to view the latest image from a specific folder (unique_id)
@app.route('/latest_image/<unique_id>', methods=['GET'])
def get_latest_image(unique_id):
    image_folder = os.path.join(BASE_IMAGE_DIR, unique_id)
    
    if not os.path.exists(image_folder):
        return jsonify({"error": f"No images found for ID {unique_id}"}), 404
    
    # Get the latest image file based on timestamp
    images = os.listdir(image_folder)
    if not images:
        return jsonify({"error": "No images available"}), 404
    
    latest_image = max(images, key=lambda x: os.path.getctime(os.path.join(image_folder, x)))
    
    return jsonify({"latest_image": latest_image}), 200

# Route to download all images as a ZIP file
@app.route('/download_all_images', methods=['GET'])
def download_all_images():
    # Create a ZIP file with all images
    zip_filename = "all_images.zip"
    zip_filepath = os.path.join(BASE_IMAGE_DIR, zip_filename)
    
    # Create a ZIP archive of the base directory (excluding the zip file itself)
    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(BASE_IMAGE_DIR):
            for file in files:
                if file != zip_filename:
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), BASE_IMAGE_DIR))
    
    # Send the ZIP file to the client
    return send_file(zip_filepath, as_attachment=True)

# Route to download the BME680 sensor data as CSV
@app.route('/download_sensor_data', methods=['GET'])
def download_sensor_data():
    if os.path.exists(CSV_FILE_PATH):
        return send_file(CSV_FILE_PATH, as_attachment=True)
    else:
        return jsonify({"error": "Sensor data not found"}), 404

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    # Get the port from the environment variable (set by Railway)
    port = int(os.environ.get('PORT', 5000))  # Default to 5000 if PORT isn't set
    app.run(debug=False, host='0.0.0.0', port=port)

