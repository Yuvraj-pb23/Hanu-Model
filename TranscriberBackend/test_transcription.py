import requests

try:
    with open('test.wav', 'rb') as f:
        files = {'audio': f}
        response = requests.post('http://localhost:8000/api/contact-transcribe/', files=files)
        print("Status code:", response.status_code)
        print("Response object:", response.json())
except Exception as e:
    print(f"Error: {e}")
