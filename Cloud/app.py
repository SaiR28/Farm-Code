from flask import Flask, request, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# Base directory for uploaded images
BASE_UPLOAD_FOLDER = "uploads"
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return "Welcome to the ESP32-CAM Image Server!"

@app.route("/upload", methods=["POST"])
def upload_image():
    # Check for required fields
    if 'unique_id' not in request.form:
        return jsonify({"error": "Unique ID not provided"}), 400

    if 'image' not in request.files:
        return jsonify({"error": "No image file found in request"}), 400
    
    # Extract unique ID and image file
    unique_id = request.form['unique_id']
    image = request.files['image']
    
    if image.filename == "":
        return jsonify({"error": "No selected file"}), 400

    # Create a directory for the unique ID if it doesn't exist
    user_folder = os.path.join(BASE_UPLOAD_FOLDER, unique_id)
    os.makedirs(user_folder, exist_ok=True)

    # Save the image with a timestamp
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + image.filename
    filepath = os.path.join(user_folder, filename)
    image.save(filepath)

    return jsonify({"message": "Image uploaded successfully!", "filename": filename, "folder": unique_id}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
