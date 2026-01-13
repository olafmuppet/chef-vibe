import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

st.set_page_config(page_title="Chef Vibe Final", page_icon="🥗")
st.title("🥗 Chef Vibe: Final Reset")

# 1. Inputs
api_key = st.text_input("Enter Gemini API Key:", type="password")
video_url = st.text_input("Paste YouTube URL:")

if st.button("Rip Recipe"):
    if not api_key or not video_url:
        st.error("Missing Info!")
    else:
        try:
            # URL Logic
            if "youtu.be" in video_url:
                vid_id = video_url.split("/")[-1].split("?")[0]
            elif "shorts" in video_url:
                vid_id = video_url.split("shorts/")[1].split("?")[0]
            else:
                vid_id = video_url.split("v=")[1].split("&")[0]

            with st.spinner("Gettting Transcript..."):
                transcript = YouTubeTranscriptApi.get_transcript(vid_id)
                full_text = " ".join([t['text'] for t in transcript])
            
            with st.spinner("AI Extracting..."):
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(f"Extract ingredients from: {full_text[:10000]}. Return ONLY list separated by |")
                
                st.success("Done!")
                items = response.text.split("|")
                for item in items:
                    if item.strip():
                        col1, col2 = st.columns([3, 1])
                        with col1: st.checkbox(item.strip())
                        with col2: st.link_button("Buy ↗️", f"https://www.instacart.com/store/search?term={item.strip()}")
                        
        except Exception as e:
            st.error(f"Error: {e}")