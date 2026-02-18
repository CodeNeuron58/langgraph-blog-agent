import streamlit as st
import os
import json
from pathlib import Path
from src.graph import app as graph_app
from src.schemas import Plan, Task

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
st.info("The agent will show its thinking process, decision making, and raw state below.")

# Input Form
with st.form("blog_form"):
    topic = st.text_input("Enter a topic:", placeholder="e.g., The Future of Multi-Agent Systems")
    submitted = st.form_submit_button("Generate Blog")

if submitted and topic:
    st.markdown("### 🚀 Agent Execution Log")
    
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
    
    final_content = ""
    
    try:
        # Stream the graph execution
        stream = graph_app.stream(initial_state)
        
        for event in stream:
            for node_name, state_update in event.items():
                
                # --- Create a section for each node ---
                with st.expander(f"Step: {node_name.upper()}", expanded=True):
                    
                    # 1. Router Node
                    if node_name == "router":
                        st.write(f"**Mode Selected:** `{state_update.get('mode')}`")
                        st.write(f"**Needs Research:** `{state_update.get('needs_research')}`")
                        if state_update.get('queries'):
                            st.write("**Queries Generated:**")
                            st.json(state_update['queries'])
                    
                    # 2. Research Node
                    elif node_name == "research":
                        evidence = state_update.get('evidence', [])
                        st.write(f"**Evidence Found:** {len(evidence)} items")
                        if evidence:
                            st.write("**Sources:**")
                            for item in evidence:
                                st.markdown(f"- [{item.title}]({item.url})")
                    
                    # 3. Orchestrator Node (The Plan)
                    elif node_name == "orchestrator":
                        plan_data = state_update.get('plan')
                        if plan_data:
                            # If it's a Pydantic model (Plan object), dump it
                            if hasattr(plan_data, 'model_dump'):
                                plan_dict = plan_data.model_dump()
                            else:
                                plan_dict = plan_data
                                
                            st.success("✅ implementation Plan generated!")
                            st.write(f"**Blog Title:** {plan_dict.get('blog_title')}")
                            st.write(f"**Target Audience:** {plan_dict.get('audience')}")
                            
                            st.write("**Tasks / Sections:**")
                            tasks = plan_dict.get('tasks', [])
                            for t in tasks:
                                st.markdown(f"- **{t['title']}** ({t['target_words']} words): {t['goal']}")

                    # 4. Worker Node
                    elif node_name == "worker":
                        sections = state_update.get('sections', [])
                        for _, sec_content in sections:
                            # Extract title usually in first line
                            lines = sec_content.strip().split('\n')
                            title = lines[0] if lines else "Section"
                            st.text(f"Generated section: {title}")
                            with st.expander("View Section Content"):
                                st.markdown(sec_content)

                    # 5. Reducer (Final)
                    elif node_name == "reducer":
                        final_content = state_update.get('final')
                        st.success("🎉 Blog generation complete!")

                    # --- Full State Dump for "Everything that's happening" ---
                    st.divider()
                    st.caption("Raw State Update")
                    st.json(state_update)

        if final_content:
            st.markdown("### 📄 Final Blog Output")
            st.markdown("---")
            st.markdown(final_content)
            # Rerun to update sidebar list (optional, but good for UX)
            # We can't rerun immediately inside the loop easily without interrupting stream
            # so we just let it be.
            
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
