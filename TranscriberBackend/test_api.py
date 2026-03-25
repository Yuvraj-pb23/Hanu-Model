import requests
import time

max_retries = 20
for i in range(max_retries):
    try:
        with open('test.wav', 'rb') as f:
            files = {'audio': f}
            response = requests.post('http://localhost:8000/api/contact-transcribe/', files=files)
            print("Status code:", response.status_code)
            print("Response object:", response.json())
            break
    except Exception as e:
        print(f"Attempt {i+1} failed...")
        time.sleep(10)
