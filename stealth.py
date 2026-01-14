import streamlit as st
import google.generativeai as genai
import requests
from yt_dlp import YoutubeDL
import urllib.parse

# --- 1. SETUP PAGE & CAPTURE URL ---
st.set_page_config(page_title="Chef Vibe", page_icon="🥂")

# The "Catcher's Mitt": Grabs the link sent from your iPhone
params = st.query_params
url_from_iphone = params.get("url", "")

st.title("🥂 Chef Vibe")

# --- 2. THE VAULT (API KEY) ---
if "GEMINI_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_KEY"]
else:
    api_key = st.text_input("Enter Gemini API Key:", type="password")

# --- 3. INPUT SECTION ---
# This box now accepts any link and auto-fills from the Shortcut
video_url = st.text_input("Paste Link (Instagram, TikTok, YouTube):", value=url_from_iphone)

# --- 4. THE REST OF YOUR FUNCTIONS ---
def get_valid_model():
    """Asks Google which model we are allowed to use."""
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'gemini' in m.name:
                    return m.name
        return 'models/gemini-pro'
    except:
        return 'gemini-pro'

def get_stealth_transcript(url):
   # DISGUISE MODE: Pretend to be an iPhone 17 using Safari
    # ATTEMPT 3: Force the internal iOS API client
    # HYBRID FIX: Force iOS API but keep the User-Agent to prevent crashing
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        # 1. Keep this so the code below doesn't crash
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        # 2. Force the internal iOS API for Instagram
        'extractor_args': {'instagram': {'imp': ['ios']}},
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
        return f"Error: {e}"

if st.button("Rip Recipe"):
    if not api_key or not video_url:
        st.error("Missing Info!")
    else:
        with st.spinner("Step 1: Downloading Transcript..."):
            transcript_text = get_stealth_transcript(video_url)

        if "Error" in transcript_text:
            st.error(transcript_text)
        else:
            try:
                genai.configure(api_key=api_key)
                valid_model_name = get_valid_model()
                
                with st.spinner(f"Step 2: AI Chef ({valid_model_name}) is grading & cooking..."):
                    model = genai.GenerativeModel(valid_model_name)
                    
                    # --- UPDATED PROMPT: Stronger formatting rules ---
                    prompt = f"""
                    You are a professional chef. Analyze this transcript.
                    
                    SECTION 1: SUMMARY
                    Format exactly like this: "Difficulty Level | Estimated Time"
                    Example: Medium | 45 Mins
                    
                    SECTION 2: INSTRUCTIONS
                    Create a concise, numbered step-by-step summary.
                    
                    SECTION 3: INGREDIENTS
                    List ingredients with ESTIMATED quantities if missing.
                    IMPORTANT: You MUST separate every single ingredient with a vertical pipe symbol (|). Do NOT use newlines for the list.
                    Example: 2 Eggs | 1 cup Flour | Salt
                    
                    FORMATTING RULE:
                    Use "###SPLIT###" to separate the three sections.
                    
                    Transcript: {transcript_text[:15000]}
                    """
                    
                    response = model.generate_content(prompt)
                    
                    # --- PARSING ---
                    full_text = response.text
                    parts = full_text.split("###SPLIT###")
                    
                    if len(parts) >= 3:
                        meta_info = parts[0].strip() # Difficulty | Time
                        instructions = parts[1].strip()
                        ingredients_raw = parts[2].strip()
                        
                        # Split Difficulty and Time
                        if "|" in meta_info:
                            difficulty, est_time = meta_info.split("|", 1)
                        else:
                            difficulty = meta_info
                            est_time = "Unknown"
                            
                    else:
                        difficulty = "Unknown"
                        est_time = ""
                        instructions = "Could not parse."
                        ingredients_raw = full_text
                    
                    st.success("Recipe Ripped!")
                    
                    # SECTION 1: METADATA ROW
                    c1, c2 = st.columns(2)
                    with c1:
                        if "Easy" in difficulty:
                            st.info(f"**Level:** {difficulty} 🟢")
                        elif "Medium" in difficulty:
                            st.warning(f"**Level:** {difficulty} 🟡")
                        else:
                            st.error(f"**Level:** {difficulty} 🔴")
                    with c2:
                        st.success(f"**Time:** {est_time} ⏰")
                    
                    # SECTION 2: INSTRUCTIONS
                    st.subheader("📝 Quick Guide")
                    st.markdown(instructions)
                    
                    st.markdown("---")
                    
                    # SECTION 3: SHOPPING LIST
                    st.subheader("🛒 Shopping List")
                    
                    # Force clean splitting even if AI uses newlines instead of pipes
                    clean_raw = ingredients_raw.replace("\n", "|")
                    items = clean_raw.split("|")
                    
                    for i, item in enumerate(items):
                        if item.strip() and "###" not in item:
                            col1, col2 = st.columns([3, 1])
                            with col1: 
                                st.checkbox(item.strip(), key=f"chk_{i}")
                            
                            encoded_item = urllib.parse.quote(item.strip())
                            instacart_url = f"https://www.instacart.com/store/s?k={encoded_item}"
                            
                            with col2: st.link_button("Buy ↗️", instacart_url)
            except Exception as e:
                st.error(f"AI Error: {e}")