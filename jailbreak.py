import streamlit as st
import google.generativeai as genai
import re

# We use pytubefix because your local youtube-transcript-api is corrupted
try:
    from pytubefix import YouTube
except ImportError:
    st.error("🚨 Missing pytubefix. Please run: pip install pytubefix")
    st.stop()

st.set_page_config(page_title="Chef Vibe: Jailbreak", page_icon="🔓")
st.title("🔓 Chef Vibe: Final Fix")

# 1. Inputs
api_key = st.text_input("Enter Gemini API Key:", type="password")
video_url = st.text_input("Paste YouTube URL:")

def get_transcript_pytube(url):
    try:
        yt = YouTube(url)
        # Get English captions (auto-generated or manual)
        caption = yt.captions.get_by_language_code('en')
        if not caption:
            # Try 'a.en' (auto-generated english) if 'en' fails
            caption = yt.captions.get_by_language_code('a.en')
        
        if caption:
            # Convert XML to pure text using Regex
            xml_text = caption.xml_captions
            clean_text = re.sub(r'<[^>]+>', ' ', xml_text)
            return clean_text
        else:
            return None
    except Exception as e:
        return f"Error: {e}"

if st.button("Rip Recipe"):
    if not api_key or not video_url:
        st.error("Missing Info!")
    else:
        with st.spinner("🔓 Bypassing broken library..."):
            # Use the new tool
            full_text = get_transcript_pytube(video_url)

        if not full_text or "Error" in full_text:
            st.error(f"Could not get transcript. Details: {full_text}")
        else:
            try:
                with st.spinner("👨‍🍳 Cooking list..."):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""
                    Extract ingredients from this transcript.
                    Output ONLY a list of ingredients separated by a pipe symbol (|).
                    Example: Eggs | Flour | Milk
                    Transcript: {full_text[:10000]}
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
                                clean_item = item.strip().replace(" ", "+")
                                st.link_button("Buy ↗️", f"https://www.instacart.com/store/search?term={clean_item}")
            except Exception as e:
                st.error(f"AI Error: {e}")