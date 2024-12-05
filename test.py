import requests
import random
import time

# URL of the Flask server
url = "http://127.0.0.1:5000/submit"

# Function to generate random BME680 sensor data
def generate_sensor_data():
    return {
        "temperature": round(random.uniform(20.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 80.0), 2),
        "pressure": round(random.uniform(950.0, 1050.0), 2),
        "gas_resistance": round(random.uniform(100.0, 500.0), 2),
    }

# Send data in a loop
try:
    while True:
        data = generate_sensor_data()
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print(f"Data sent successfully: {data}")
        else:
            print(f"Failed to send data: {response.status_code}")
        time.sleep(5)  # Send data every 5 seconds
except KeyboardInterrupt:
    print("\nStopped sending data.")
