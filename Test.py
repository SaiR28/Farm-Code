"""
Test Script for Hydroponic Farm API
----------------------------------
This script simulates sending data from various sensors and modules to test the API endpoints.
"""

import requests
import random
import time
from datetime import datetime
import os
from typing import Dict, Any

class FarmAPITester:
    """Class to test the Farm API endpoints"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url
        self.test_image_path = "test_image.jpg"
        self._create_test_image()
    
    def _create_test_image(self) -> None:
        """Create a simple test image if it doesn't exist"""
        if not os.path.exists(self.test_image_path):
            # Create a small black image for testing
            from PIL import Image
            img = Image.new('RGB', (100, 100), color='black')
            img.save(self.test_image_path)
    
    def generate_sensor_data(self) -> Dict[str, float]:
        """Generate random sensor data"""
        return {
            "ph": round(random.uniform(5.5, 7.5), 2),
            "tds": round(random.uniform(500, 1500), 2),
            "water_temp": round(random.uniform(20, 26), 2),
            "light_intensity": round(random.uniform(800, 2000), 2),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def generate_actuator_data(self) -> Dict[str, str]:
        """Generate random actuator status data"""
        return {
            "light_status": random.choice(["ON", "OFF"]),
            "pump_status": random.choice(["ON", "OFF"]),
            "ph_up_pump_status": random.choice(["ON", "OFF"]),
            "ph_down_pump_status": random.choice(["ON", "OFF"]),
            "nutrient_pump_status": random.choice(["ON", "OFF"]),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def generate_environment_data(self) -> Dict[str, float]:
        """Generate random environment data"""
        return {
            "temperature": round(random.uniform(20, 30), 2),
            "humidity": round(random.uniform(40, 80), 2),
            "pressure": round(random.uniform(1000, 1025), 2),
            "voc": round(random.uniform(100, 1000), 2),
            "co2": round(random.uniform(400, 1200), 2),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def test_sensor_data(self, rack_id: int) -> None:
        """Test sending sensor data"""
        url = f"{self.base_url}/api/rack/{rack_id}/data"
        data = self.generate_sensor_data()
        
        try:
            response = requests.post(url, json=data)
            print(f"Sensor Data Test - Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error sending sensor data: {e}")

    def test_actuator_data(self, rack_id: int) -> None:
        """Test sending actuator data"""
        url = f"{self.base_url}/api/rack/{rack_id}/actuator"
        data = self.generate_actuator_data()
        
        try:
            response = requests.post(url, json=data)
            print(f"Actuator Data Test - Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error sending actuator data: {e}")

    def test_environment_data(self, rack_id: int) -> None:
        """Test sending environment data"""
        url = f"{self.base_url}/api/rack/{rack_id}/environment"
        data = self.generate_environment_data()
        
        try:
            response = requests.post(url, json=data)
            print(f"Environment Data Test - Status: {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error sending environment data: {e}")

    def test_image_upload(self, rack_id: int, camera_id: int) -> None:
        """Test uploading an image"""
        url = f"{self.base_url}/api/rack/{rack_id}/camera/{camera_id}/image"
        
        try:
            with open(self.test_image_path, 'rb') as img:
                files = {'image': ('test.jpg', img, 'image/jpeg')}
                response = requests.post(url, files=files)
                print(f"Image Upload Test - Status: {response.status_code}")
                print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error uploading image: {e}")

    def test_get_all_data(self, rack_id: int) -> None:
        """Test getting all rack data"""
        url = f"{self.base_url}/api/rack/{rack_id}/data/all"
        
        try:
            response = requests.get(url)
            print(f"Get All Data Test - Status: {response.status_code}")
            print("Response Data:")
            print(f"Sensor Data: {response.json().get('sensor_data')}")
            print(f"Actuator Data: {response.json().get('actuator_data')}")
            print(f"Environment Data: {response.json().get('environment_data')}")
            print(f"Recent Images: {response.json().get('recent_images')}")
        except Exception as e:
            print(f"Error getting all data: {e}")

    def run_continuous_test(self, rack_id: int, camera_id: int, interval: int = 60) -> None:
        """
        Run a continuous test that sends data at regular intervals
        
        Args:
            rack_id: ID of the rack to test
            camera_id: ID of the camera to test
            interval: Time between tests in seconds (default: 60)
        """
        print(f"Starting continuous test for Rack {rack_id}, Camera {camera_id}")
        print(f"Data will be sent every {interval} seconds")
        print("Press Ctrl+C to stop the test")
        
        try:
            while True:
                print("\n" + "="*50)
                print(f"Test Run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*50)
                
                # Send all types of data
                self.test_sensor_data(rack_id)
                time.sleep(1)
                
                self.test_actuator_data(rack_id)
                time.sleep(1)
                
                self.test_environment_data(rack_id)
                time.sleep(1)
                
                self.test_image_upload(rack_id, camera_id)
                time.sleep(1)
                
                self.test_get_all_data(rack_id)
                
                print(f"\nWaiting {interval} seconds until next test...")
                time.sleep(interval - 4)  # Subtract time taken by the tests
                
        except KeyboardInterrupt:
            print("\nTest stopped by user")
        finally:
            if os.path.exists(self.test_image_path):
                os.remove(self.test_image_path)

def main():
    # Create tester instance
    tester = FarmAPITester()
    
    # Run a continuous test for rack 1, camera 1, with 60-second intervals
    tester.run_continuous_test(rack_id=1, camera_id=1, interval=60)

if __name__ == "__main__":
    main()