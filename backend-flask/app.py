import streamlit as st
from rag_agent_system import RAGAgentSystem
import os
import tempfile

# Page configuration
st.set_page_config(
    page_title="Multi-Agent RAG System",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'rag_system' not in st.session_state:
    st.session_state.rag_system = RAGAgentSystem()
if 'current_agent' not in st.session_state:
    st.session_state.current_agent = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = {}

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
    .agent-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.header("📋 Navigation")
    
    # Main pages
    main_pages = ["🏠 Home", "➕ Create Agent", "💬 Query Agent", "⚙️ Manage Agents"]
    
    # Agent chatbot pages
    agents = st.session_state.rag_system.list_agents()
    agent_pages = [f"🤖 {agent['name']}" for agent in agents]
    
    # Combine all pages
    all_pages = main_pages + (["---"] if agent_pages else []) + agent_pages
    
    page = st.radio("Select Page:", all_pages, index=0)
    
    st.divider()
    st.subheader("ℹ️ System Info")
    st.info("""
    **Tech Stack:**
    - LLM: Llama 3.2 (Ollama)
    - Embeddings: mxbai-embed-large
    - Vector DB: FAISS
    - Framework: LangChain LCEL
    """)
    
    # Show agent count
    st.metric("Total Agents", len(agents))
    
    if agent_pages:
        st.divider()
        st.caption("💡 Click on agent names to open their chatbot")

# Check if it's an agent chatbot page
is_agent_page = page.startswith("🤖 ")

# Main content for agent chatbot pages
if is_agent_page:
    agent_name = page.replace("🤖 ", "")
    agent_info = st.session_state.rag_system.get_agent_info(agent_name)
    
    if agent_info:
        # Agent Header
        st.markdown(f"""
        <div class="agent-header">
            <h1>🤖 {agent_name}</h1>
            <p style='font-size: 1.2rem; margin-top: 0.5rem;'>
                <strong>Domain:</strong> {agent_info['domain'] or 'General'}
            </p>
            <p style='margin-top: 0.5rem;'>{agent_info['description'] or 'No description provided'}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Initialize chat history for this agent
        if agent_name not in st.session_state.chat_history:
            st.session_state.chat_history[agent_name] = []
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history[agent_name]:
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="chat-message user-message">
                        <strong>👤 You:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="chat-message assistant-message">
                        <strong>🤖 {agent_name}:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
        
        # Chat input section
        st.divider()
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            user_query = st.text_input(
                "Ask a question:",
                key=f"chat_input_{agent_name}",
                placeholder="Type your question here..."
            )
        
        with col2:
            k_value = st.number_input("Top K", min_value=1, max_value=10, value=4, key=f"k_{agent_name}")
        
        col_send, col_clear = st.columns(2)
        
        with col_send:
            send_button = st.button("📤 Send", type="primary", key=f"send_{agent_name}")
        
        with col_clear:
            clear_button = st.button("🗑️ Clear Chat", key=f"clear_{agent_name}")
        
        # Handle send button
        if send_button and user_query:
            # Add user message to history
            st.session_state.chat_history[agent_name].append({
                "role": "user",
                "content": user_query
            })
            
            # Get response from agent
            with st.spinner("🤔 Thinking..."):
                result = st.session_state.rag_system.query_agent(
                    agent_name=agent_name,
                    query=user_query,
                    k=k_value
                )
                
                if result["success"]:
                    # Add assistant response to history
                    st.session_state.chat_history[agent_name].append({
                        "role": "assistant",
                        "content": result["answer"]
                    })
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
        
        # Handle clear button
        if clear_button:
            st.session_state.chat_history[agent_name] = []
            st.rerun()
        
        # Agent info in expander
        with st.expander("📊 Agent Information"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Document Chunks", agent_info['num_documents'])
            with col_b:
                st.metric("PDF Files", len(agent_info['pdf_files']))
            
            st.write("**PDF Files:**")
            for pdf in agent_info['pdf_files']:
                st.text(f"• {pdf}")

# Main pages content
elif page == "🏠 Home":
    st.markdown('<div class="main-header">🤖 Multi-Agent RAG System</div>', unsafe_allow_html=True)
    st.markdown("##### Powered by Llama 3.2, mxbai-embed-large & FAISS")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**📚 Create Agents**\n\nBuild custom RAG agents with your PDF documents")
    
    with col2:
        st.success("**💬 Chat with Agents**\n\nOpen dedicated chatbot pages for each agent")
    
    with col3:
        st.warning("**⚙️ Manage**\n\nView and delete existing agents")
    
    st.divider()
    
    st.subheader("🚀 Getting Started")
    st.markdown("""
    1. **Create an Agent**: Upload PDFs and specify a domain
    2. **Open Agent Chatbot**: Click on agent name in sidebar to open dedicated chat page
    3. **Have Conversations**: Chat naturally with your specialized agents
    
    Each agent has its own isolated knowledge base and chat interface!
    """)
    
    # Show agents
    agents = st.session_state.rag_system.list_agents()
    if agents:
        st.subheader("📊 Your Agents")
        for agent in agents:
            with st.expander(f"🤖 {agent['name']}"):
                st.write(f"**Domain:** {agent['domain'] or 'General'}")
                st.write(f"**Description:** {agent['description'] or 'No description'}")
                st.write(f"**Documents:** {agent['num_documents']} chunks")
                st.write(f"**Files:** {len(agent['pdf_files'])} PDFs")
                if st.button(f"Open {agent['name']} Chatbot", key=f"open_{agent['name']}"):
                    st.info(f"Click on '🤖 {agent['name']}' in the sidebar to open the chatbot!")

elif page == "➕ Create Agent":
    st.header("➕ Create New RAG Agent")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        agent_name = st.text_input(
            "Agent Name *",
            placeholder="e.g., Research Assistant, Legal Advisor"
        )
        
        domain = st.text_input(
            "Domain *",
            placeholder="e.g., Medical, Legal, Technology, Finance"
        )
        
        description = st.text_area(
            "Description (Optional)",
            placeholder="Describe what this agent will do...",
            height=100
        )
        
        uploaded_files = st.file_uploader(
            "Upload PDF Documents *",
            type=['pdf'],
            accept_multiple_files=True,
            help="Upload one or more PDF files for this agent's knowledge base"
        )
        
        if uploaded_files:
            st.info(f"📄 {len(uploaded_files)} file(s) selected")
        
        if st.button("🚀 Create Agent", type="primary"):
            if not agent_name:
                st.error("⚠️ Please provide an agent name")
            elif not domain:
                st.error("⚠️ Please provide a domain")
            elif not uploaded_files:
                st.error("⚠️ Please upload at least one PDF file")
            else:
                with st.spinner("🔄 Creating agent and processing PDFs..."):
                    temp_paths = []
                    try:
                        for uploaded_file in uploaded_files:
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                                tmp_file.write(uploaded_file.getvalue())
                                temp_paths.append(tmp_file.name)
                        
                        result = st.session_state.rag_system.create_agent(
                            agent_name=agent_name,
                            pdf_paths=temp_paths,
                            description=description,
                            domain=domain
                        )
                        
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            st.balloons()
                            st.info(f"💡 Click on '🤖 {agent_name}' in the sidebar to open the chatbot!")
                            # Force refresh to show new agent in sidebar
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")
                    
                    finally:
                        for path in temp_paths:
                            try:
                                os.unlink(path)
                            except OSError as e:
                                print(f"Warning: Failed to clean up temp file {path}: {e}")
    
    with col2:
        st.subheader("📝 Quick Guide")
        st.markdown("""
        **Steps:**
        1. Enter unique agent name
        2. Specify domain/expertise
        3. Add description (optional)
        4. Upload PDF documents
        5. Click 'Create Agent'
        
        **After Creation:**
        - Agent appears in sidebar
        - Click to open chatbot page
        - Start chatting!
        
        **Tips:**
        - Use clear domain names
        - Upload related PDFs
        - Each agent is isolated
        """)

elif page == "💬 Query Agent":
    st.header("💬 Quick Query (Single Question)")
    st.caption("For full conversations, use the agent chatbot pages from the sidebar")
    
    agents = st.session_state.rag_system.list_agents()
    
    if not agents:
        st.warning("⚠️ No agents available. Please create an agent first.")
    else:
        agent_names = [agent["name"] for agent in agents]
        selected_agent = st.selectbox(
            "🤖 Select Agent",
            agent_names,
            key="query_agent_select"
        )
        
        if selected_agent:
            agent_info = next(a for a in agents if a["name"] == selected_agent)
            
            st.info(f"💡 For full chat experience, click on '🤖 {selected_agent}' in the sidebar!")
            
            with st.expander("📊 Agent Information"):
                st.write(f"**Domain:** {agent_info['domain'] or 'General'}")
                st.write(f"**Description:** {agent_info['description'] or 'No description'}")
                st.write(f"**Documents:** {agent_info['num_documents']} chunks")
        
        query = st.text_area(
            "💭 Enter your question",
            placeholder="Ask something based on the agent's knowledge...",
            height=120
        )
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            k_value = st.number_input("Top K docs", min_value=1, max_value=10, value=4)
        
        if st.button("🔍 Ask Question", type="primary"):
            if not query:
                st.error("⚠️ Please enter a question")
            else:
                with st.spinner("🤔 Thinking..."):
                    result = st.session_state.rag_system.query_agent(
                        agent_name=selected_agent,
                        query=query,
                        k=k_value
                    )
                    
                    if result["success"]:
                        st.success("✅ Answer generated!")
                        st.subheader("📝 Answer:")
                        st.write(result["answer"])
                        
                        with st.expander("📚 View Source Documents"):
                            for i, doc in enumerate(result["source_documents"], 1):
                                st.markdown(f"**Source {i}:**")
                                st.text(doc[:500] + "..." if len(doc) > 500 else doc)
                                if i < len(result["source_documents"]):
                                    st.divider()
                    else:
                        st.error(f"❌ {result['error']}")

else:  # Manage Agents
    st.header("⚙️ Manage RAG Agents")
    
    agents = st.session_state.rag_system.list_agents()
    
    if not agents:
        st.info("ℹ️ No agents created yet. Go to 'Create Agent' to get started.")
    else:
        st.subheader(f"📊 Total Agents: {len(agents)}")
        st.divider()
        
        for agent in agents:
            with st.container():
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    st.markdown(f"### 🤖 {agent['name']}")
                    st.write(f"**Domain:** {agent['domain'] or 'General'}")
                    st.write(f"**Description:** {agent['description'] or 'No description'}")
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Document Chunks", agent['num_documents'])
                    with col_b:
                        st.metric("PDF Files", len(agent['pdf_files']))
                    with col_c:
                        if st.button(f"💬 Open Chat", key=f"chat_{agent['name']}"):
                            st.info(f"Click '🤖 {agent['name']}' in the sidebar!")
                    
                    with st.expander("📄 View PDF Files"):
                        for pdf in agent['pdf_files']:
                            st.text(f"• {pdf}")
                
                with col2:
                    st.write("")
                    st.write("")
                    if st.button("🗑️", key=f"delete_{agent['name']}", help="Delete agent"):
                        if st.session_state.get(f"confirm_delete_{agent['name']}", False):
                            result = st.session_state.rag_system.delete_agent(agent['name'])
                            if result["success"]:
                                # Clear chat history for deleted agent
                                if agent['name'] in st.session_state.chat_history:
                                    del st.session_state.chat_history[agent['name']]
                                st.success(result["message"])
                                st.rerun()
                            else:
                                st.error(result["error"])
                        else:
                            st.session_state[f"confirm_delete_{agent['name']}"] = True
                            st.warning("Click again to confirm")
                
                st.divider()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <strong>Multi-Agent RAG System</strong><br>
    Built with LangChain LCEL • Streamlit • Ollama • FAISS<br>
    Each agent has its own dedicated chatbot interface
</div>
""", unsafe_allow_html=True)