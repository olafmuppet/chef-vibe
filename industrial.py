import streamlit as st
import google.generativeai as genai
import requests
import json

# We use the industrial-grade 'yt_dlp' library
try:
    from yt_dlp import YoutubeDL
except ImportError:
    st.error("🚨 Critical Missing Tool: yt-dlp. Run 'pip install yt-dlp'")
    st.stop()

st.set_page_config(page_title="Chef Vibe: Industrial", page_icon="🏭")
st.title("🏭 Chef Vibe: Industrial Mode")

# 1. Inputs
api_key = st.text_input("Enter Gemini API Key:", type="password")
video_url = st.text_input("Paste YouTube URL:")

def get_captions_via_ytdlp(url):
    ydl_opts = {
        'skip_download': True,  # We don't want the video, just data
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # 1. Extract Video Metadata
            info = ydl.extract_info(url, download=False)
            
            # 2. Look for Captions (Manual or Auto-Generated)
            captions = info.get('subtitles') or info.get('automatic_captions')
            
            if not captions:
                return "Error: No captions found for this video."

            # 3. Find English (en) or Auto-English (en-orig, en-US, etc)
            # We prefer 'en', then 'en-orig', then the first one we find.
            lang = 'en'
            if 'en' not in captions:
                # Fallback: look for any english variant
                found = False
                for code in captions:
                    if code.startswith('en'):
                        lang = code
                        found = True
                        break
                if not found:
                    # Last resort: take the first available language
                    lang = list(captions.keys())[0]

            # 4. Get the JSON URL for the captions
            # yt-dlp gives us a list of formats. We want 'json3' or 'vtt'.
            # JSON3 is easiest to parse.
            cap_formats = captions[lang]
            json_url = None
            for fmt in cap_formats:
                if fmt['ext'] == 'json3':
                    json_url = fmt['url']
                    break
            
            if not json_url:
                # Fallback to whatever URL is there if json3 isn't found
                json_url = cap_formats[0]['url']

            # 5. Download and Parse
            response = requests.get(json_url)
            if response.status_code != 200:
                return "Error: Could not download caption data."
            
            # If it's JSON3 format
            try:
                data = response.json()
                events = data.get('events', [])
                full_text = []
                for event in events:
                    segs = event.get('segs', [])
                    for seg in segs:
                        if seg.get('utf8'):
                            full_text.append(seg['utf8'])
                return " ".join(full_text)
            except:
                # If it wasn't JSON, just return raw text (fallback)
                return response.text

    except Exception as e:
        return f"Extraction Error: {e}"

if st.button("Rip Recipe"):
    if not api_key or not video_url:
        st.error("Missing Info!")
    else:
        with st.spinner("🏭 Extracting data using yt-dlp..."):
            transcript_text = get_captions_via_ytdlp(video_url)

        if "Error" in transcript_text:
            st.error(transcript_text)
        else:
            try:
                with st.spinner("👨‍🍳 AI Chef is cooking..."):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""
                    Extract ingredients from this text.
                    Output ONLY a list of ingredients separated by a pipe symbol (|).
                    Example: Eggs | Flour | Milk
                    Transcript: {transcript_text[:15000]}
                    """
                    
                    response = model.generate_content(prompt)
                    
                    st.success("Success!")
                    st.subheader("🛒 Shopping List")
                    
                    items = response.text.split("|")
                    for item in items:
                        if item.strip():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.checkbox(item.strip())
                            with col2:
                                clean = item.strip().replace(" ", "+")
                                st.link_button("Buy ↗️", f"https://www.instacart.com/store/search?term={clean}")
            except Exception as e:
                st.error(f"AI Error: {e}")