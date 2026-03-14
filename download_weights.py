import os
import urllib.request
import ssl

url = 'https://github.com/serengil/deepface_models/releases/download/v1.0/facenet_weights.h5'
save_path = r'C:\Users\804\.deepface\weights\facenet_weights.h5'
os.makedirs(os.path.dirname(save_path), exist_ok=True)

context = ssl._create_unverified_context()
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

print(f"Downloading {url} to {save_path}...")
with urllib.request.urlopen(req, context=context) as response, open(save_path, 'wb') as f:
    f.write(response.read())
print("Weights downloaded successfully.")
