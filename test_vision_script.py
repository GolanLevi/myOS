
import requests
import base64
import json
import os

# --- Configurations ---
SERVER_URL = "http://localhost:8000/analyze_email"
IMAGE_PATH = "test_image.jpg" # You will need to provide a real image path or create a dummy one
USER_ID = "admin"

def create_dummy_image():
    """Created a simple red image if not exists"""
    from PIL import Image
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(IMAGE_PATH)
    print(f"🖼️ Created dummy image at {IMAGE_PATH}")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string

def test_vision():
    # 1. Ensure image exists
    if not os.path.exists(IMAGE_PATH):
        create_dummy_image()

    # 2. Encode
    print("Encoding image...")
    img_b64 = encode_image(IMAGE_PATH)

    # 3. Payload
    payload = {
        "text": "This is an invitation. What do you see in the image?",
        "source": "test_script",
        "user_id": USER_ID,
        "images": [img_b64]
    }

    # 4. Send Request
    print("🚀 Sending request to server...")
    try:
        response = requests.post(SERVER_URL, json=payload)
        response.raise_for_status()
        print("✅ Server Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response:
             print(e.response.text)

if __name__ == "__main__":
    test_vision()
