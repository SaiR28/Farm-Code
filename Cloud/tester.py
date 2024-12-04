import requests

# Flask server URL
server_url = "http://127.0.0.1:5000/upload"  # Replace with your Railway domain if deployed

# Unique ID of the ESP32 device
unique_id = "ESP32_CAM_01"

# Path to the image file to upload
image_path = "test_image.jpg"  # Replace with the path to your test image

def test_upload():
    try:
        # Prepare the data
        with open(image_path, "rb") as image_file:
            files = {
                "image": image_file
            }
            data = {
                "unique_id": unique_id
            }

            # Send the POST request
            response = requests.post(server_url, files=files, data=data)

        # Print the response from the server
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()
