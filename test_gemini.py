from google import genai
import os
import time

# 1. Setup - Fetch API Key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # Manual fallback for your local test environment
    api_key = "AIzaSyA-wbm4CPmGo4pIaRV-PXkI16o29LTkfBU"

client = genai.Client(api_key=api_key)
MODEL_ID = "gemini-3-flash-preview"

def analyze_video():
    print("--- 🎥 Neural Video Analysis Node ---")
    
    # Take input from terminal
    video_url = input("Please enter the YouTube URL: ").strip()
    
    if not video_url:
        print("Error: No URL provided.")
        return

    print(f"\n[SYSTEM] Ingesting stream from: {video_url}")
    print("[SYSTEM] Processing multimodal data (this may take a moment)...")

    try:
        # Construct the prompt for high-fidelity insights
        prompt = """
        Analyze this video and provide:
        1. A 100-word professional transcript.
        2. A 2-sentence executive summary.
        3. 5 key tags/keywords.
        4. Main objects or themes detected.
        """

        # Generate content using the video URL directly
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[video_url, prompt]
        )

        print("\n" + "="*50)
        print("📊 ANALYSIS COMPLETE")
        print("="*50)
        print(response.text)
        print("="*50)

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline Failed: {e}")

if __name__ == "__main__":
    analyze_video()