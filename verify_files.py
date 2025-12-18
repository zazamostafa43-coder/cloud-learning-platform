import sys
import os

def check_structure():
    print("--- Project Structure Verification ---")
    paths = [
        "services/stt_service/main.py",
        "services/tts_service/main.py",
        "services/document_service/main.py",
        "services/chat_service/main.py",
        "services/quiz_service/main.py",
        "gateway/main.py",
        "frontend/src/App.jsx",
        "infrastructure/main.tf",
        ".env"
    ]
    
    all_ok = True
    for p in paths:
        if os.path.exists(p):
            print(f"[OK] Found: {p}")
        else:
            print(f"[MISSING] {p}")
            all_ok = False
    
    if all_ok:
        print("\n✅ All source files are present and correctly structured.")
    else:
        print("\n❌ Some files are missing.")

if __name__ == "__main__":
    check_structure()
