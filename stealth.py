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
st.set_page_config(
    page_title="Chef Vibe", 
    page_icon="🥂",
    layout="centered"
)

# --- CUSTOM CSS (The Aesthetics) ---
st.markdown("""
<style>
    /* Import nice Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Poppins', sans-serif;
    }

    /* Center the Main Title & Color it Chef Red */
    .stApp h1 {
        text-align: center;
        color: #FF4B4B; 
        font-weight: 700;
        margin-bottom: 10px;
    }
    
    /* Style the 'Lets Do This' Button */
    .stButton > button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        border-radius: 12px;
        padding: 15px 20px;
        font-size: 18px;
        font-weight: 600;
        border: none;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: #D43F3F;
        transform: scale(1.02);
        color: white;
    }

    /* Hide Streamlit Footer & Menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

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
if st.button("Lets Do This! 🚀"):
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
                    
                    # UPDATED PROMPT: "Smart Estimate" Logic
                    prompt = f"""
                    You are a professional chef. Extract the recipe from this transcript.
                    
                    CRITICAL INSTRUCTION FOR INGREDIENTS:
                    1. ACCURACY FIRST: If the transcript explicitly mentions a quantity (e.g., "2 cups", "10 oz", "a handful"), USE IT exactly. Do NOT label it as "Estimated".
                    2. GAPS ONLY: Only if the transcript is completely silent on quantity, you must estimate it based on cooking ratios.
                    3. LABELING: If you had to guess the quantity (Rule #2), prefix it with "(Est.)". If it was in the video, do NOT add a prefix.
                    4. FORMAT: Always use "Quantity + Ingredient Name" (e.g., "12 oz Pasta").
                    5. CLEANUP: Never list "to taste" or "garnish" as a separate line.
                    
                    OUTPUT FORMAT:
                    
                    SECTION 1: METADATA
                    Format: "Difficulty | Time"
                    Example: Easy | 15 Mins
                    
                    SECTION 2: INSTRUCTIONS
                    Write a clean, numbered list of steps. Do NOT use the word "Section".
                    
                    SECTION 3: INGREDIENTS
                    Format: Quantity + Item.
                    Must be separated by the pipe symbol (|).
                    
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
                    
                    # 1. METADATA
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
                    
                    # 3. SHOPPING LIST (Mobile Optimized)
                    st.subheader("🛒 Shopping List")
                    
                    clean_ingred = ingred.replace("\n", "|").split("|")
                    
                    for item in clean_ingred:
                        clean_item = item.strip()
                        if clean_item and "Section" not in clean_item and "###" not in clean_item:
                            
                            if clean_item.lower() == "to taste":
                                continue
                                
                            # Encode for URL
                            query = urllib.parse.quote(clean_item)
                            url = f"https://www.instacart.com/store/s?k={query}"
                            
                            # MOBILE FIX: Use Markdown link to keep buy button inline
                            st.markdown(f"• **{clean_item}** — [**Buy ↗️**]({url})")
                            
            except Exception as e:
                st.error(f"AI Error: {e}")