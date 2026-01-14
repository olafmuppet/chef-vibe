import streamlit as st
import google.generativeai as genai
import requests
from yt_dlp import YoutubeDL
import urllib.parse
# We wrap the import to prevent crash if library is acting up
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

# --- 1. SETUP PAGE & CAPTURE URL ---
st.set_page_config(page_title="Chef Vibe", page_icon="🥂")

params = st.query_params
url_from_iphone = params.get("url", "")

st.title("🥂 Chef Vibe")

# --- 2. THE VAULT ---
if "GEMINI_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_KEY"]
else:
    api_key = st.text_input("Enter Gemini API Key:", type="password")

# --- 3. INPUT SECTION ---
video_url = st.text_input("Paste Link (YouTube, Instagram, TikTok):", value=url_from_iphone)

def get_valid_model():
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name: return m.name
        return 'models/gemini-pro'
    except:
        return 'gemini-pro'

def extract_youtube_id(url):
    if "youtu.be" in url: return url.split("/")[-1].split("?")[0]
    if "v=" in url: return url.split("v=")[1].split("&")[0]
    return None

def get_stealth_transcript(url):
    transcript_text = None
    
    # --- STRATEGY A: YouTube Native API ---
    if ("youtube.com" in url or "youtu.be" in url) and YouTubeTranscriptApi:
        try:
            video_id = extract_youtube_id(url)
            if video_id:
                # Try to get the official transcript
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = " ".join([entry['text'] for entry in transcript_list])
                return transcript_text # Success! Return immediately.
        except Exception:
            # If API fails, silently fall through to Strategy B (Safety Net)
            pass

    # --- STRATEGY B: The "Disguised" Downloader (Instagram/TikTok/Backup) ---
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            captions = info.get('subtitles') or info.get('automatic_captions')
            
            if not captions: return "Error: No captions found."

            lang = 'en'
            if 'en' not in captions:
                for code in captions:
                    if code.startswith('en'):
                        lang = code
                        break
                else:
                    lang = list(captions.keys())[0]

            cap_formats = captions[lang]
            json_url = None
            for fmt in cap_formats:
                if fmt['ext'] == 'json3':
                    json_url = fmt['url']
                    break
            if not json_url: json_url = cap_formats[0]['url']

            headers = {'User-Agent': ydl_opts['user_agent']}
            response = requests.get(json_url, headers=headers)
            
            try:
                data = response.json()
                events = data.get('events', [])
                full_text = []
                for event in events:
                    segs = event.get('segs', [])
                    for seg in segs:
                        if seg.get('utf8'): full_text.append(seg['utf8'])
                return " ".join(full_text)
            except:
                return response.text
    except Exception as e:
        return f"Download Error: {e}"

if st.button("Rip Recipe"):
    if not api_key or not video_url:
        st.error("Missing Info!")
    else:
        with st.spinner("Hunting for captions..."):
            transcript_text = get_stealth_transcript(video_url)

        if "Error" in transcript_text:
            st.error(transcript_text)
        else:
            try:
                genai.configure(api_key=api_key)
                valid_model_name = get_valid_model()
                
                with st.spinner("Chef is cooking..."):
                    model = genai.GenerativeModel(valid_model_name)
                    prompt = f"""
                    You are a professional chef. Analyze this transcript.
                    
                    SECTION 1: SUMMARY
                    Format: "Difficulty Level | Estimated Time"
                    
                    SECTION 2: INSTRUCTIONS
                    Step-by-step summary.
                    
                    SECTION 3: INGREDIENTS
                    List separated by | (pipe) symbols.
                    Example: Eggs | Milk | Flour
                    
                    FORMATTING: Use "###SPLIT###" between sections.
                    
                    Transcript: {transcript_text[:15000]}
                    """
                    response = model.generate_content(prompt)
                    full_text = response.text
                    parts = full_text.split("###SPLIT###")
                    
                    if len(parts) >= 3:
                        meta = parts[0].strip()
                        instr = parts[1].strip()
                        ingred = parts[2].strip()
                    else:
                        meta = "Unknown"
                        instr = full_text
                        ingred = ""

                    st.success("Done!")
                    st.info(f"**Meta:** {meta}")
                    st.subheader("📝 Instructions")
                    st.write(instr)
                    st.subheader("🛒 Shopping")
                    
                    clean_ingred = ingred.replace("\n", "|").split("|")
                    for item in clean_ingred:
                        if item.strip():
                            c1, c2 = st.columns([3,1])
                            c1.write(f"- {item.strip()}")
                            enc = urllib.parse.quote(item.strip())
                            c2.link_button("Buy", f"https://www.instacart.com/store/s?k={enc}")
                            
            except Exception as e:
                st.error(f"AI Error: {e}")