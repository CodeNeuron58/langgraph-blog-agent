import streamlit as st
import os
from pathlib import Path
from src.graph import app as graph_app

# --- Configuration ---
BLOG_DIR = Path("generated_blogs")
BLOG_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="LangGraph Blog Agent",
    page_icon="📝",
    layout="wide"
)

# --- Sidebar: History & Downloads ---
st.sidebar.header("📚 Generated Blogs")
st.sidebar.info("Select a blog below to download.")

# Refresh list of files
blog_files = list(BLOG_DIR.glob("*.md"))
blog_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

selected_file = None
if blog_files:
    selected_file_name = st.sidebar.selectbox(
        "Select a file:",
        options=[f.name for f in blog_files],
        index=0
    )
    if selected_file_name:
        selected_file = BLOG_DIR / selected_file_name
        
        # Download Button
        with open(selected_file, "r", encoding="utf-8") as f:
            st.sidebar.download_button(
                label="⬇️ Download Markdown",
                data=f,
                file_name=selected_file_name,
                mime="text/markdown"
            )
else:
    st.sidebar.text("No blogs generated yet.")


# --- Main Content ---
st.title("📝 LangGraph Blog Agent")
st.markdown("Generate high-quality technical blog posts using AI agents.")

# Input Form
with st.form("blog_form"):
    topic = st.text_input("Enter a topic:", placeholder="e.g., The Future of Multi-Agent Systems")
    submitted = st.form_submit_button("Generate Blog")

if submitted and topic:
    with st.spinner(f"Running agents for topic: '{topic}'... This may take a minute."):
        try:
            initial_state = {
                "topic": topic,
                "mode": "",
                "needs_research": False,
                "queries": [],
                "evidence": [],
                "plan": None,
                "sections": [],
                "final": "",
            }
            
            # Execute the graph
            result = graph_app.invoke(initial_state)
            
            final_content = result.get("final", "")
            
            if final_content:
                st.success("Blog generated successfully!")
                st.markdown("---")
                st.markdown(final_content)
                
                # Rerun to update sidebar list
                st.rerun()
            else:
                st.error("Failed to generate content. Please try again.")
                
        except Exception as e:
            st.error(f"An error occurred: {e}")

elif submitted and not topic:
    st.warning("Please enter a topic.")

# --- Display Selected Blog from Sidebar ---
if selected_file and not submitted:
    st.markdown("---")
    st.subheader(f"Viewing: {selected_file.name}")
    try:
        content = selected_file.read_text(encoding="utf-8")
        st.markdown(content)
    except Exception as e:
        st.error(f"Error reading file: {e}")
