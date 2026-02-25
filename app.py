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

# Removed old sidebar logic


# --- Main Content ---
st.title("📝 LangGraph Blog Agent")
st.markdown("Generate high-quality technical blog posts using AI agents.")

tab_generate, tab_view = st.tabs(["🚀 Generate New Blog", "📚 View & Manage Blogs"])

# --- TAB 1: GENERATE ---
with tab_generate:
    st.info("The agent will show its thinking process, decision making, and raw state below.")

    with st.form("blog_form"):
        topic = st.text_input("Enter a topic:", placeholder="e.g., The Future of Multi-Agent Systems")
        submitted = st.form_submit_button("Generate Blog")

    if submitted and topic:
        st.markdown("### ⚙️ Agent Execution Log")
        
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
                                if hasattr(plan_data, 'model_dump'):
                                    plan_dict = plan_data.model_dump()
                                else:
                                    plan_dict = plan_data
                                    
                                st.success("✅ Implementation Plan generated!")
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
                                lines = sec_content.strip().split('\n')
                                title = lines[0] if lines else "Section"
                                st.text(f"Generated section: {title}")
                                with st.expander("View Section Draft"):
                                    st.markdown(sec_content)

                        # 5. Reducer (Final)
                        elif node_name == "reducer":
                            final_content = state_update.get('final')
                            st.success("🎉 Blog generation complete! Go to the 'View & Manage Blogs' tab to read it.")

        except Exception as e:
            st.error(f"An error occurred: {e}")

    elif submitted and not topic:
        st.warning("Please enter a topic.")


# --- TAB 2: VIEW & MANAGE ---
with tab_view:
    # Refresh list of files dynamically in this tab
    blog_files = list(BLOG_DIR.glob("*.md"))
    blog_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    if blog_files:
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("Saved Blogs")
            selected_file_name = st.radio(
                "Select a blog:",
                options=[f.name for f in blog_files],
                index=0
            )
            
            if selected_file_name:
                selected_file = BLOG_DIR / selected_file_name
                with open(selected_file, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="⬇️ Download Markdown",
                        data=f,
                        file_name=selected_file_name,
                        mime="text/markdown",
                        use_container_width=True
                    )
        
        with col2:
            if selected_file_name:
                selected_file = BLOG_DIR / selected_file_name
                st.markdown("---")
                try:
                    content = selected_file.read_text(encoding="utf-8")
                    st.markdown(content)
                except Exception as e:
                    st.error(f"Error reading file: {e}")
    else:
        st.info("No blogs generated yet. Go to the 'Generate New Blog' tab to create one!")
