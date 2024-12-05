import os
from flask import Flask, request, jsonify, send_file, render_template
import csv
from datetime import datetime
from werkzeug.utils import secure_filename
import zipfile

app = Flask(__name__)

# Path for the CSV file
CSV_FILE = "sensor_data.csv"
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}  # Allowed image formats

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Ensure the CSV file exists with a header row
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "temperature", "humidity", "pressure", "gas_resistance"])

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_data():
    data = request.json
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    pressure = data.get("pressure")
    gas_resistance = data.get("gas_resistance")

    # Save the data to the CSV file
    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, temperature, humidity, pressure, gas_resistance])

    return jsonify({"status": "success", "message": "Data saved successfully"}), 200

@app.route('/data', methods=['GET'])
def get_data():
    try:
        with open(CSV_FILE, mode="r") as file:
            reader = list(csv.reader(file))
            return jsonify({"data": reader[1:]})  # Exclude header row
    except FileNotFoundError:
        return jsonify({"data": []})

@app.route('/download', methods=['GET'])
def download_csv():
    return send_file(CSV_FILE, as_attachment=True)

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files['file']
    unique_id = request.form.get('unique_id')

    if not file or not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Invalid file format"}), 400

    # Create a folder for the unique ID if it doesn't exist
    user_folder = os.path.join(UPLOAD_FOLDER, unique_id)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    # Secure the filename and save the image
    filename = secure_filename(file.filename)
    file_path = os.path.join(user_folder, filename)
    file.save(file_path)

    return jsonify({"status": "success", "message": f"Image saved as {filename}"}), 200

@app.route('/latest_image/<unique_id>', methods=['GET'])
def latest_image(unique_id):
    user_folder = os.path.join(UPLOAD_FOLDER, unique_id)

    if not os.path.exists(user_folder):
        return jsonify({"status": "error", "message": "No images found for this ID"}), 404

    # Get the latest image based on the file modified time
    images = [f for f in os.listdir(user_folder) if allowed_file(f)]
    if not images:
        return jsonify({"status": "error", "message": "No images found for this ID"}), 404

    latest_image = max(images, key=lambda f: os.path.getmtime(os.path.join(user_folder, f)))
    return send_file(os.path.join(user_folder, latest_image))

@app.route('/download_images/<unique_id>', methods=['GET'])
def download_images(unique_id):
    user_folder = os.path.join(UPLOAD_FOLDER, unique_id)

    if not os.path.exists(user_folder):
        return jsonify({"status": "error", "message": "No images found for this ID"}), 404

    # Create a ZIP file
    zip_filename = f"{unique_id}_images.zip"
    zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(user_folder):
            for file in files:
                if allowed_file(file):
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, user_folder))

    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    # Get the port from the environment variable (set by Railway)
    port = int(os.environ.get('PORT', 5000))  # Default to 5000 if PORT isn't set
    app.run(debug=True, host='0.0.0.0', port=port)  # Use the available port
