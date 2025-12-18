import requests
import json

BASE_URL = "http://localhost:8000"

def test_tts():
    print("1. Testing TTS Synthesis...")
    url = f"{BASE_URL}/tts/synthesize"
    data = {"text": "مرحباً بكم في منصة التعليم السحابية", "language": "ar"}
    response = requests.post(url, json=data)
    
    if response.status_code != 200:
        print(f"Error: Synthesis failed with status {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    print("Synthesis Success:", result)
    
    audio_url = result.get("audio_url")
    if not audio_url:
        print("Error: No audio_url in response")
        return
    
    # Correct the URL to go through gateway (frontend logic)
    proxy_url = f"{BASE_URL}{audio_url.replace('/api/tts', '/tts')}"
    print(f"2. Testing Audio Download via {proxy_url}...")
    
    audio_response = requests.get(proxy_url)
    if audio_response.status_code != 200:
        print(f"Error: Audio download failed with status {audio_response.status_code}")
        print(audio_response.text)
        return
    
    content_type = audio_response.headers.get("Content-Type")
    print(f"Download Success! Content-Type: {content_type}, Size: {len(audio_response.content)} bytes")
    
    if "audio" in content_type:
        print("✅ Success: Binary audio received correctly through gateway!")
    else:
        print("❌ Failure: Response is not audio. Content preview:")
        print(audio_response.text[:200])

if __name__ == "__main__":
    test_tts()
