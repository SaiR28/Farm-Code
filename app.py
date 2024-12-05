from flask import Flask, request, jsonify, send_file, render_template
import csv
import os
from datetime import datetime

app = Flask(__name__)

# Path for the CSV file
CSV_FILE = "sensor_data.csv"

# Ensure the CSV file exists with a header row
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "temperature", "humidity", "pressure", "gas_resistance"])

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

if __name__ == '__main__':
    app.run(debug=True)
