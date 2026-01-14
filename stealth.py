import streamlit as st
import google.generativeai as genai
import requests
from yt_dlp import YoutubeDL
import urllib.parse
# Wrap import to prevent crash if library is missing
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Chef Vibe", page_icon="🥂")

# Capture URL from iPhone Shortcut
params = st.query_params
url_from_iphone = params.get("url", "")

st.title("🥂 Chef Vibe")

# --- 2. AUTHENTICATION ---
if "GEMINI_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_KEY"]
else:
    api_key = st.text_input("Enter Gemini API Key:", type="password")

# --- 3. INPUT ---
video_url = st.text_input("Paste Link (YouTube, Instagram, TikTok):", value=url_from_iphone)

# --- 4. HELPER FUNCTIONS ---
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
    
    # STRATEGY A: YouTube Native API
    if ("youtube.com" in url or "youtu.be" in url) and YouTubeTranscriptApi:
        try:
            video_id = extract_youtube_id(url)
            if video_id:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                transcript_text = " ".join([entry['text'] for entry in transcript_list])
                return transcript_text
        except Exception:
            pass # Fallback to Strategy B

    # STRATEGY B: The Disguised Downloader
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

# --- 5. APP LOGIC ---
if st.button("Rip Recipe"):
    if not api_key or not video_url:
        st.error("Missing Info!")
    else:
        with st.spinner("Finding recipe..."):
            transcript_text = get_stealth_transcript(video_url)

        if "Error" in transcript_text:
            st.error(transcript_text)
        else:
            try:
                genai.configure(api_key=api_key)
                valid_model_name = get_valid_model()
                
                with st.spinner("Chef is writing the shopping list..."):
                    model = genai.GenerativeModel(valid_model_name)
                    
                    # UPDATED PROMPT: Demands quantities and clean formatting
                    prompt = f"""
                    You are a professional chef. Extract the recipe from this transcript.
                    
                    OUTPUT FORMAT:
                    
                    SECTION 1: METADATA
                    Format: "Difficulty | Time"
                    Example: Easy | 15 Mins
                    
                    SECTION 2: INSTRUCTIONS
                    Write a clean, numbered list of steps. Do NOT use the word "Section".
                    
                    SECTION 3: INGREDIENTS
                    List ingredients with SPECIFIC quantities or weights (estimate if not stated).
                    Must be separated by the pipe symbol (|).
                    Example: 200g Chicken | 1 tsp Salt | 2 cups Rice
                    
                    SEPARATOR:
                    Use "###SPLIT###" strictly between the three sections.
                    
                    Transcript: {transcript_text[:15000]}
                    """
                    
                    response = model.generate_content(prompt)
                    parts = response.text.split("###SPLIT###")
                    
                    if len(parts) >= 3:
                        meta = parts[0].strip()
                        instr = parts[1].strip()
                        ingred = parts[2].strip()
                    else:
                        meta = "Unknown | Unknown"
                        instr = response.text
                        ingred = ""

                    # --- UI DISPLAY ---
                    
                    # 1. METADATA (Clean Row)
                    if "|" in meta:
                        diff, time = meta.split("|", 1)
                    else:
                        diff, time = meta, ""
                        
                    c1, c2 = st.columns(2)
                    c1.info(f"**Level:** {diff.strip()}")
                    c2.success(f"**Time:** {time.strip()}")
                    
                    st.divider()
                    
                    # 2. INSTRUCTIONS
                    st.subheader("📝 Instructions")
                    st.markdown(instr)
                    
                    st.divider()
                    
                    # 3. SHOPPING LIST (Aligned Buttons)
                    st.subheader("🛒 Shopping List")
                    
                    # Clean up newlines or weird formatting from AI
                    clean_ingred = ingred.replace("\n", "|").split("|")
                    
                    for item in clean_ingred:
                        clean_item = item.strip()
                        # Filter out empty strings or accidental headers
                        if clean_item and "Section" not in clean_item and "###" not in clean_item:
                            
                            # Layout: Text takes 3 parts, Button takes 1 part
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write(f"• **{clean_item}**")
                            
                            with col2:
                                # Create Instacart Search Link
                                query = urllib.parse.quote(clean_item)
                                url = f"https://www.instacart.com/store/s?k={query}"
                                st.link_button("Buy", url)
                            
            except Exception as e:
                st.error(f"AI Error: {e}")