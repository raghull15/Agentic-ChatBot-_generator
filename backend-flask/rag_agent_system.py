import os
import uuid
import time
from collections import defaultdict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from pypdf import PdfReader
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta

# MongoDB imports
from db import get_agents_collection, get_token_usage_collection

# Token counting
from token_counter import calculate_token_usage

# Data source connectors
from data_sources import CSVSource, WordSource, SQLSource, NoSQLSource, TXTSource


class RAGAgentSystem:
    def __init__(self, persist_directory: str = "./faiss_db"):
        """Initialize the RAG Agent System with FAISS using modern LCEL approach"""
        self.persist_directory = persist_directory
        
        # Initialize embeddings
        self.embeddings = OllamaEmbeddings(model="mxbai-embed-large")
        
        # Initialize LLM
        self.llm = ChatOllama(model="llama3.2:3b", temperature=0.7)
        
        # In-memory storage (cached from MongoDB)
        self.agents: Dict[str, dict] = {}
        self.vectorstores: Dict[str, FAISS] = {}
        
        # Embed token to agent mapping
        self.embed_tokens: Dict[str, str] = {}  # token -> agent_key
        
        # Rate limiting for embed queries
        self.rate_limits: Dict[str, list] = defaultdict(list)  # token -> [timestamps]
        self.RATE_LIMIT_WINDOW = 60  # seconds
        self.RATE_LIMIT_MAX = 20  # max requests per window
        
        # Conversation memory (session_id -> list of {role, content})
        self.conversations: Dict[str, List[dict]] = defaultdict(list)
        self.CONVERSATION_MAX_HISTORY = 10  # Keep last N turns
        
        # MongoDB collection
        self.collection = get_agents_collection()
        self.token_usage_collection = get_token_usage_collection()
        
        # System prompts for token counting
        self.SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant specialized in {domain}. 
            Answer the question based on the provided context.
            If you cannot find the answer in the context, say so.
            
            Context: {context}
            
            Question: {question}
            
            Answer:"""
        
        self.EMBED_PROMPT_TEMPLATE = """You are a helpful AI assistant. Answer the question based on the provided context.
            Keep your answer concise and helpful.
            
            Context: {context}
            Question: {question}
            Answer:"""
        
        os.makedirs(self.persist_directory, exist_ok=True)
        self.load_agents_from_db()
        
    def load_agents_from_db(self):
        """Load existing agents from MongoDB"""
        if self.collection is None:
            # Fallback to JSON file if MongoDB not available
            self._load_from_json_fallback()
            return
            
        try:
            # Load all agents from MongoDB
            cursor = self.collection.find({})
            for doc in cursor:
                agent_key = doc['_id']
                # Remove MongoDB _id from the dict and store
                agent_data = {k: v for k, v in doc.items() if k != '_id'}
                self.agents[agent_key] = agent_data
                
                # Rebuild embed token mapping
                if agent_data.get('embed_token'):
                    self.embed_tokens[agent_data['embed_token']] = agent_key
                    
            print(f"[OK] Loaded {len(self.agents)} agents from MongoDB")
        except Exception as e:
            print(f"[ERROR] Error loading from MongoDB: {e}")
            self._load_from_json_fallback()
    
    def _load_from_json_fallback(self):
        """Fallback to JSON file storage"""
        metadata_file = os.path.join(self.persist_directory, "agents_metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                self.agents = json.load(f)
            # Rebuild embed token mapping
            for key, agent in self.agents.items():
                if agent.get('embed_token'):
                    self.embed_tokens[agent['embed_token']] = key
            print(f"[OK] Loaded {len(self.agents)} agents from JSON fallback")
    
    def save_agent_to_db(self, agent_key: str, agent_data: dict):
        """Save a single agent to MongoDB"""
        if self.collection is None:
            self._save_to_json_fallback()
            return
            
        try:
            # Upsert agent document
            doc = {'_id': agent_key, **agent_data}
            self.collection.replace_one({'_id': agent_key}, doc, upsert=True)
        except Exception as e:
            print(f"[ERROR] Error saving to MongoDB: {e}")
            self._save_to_json_fallback()
    
    def delete_agent_from_db(self, agent_key: str):
        """Delete agent from MongoDB"""
        if self.collection is None:
            self._save_to_json_fallback()
            return
            
        try:
            self.collection.delete_one({'_id': agent_key})
        except Exception as e:
            print(f"[ERROR] Error deleting from MongoDB: {e}")
            self._save_to_json_fallback()
            
    def delete_agent(self, agent_name: str, user_id: str) -> bool:
        """Delete an agent completely (DB + Files)"""
        import shutil
        
        # 1. Get agent key
        agent_key = self.get_agent_key(agent_name, user_id)
        
        # 2. Delete from DB
        self.delete_agent_from_db(agent_key)
        
        # 3. Delete from File System
        agent_path = self.get_agent_path(agent_name, user_id)
        if os.path.exists(agent_path):
            try:
                shutil.rmtree(agent_path)
                print(f"[INFO] Deleted agent directory: {agent_path}")
            except Exception as e:
                print(f"[ERROR] Failed to delete agent directory: {e}")
                return False
        
        # 4. Remove from memory
        if agent_key in self.agents:
            del self.agents[agent_key]
        if agent_key in self.vectorstores:
            del self.vectorstores[agent_key]
            
        return True
    
    def _save_to_json_fallback(self):
        """Fallback to JSON file storage"""
        metadata_file = os.path.join(self.persist_directory, "agents_metadata.json")
        with open(metadata_file, 'w') as f:
            json.dump(self.agents, f, indent=2)
    
    def _store_token_usage(self, user_id: str, agent_name: str, query: str, token_usage: dict):
        """Store token usage in MongoDB"""
        if self.token_usage_collection is None:
            print("[WARN] Token usage collection not available, skipping storage")
            return
        
        try:
            usage_doc = {
                "user_id": user_id,
                "agent_name": agent_name,
                "query": query[:500],  # Truncate long queries
                "timestamp": datetime.now(),
                "token_usage": token_usage
            }
            self.token_usage_collection.insert_one(usage_doc)
        except Exception as e:
            print(f"[ERROR] Error storing token usage: {e}")
    
    def get_user_token_usage(self, user_id: str = None) -> list:
        """Get aggregated token usage, optionally filtered by user_id"""
        if self.token_usage_collection is None:
            return []
        
        try:
            pipeline = [
                {"$group": {
                    "_id": "$user_id",
                    "total_queries": {"$sum": 1},
                    "total_prompt_tokens": {"$sum": "$token_usage.prompt_tokens"},
                    "total_completion_tokens": {"$sum": "$token_usage.completion_tokens"},
                    "total_tokens": {"$sum": "$token_usage.total_tokens"},
                    "last_query": {"$max": "$timestamp"}
                }},
                {"$sort": {"total_tokens": -1}}
            ]
            
            if user_id:
                pipeline.insert(0, {"$match": {"user_id": user_id}})
            
            return list(self.token_usage_collection.aggregate(pipeline))
        except Exception as e:
            print(f"[ERROR] Error getting token usage: {e}")
            return []
    
    def get_detailed_token_usage(self, user_id: str, limit: int = 50) -> list:
        """Get detailed query-level token usage for a user"""
        if self.token_usage_collection is None:
            return []
        
        try:
            cursor = self.token_usage_collection.find(
                {"user_id": user_id}
            ).sort("timestamp", -1).limit(limit)
            
            return [{
                "agent_name": doc.get("agent_name"),
                "query": doc.get("query"),
                "timestamp": doc.get("timestamp").isoformat() if doc.get("timestamp") else None,
                "token_usage": doc.get("token_usage", {})
            } for doc in cursor]
        except Exception as e:
            print(f"[ERROR] Error getting detailed token usage: {e}")
            return []
    
    def get_agent_counts_by_user(self) -> dict:
        """Get count of agents per user for admin dashboard"""
        user_counts = {}
        for key, agent in self.agents.items():
            user_id = agent.get("user_id")
            if user_id:
                if user_id not in user_counts:
                    user_counts[user_id] = 0
                user_counts[user_id] += 1
        return user_counts
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text
        except Exception as e:
            print(f"Error extracting text from {pdf_path}: {e}")
            return ""
    
    def get_agent_key(self, agent_name: str, user_id: str) -> str:
        """Generate unique key for agent based on name and user_id"""
        safe_name = agent_name.lower().replace(' ', '_').replace('/', '_')
        return f"{user_id}_{safe_name}"
    
    def get_agent_path(self, agent_name: str, user_id: str) -> str:
        """Get the storage path for an agent's FAISS index"""
        agent_key = self.get_agent_key(agent_name, user_id)
        return os.path.join(self.persist_directory, agent_key)
    
    def get_agent_info(self, agent_name: str, user_id: str) -> Optional[dict]:
        """Get information about a specific agent"""
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return None
        
        agent = self.agents[agent_key]
        
        # Check ownership
        if agent.get("user_id") != user_id:
            return None
        
        return {
            "id": agent.get("agent_id"),
            "name": agent.get("agent_name"),
            "domain": agent.get("domain", ""),
            "description": agent.get("description", ""),
            "source_type": agent.get("source_type", "pdf"),
            "source_files": agent.get("source_files", agent.get("pdf_files", [])),
            "num_documents": agent.get("num_documents", 0),
            "embed_token": agent.get("embed_token"),
            "embed_enabled": agent.get("embed_enabled", False),
            "created_at": agent.get("created_at"),
            "updated_at": agent.get("updated_at")
        }
    
    def get_agent_by_id(self, agent_id: str, user_id: str = None) -> Optional[dict]:
        """Get agent by its unique ID"""
        for agent_key, agent in self.agents.items():
            if agent.get("agent_id") == agent_id:
                # If user_id provided, check ownership
                if user_id and agent.get("user_id") != user_id:
                    return None
                return {
                    "key": agent_key,
                    "id": agent.get("agent_id"),
                    "name": agent.get("agent_name"),
                    "user_id": agent.get("user_id"),
                    "domain": agent.get("domain", ""),
                    "description": agent.get("description", ""),
                    "source_type": agent.get("source_type", "pdf"),
                    "source_files": agent.get("source_files", agent.get("pdf_files", [])),
                    "num_documents": agent.get("num_documents", 0),
                    "embed_token": agent.get("embed_token"),
                    "embed_enabled": agent.get("embed_enabled", False),
                    "system_prompt": agent.get("system_prompt"),
                    "welcome_message": agent.get("welcome_message"),
                    "created_at": agent.get("created_at"),
                    "updated_at": agent.get("updated_at")
                }
        return None
    
    def get_agent_key_by_id(self, agent_id: str) -> Optional[str]:
        """Get agent key by agent ID"""
        for agent_key, agent in self.agents.items():
            if agent.get("agent_id") == agent_id:
                return agent_key
        return None
    
    def generate_embed_token(self, agent_name: str, user_id: str) -> dict:
        """Generate an embed token for an agent"""
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return {"success": False, "error": "Agent not found"}
        
        # Check ownership
        if self.agents[agent_key].get("user_id") != user_id:
            return {"success": False, "error": "Access denied"}
        
        # Generate new token if not exists or is None
        existing_token = self.agents[agent_key].get('embed_token')
        if not existing_token:
            token = str(uuid.uuid4()).replace('-', '')[:24]
            self.agents[agent_key]['embed_token'] = token
            self.agents[agent_key]['embed_enabled'] = True
            self.embed_tokens[token] = agent_key
            self.save_agent_to_db(agent_key, self.agents[agent_key])
            print(f"Generated new embed token for {agent_name}: {token}")
        else:
            print(f"Using existing embed token for {agent_name}: {existing_token}")
        
        return {
            "success": True,
            "embed_token": self.agents[agent_key]['embed_token'],
            "agent_name": agent_name
        }
    
    def get_agent_by_embed_token(self, token: str) -> Optional[dict]:
        """Find agent by embed token"""
        if token not in self.embed_tokens:
            return None
        
        agent_key = self.embed_tokens[token]
        if agent_key not in self.agents:
            return None
            
        agent = self.agents[agent_key]
        if not agent.get('embed_enabled', False):
            return None
            
        return agent
    
    def check_rate_limit(self, token: str) -> bool:
        """Check if embed token is within rate limits"""
        current_time = time.time()
        # Clean old entries
        self.rate_limits[token] = [
            t for t in self.rate_limits[token] 
            if current_time - t < self.RATE_LIMIT_WINDOW
        ]
        
        if len(self.rate_limits[token]) >= self.RATE_LIMIT_MAX:
            return False
        
        self.rate_limits[token].append(current_time)
        return True
    
    def query_by_embed_token(self, token: str, query: str) -> dict:
        """Query an agent using embed token (for widget)"""
        # Check rate limit
        if not self.check_rate_limit(token):
            return {"success": False, "error": "Rate limit exceeded. Please try again later."}
        
        agent = self.get_agent_by_embed_token(token)
        if agent is None:
            return {"success": False, "error": "Invalid or disabled embed token"}
        
        agent_key = self.embed_tokens[token]
        agent_name = agent.get('agent_name')
        user_id = agent.get('user_id')
        
        # Load vectorstore if needed
        if agent_key not in self.vectorstores:
            agent_path = self.get_agent_path(agent_name, user_id)
            try:
                self.vectorstores[agent_key] = FAISS.load_local(
                    agent_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                return {"success": False, "error": f"Error loading agent: {str(e)}"}
        
        # Query
        try:
            vectorstore = self.vectorstores[agent_key]
            retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
            
            prompt = ChatPromptTemplate.from_template(self.EMBED_PROMPT_TEMPLATE)
            
            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)
            
            # Get source documents for token counting
            source_docs = retriever.invoke(query)
            
            chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            answer = chain.invoke(query)
            
            # Calculate token usage
            token_usage = calculate_token_usage(
                system_prompt=self.EMBED_PROMPT_TEMPLATE,
                query=query,
                rag_documents=source_docs,
                response=answer,
                domain="general"
            )
            
            # Store token usage (charge to the agent owner)
            self._store_token_usage(user_id, agent_name, query, token_usage)
            
            return {
                "success": True,
                "answer": answer,
                "agent_name": agent_name,
                "token_usage": token_usage
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error: {str(e)}"}
    
    def create_agent(self, agent_name: str, pdf_paths: List[str], 
                    user_id: str, description: str = "", domain: str = "") -> dict:
        """Create a new RAG agent with its own FAISS vector store"""
        
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' already exists for this user"}
        
        try:
            # Extract text from all PDFs
            all_text = ""
            pdf_names = []
            
            for pdf_path in pdf_paths:
                if not os.path.exists(pdf_path):
                    return {"success": False, "error": f"PDF file not found: {pdf_path}"}
                
                text = self.extract_text_from_pdf(pdf_path)
                if text:
                    all_text += text + "\n\n"
                    pdf_names.append(os.path.basename(pdf_path))
            
            if not all_text.strip():
                return {"success": False, "error": "No text could be extracted from PDFs"}
            
            # Split text into chunks (smaller chunks to fit embedding model context)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=50,
                length_function=len
            )
            chunks = text_splitter.split_text(all_text)
            
            if not chunks:
                return {"success": False, "error": "No text chunks created"}
            
            # Create FAISS vector store
            vectorstore = FAISS.from_texts(
                texts=chunks,
                embedding=self.embeddings
            )
            
            # Save FAISS index to disk
            agent_path = self.get_agent_path(agent_name, user_id)
            vectorstore.save_local(agent_path)
            
            # Store references
            self.vectorstores[agent_key] = vectorstore
            
            # Generate unique agent ID
            agent_id = str(uuid.uuid4())
            
            agent_data = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "user_id": user_id,
                "domain": domain,
                "description": description,
                "source_type": "pdf",
                "pdf_files": pdf_names,
                "source_files": pdf_names,
                "num_documents": len(chunks),
                "system_prompt": None,
                "welcome_message": None,
                "embed_token": None,
                "embed_enabled": False,
                "is_demo": False,
                "demo_expires_at": None,
                "demo_credits_used": 0,
                "demo_credit_limit": None,
                "created_at": datetime.now().isoformat()
            }
            
            self.agents[agent_key] = agent_data
            self.save_agent_to_db(agent_key, agent_data)
            
            return {
                "success": True,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "domain": domain,
                "documents_processed": len(pdf_names),
                "chunks_created": len(chunks)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_agent_from_source(self, agent_name: str, source_type: str, source_config: Dict[str, Any],
                                  user_id: str, description: str = "", domain: str = "") -> dict:
        """
        Create a new RAG agent from various data sources.
        
        Args:
            agent_name: Name of the agent
            source_type: Type of source ('pdf', 'csv', 'word', 'sql', 'nosql')
            source_config: Configuration for the source
                - For files (pdf/csv/word): {'file_paths': [...]}
                - For SQL: {'connection_string': '...', 'tables': [...], 'sample_limit': 1000}
                - For NoSQL: {'connection_string': '...', 'database': '...', 'collections': [...], 'sample_limit': 1000}
            user_id: User ID who owns the agent
            description: Agent description
            domain: Agent domain/specialty
        """
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' already exists for this user"}
        
        try:
            documents = []
            source_names = []
            
            # Extract documents based on source type
            if source_type == 'pdf':
                # Use existing PDF logic
                return self.create_agent(
                    agent_name=agent_name,
                    pdf_paths=source_config.get('file_paths', []),
                    user_id=user_id,
                    description=description,
                    domain=domain
                )
                
            elif source_type == 'csv':
                file_paths = source_config.get('file_paths', [])
                source = CSVSource(file_paths)
                documents = source.extract_documents()
                source_names = [os.path.basename(f) for f in file_paths]
                
            elif source_type == 'word':
                file_paths = source_config.get('file_paths', [])
                source = WordSource(file_paths)
                documents = source.extract_documents()
                source_names = [os.path.basename(f) for f in file_paths]
                
            elif source_type == 'sql':
                connection_string = source_config.get('connection_string', '')
                tables = source_config.get('tables', None)
                sample_limit = source_config.get('sample_limit', 1000)
                
                if not connection_string:
                    return {"success": False, "error": "SQL connection string is required"}
                
                source = SQLSource(connection_string, tables=tables, sample_limit=sample_limit)
                documents = source.extract_documents()
                source_names = [f"SQL: {len(tables) if tables else 'all'} tables"]
                
            elif source_type == 'nosql':
                connection_string = source_config.get('connection_string', '')
                database = source_config.get('database', '')
                collections = source_config.get('collections', None)
                sample_limit = source_config.get('sample_limit', 1000)
                
                if not connection_string or not database:
                    return {"success": False, "error": "MongoDB connection string and database name are required"}
                
                source = NoSQLSource(connection_string, database, collections=collections, sample_limit=sample_limit)
                documents = source.extract_documents()
                source_names = [f"MongoDB: {database}"]
                
            elif source_type == 'txt':
                file_paths = source_config.get('file_paths', [])
                source = TXTSource(file_paths)
                documents = source.extract_documents()
                source_names = [os.path.basename(f) for f in file_paths]
                
            else:
                return {"success": False, "error": f"Unsupported source type: {source_type}"}
            
            if not documents:
                return {"success": False, "error": "No documents could be extracted from the source"}
            
            # Extract text from documents and split into chunks
            all_text = "\n\n".join([doc.page_content for doc in documents])
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=50,
                length_function=len
            )
            chunks = text_splitter.split_text(all_text)
            
            if not chunks:
                return {"success": False, "error": "No text chunks created from source"}
            
            # Create FAISS vector store
            vectorstore = FAISS.from_texts(
                texts=chunks,
                embedding=self.embeddings
            )
            
            # Save FAISS index to disk
            agent_path = self.get_agent_path(agent_name, user_id)
            vectorstore.save_local(agent_path)
            
            # Store references
            self.vectorstores[agent_key] = vectorstore
            
            # Generate unique agent ID
            agent_id = str(uuid.uuid4())
            
            agent_data = {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "user_id": user_id,
                "domain": domain,
                "description": description,
                "source_type": source_type,
                "source_files": source_names,
                "pdf_files": source_names if source_type == 'pdf' else [],  # Backward compatibility
                "num_documents": len(chunks),
                "system_prompt": None,  # Custom prompt, uses default if None
                "welcome_message": None,  # Custom welcome message
                "embed_token": None,
                "embed_enabled": False,
                "is_demo": False,
                "demo_expires_at": None,
                "demo_credits_used": 0,
                "demo_credit_limit": None,
                "created_at": datetime.now().isoformat()
            }
            
            self.agents[agent_key] = agent_data
            self.save_agent_to_db(agent_key, agent_data)
            
            return {
                "success": True,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "source_type": source_type,
                "domain": domain,
                "documents_extracted": len(documents),
                "chunks_created": len(chunks)
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to create agent from source: {e}")
            return {"success": False, "error": str(e)}
    
    def update_agent_data(self, agent_name: str, user_id: str, 
                          source_type: str, source_config: Dict[str, Any]) -> dict:
        """
        Add more data to an existing agent (append-only strategy).
        
        Args:
            agent_name: Name of the existing agent
            user_id: User ID who owns the agent
            source_type: Type of new source ('pdf', 'csv', 'word', 'sql', 'nosql')
            source_config: Configuration for the source
        """
        agent_key = self.get_agent_key(agent_name, user_id)
        
        # Check if agent exists
        if agent_key not in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        # Check ownership
        if self.agents[agent_key].get("user_id") != user_id:
            return {"success": False, "error": "Access denied"}
        
        try:
            # Load existing vectorstore if not in memory
            if agent_key not in self.vectorstores:
                agent_path = self.get_agent_path(agent_name, user_id)
                try:
                    self.vectorstores[agent_key] = FAISS.load_local(
                        agent_path, 
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                except Exception as e:
                    return {"success": False, "error": f"Failed to load existing agent: {str(e)}"}
            
            existing_vectorstore = self.vectorstores[agent_key]
            original_chunk_count = self.agents[agent_key].get("num_documents", 0)
            
            # Extract documents from new source
            documents = []
            source_names = []
            
            if source_type == 'pdf':
                file_paths = source_config.get('file_paths', [])
                for pdf_path in file_paths:
                    if os.path.exists(pdf_path):
                        text = self.extract_text_from_pdf(pdf_path)
                        if text:
                            from langchain_core.documents import Document
                            documents.append(Document(page_content=text, metadata={"source": os.path.basename(pdf_path)}))
                            source_names.append(os.path.basename(pdf_path))
                            
            elif source_type == 'csv':
                file_paths = source_config.get('file_paths', [])
                source = CSVSource(file_paths)
                documents = source.extract_documents()
                source_names = [os.path.basename(f) for f in file_paths]
                
            elif source_type == 'word':
                file_paths = source_config.get('file_paths', [])
                source = WordSource(file_paths)
                documents = source.extract_documents()
                source_names = [os.path.basename(f) for f in file_paths]
                
            elif source_type == 'sql':
                connection_string = source_config.get('connection_string', '')
                tables = source_config.get('tables', None)
                sample_limit = source_config.get('sample_limit', 1000)
                
                if not connection_string:
                    return {"success": False, "error": "SQL connection string is required"}
                
                source = SQLSource(connection_string, tables=tables, sample_limit=sample_limit)
                documents = source.extract_documents()
                source_names = [f"SQL: {len(tables) if tables else 'all'} tables"]
                
            elif source_type == 'nosql':
                connection_string = source_config.get('connection_string', '')
                database = source_config.get('database', '')
                collections = source_config.get('collections', None)
                sample_limit = source_config.get('sample_limit', 1000)
                
                if not connection_string or not database:
                    return {"success": False, "error": "MongoDB connection string and database are required"}
                
                source = NoSQLSource(connection_string, database, collections=collections, sample_limit=sample_limit)
                documents = source.extract_documents()
                source_names = [f"MongoDB: {database}"]
                
            else:
                return {"success": False, "error": f"Unsupported source type: {source_type}"}
            
            if not documents:
                return {"success": False, "error": "No documents could be extracted from the source"}
            
            # Split into chunks
            all_text = "\n\n".join([doc.page_content for doc in documents])
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=50,
                length_function=len
            )
            chunks = text_splitter.split_text(all_text)
            
            if not chunks:
                return {"success": False, "error": "No text chunks created from new source"}
            
            # Create new vectorstore from new chunks
            new_vectorstore = FAISS.from_texts(
                texts=chunks,
                embedding=self.embeddings
            )
            
            # Merge new vectorstore into existing one
            existing_vectorstore.merge_from(new_vectorstore)
            
            # Save updated FAISS index
            agent_path = self.get_agent_path(agent_name, user_id)
            existing_vectorstore.save_local(agent_path)
            
            # Update metadata
            existing_sources = self.agents[agent_key].get("source_files", [])
            if isinstance(existing_sources, list):
                updated_sources = existing_sources + source_names
            else:
                updated_sources = source_names
            
            new_total_chunks = original_chunk_count + len(chunks)
            
            self.agents[agent_key]["source_files"] = updated_sources
            self.agents[agent_key]["num_documents"] = new_total_chunks
            self.agents[agent_key]["updated_at"] = datetime.now().isoformat()
            
            # Save to MongoDB
            self.save_agent_to_db(agent_key, self.agents[agent_key])
            
            return {
                "success": True,
                "agent_name": agent_name,
                "source_type": source_type,
                "new_chunks_added": len(chunks),
                "total_chunks": new_total_chunks,
                "sources_added": source_names
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to update agent data: {e}")
            return {"success": False, "error": str(e)}
    
    def query_agent(self, agent_name: str, query: str, user_id: str, k: int = 4) -> dict:
        """Query an agent with a question"""
        
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        # Check ownership
        if self.agents[agent_key].get("user_id") != user_id:
            return {"success": False, "error": "Access denied"}
        
        agent_info = self.agents[agent_key]
        domain = agent_info.get("domain", "general knowledge")
        
        # Load vectorstore if not already loaded
        if agent_key not in self.vectorstores:
            agent_path = self.get_agent_path(agent_name, user_id)
            try:
                self.vectorstores[agent_key] = FAISS.load_local(
                    agent_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                return {"success": False, "error": f"Error loading agent: {str(e)}"}
        
        try:
            vectorstore = self.vectorstores[agent_key]
            retriever = vectorstore.as_retriever(search_kwargs={"k": k})
            
            # Create prompt
            prompt = ChatPromptTemplate.from_template(self.SYSTEM_PROMPT_TEMPLATE)
            
            # Format docs helper
            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)
            
            # Get source documents
            source_docs = retriever.invoke(query)
            
            # Build LCEL chain
            chain = (
                {
                    "context": retriever | format_docs,
                    "question": RunnablePassthrough(),
                    "domain": lambda x: domain
                }
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            answer = chain.invoke(query)
            
            # Calculate token usage
            token_usage = calculate_token_usage(
                system_prompt=self.SYSTEM_PROMPT_TEMPLATE,
                query=query,
                rag_documents=source_docs,
                response=answer,
                domain=domain
            )
            
            # Store token usage in MongoDB
            self._store_token_usage(user_id, agent_name, query, token_usage)
            
            return {
                "success": True,
                "answer": answer,
                "source_documents": [doc.page_content for doc in source_docs],
                "agent_name": agent_name,
                "token_usage": token_usage
            }
            
        except Exception as e:
            return {"success": False, "error": f"Error: {str(e)}"}
    
    def query_agent_stream(self, agent_name: str, query: str, user_id: str, k: int = 4):
        """Stream query response in real-time using generator"""
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            yield {"type": "error", "content": f"Agent '{agent_name}' not found"}
            return
        
        agent = self.agents[agent_key]
        if agent.get("user_id") != user_id:
            yield {"type": "error", "content": "Access denied"}
            return
        
        try:
            # Load vectorstore if not in memory
            if agent_key not in self.vectorstores:
                agent_path = self.get_agent_path(agent_name, user_id)
                if os.path.exists(agent_path):
                    self.vectorstores[agent_key] = FAISS.load_local(
                        agent_path,
                        self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                else:
                    print(f"[ERROR] Agent path not found: {agent_path}")
                    yield {"type": "error", "content": "Agent data not found"}
                    return
            
            vectorstore = self.vectorstores[agent_key]
            retriever = vectorstore.as_retriever(search_kwargs={"k": k})
            
            # Get custom prompt or default
            custom_prompt = agent.get("system_prompt")
            if custom_prompt:
                prompt_template = custom_prompt
            else:
                domain = agent.get("domain", "general knowledge")
                prompt_template = self.SYSTEM_PROMPT_TEMPLATE.replace("{domain}", domain)
            
            # Get context
            source_docs = retriever.invoke(query)
            context = "\n\n".join(doc.page_content for doc in source_docs)
            
            # Build full prompt
            full_prompt = prompt_template.replace("{context}", context).replace("{question}", query)
            
            # Stream response
            full_response = ""
            for chunk in self.llm.stream(full_prompt):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_response += content
                yield {"type": "chunk", "content": content}
            
            # Calculate and store token usage after streaming completes
            token_usage = calculate_token_usage(
                system_prompt=prompt_template,
                query=query,
                rag_documents=source_docs,
                response=full_response,
                domain=agent.get("domain", "general")
            )
            self._store_token_usage(user_id, agent_name, query, token_usage)
            
            # Include full answer and sources in done event
            yield {
                "type": "done", 
                "answer": full_response,
                "sources": [{"pageContent": doc.page_content, "metadata": doc.metadata} for doc in source_docs],
                "token_usage": token_usage
            }
            
        except Exception as e:
            yield {"type": "error", "content": str(e)}
    
    # ==================== CONVERSATION MEMORY ====================
    
    def get_conversation_history(self, session_id: str) -> List[dict]:
        """Get conversation history for a session"""
        return self.conversations.get(session_id, [])
    
    def add_to_conversation(self, session_id: str, role: str, content: str):
        """Add a message to conversation history"""
        self.conversations[session_id].append({"role": role, "content": content})
        # Trim to max history
        if len(self.conversations[session_id]) > self.CONVERSATION_MAX_HISTORY * 2:
            self.conversations[session_id] = self.conversations[session_id][-self.CONVERSATION_MAX_HISTORY * 2:]
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history for a session"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            return True
        return False
    
    def format_conversation_context(self, session_id: str) -> str:
        """Format conversation history as context for the prompt"""
        history = self.get_conversation_history(session_id)
        if not history:
            return ""
        
        formatted = "Previous conversation:\n"
        for msg in history[-6:]:  # Last 3 exchanges
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted += f"{role}: {msg['content'][:200]}...\n" if len(msg['content']) > 200 else f"{role}: {msg['content']}\n"
        return formatted + "\n"
    
    def query_with_memory(self, agent_name: str, query: str, user_id: str, session_id: str, k: int = 4) -> dict:
        """Query agent with conversation memory"""
        # Get conversation context
        context_prefix = self.format_conversation_context(session_id)
        
        # Add current query to history
        self.add_to_conversation(session_id, "user", query)
        
        # Query with context-enhanced prompt
        enhanced_query = context_prefix + query if context_prefix else query
        
        result = self.query_agent(agent_name, enhanced_query, user_id, k)
        
        # Add response to history
        if result.get("success"):
            self.add_to_conversation(session_id, "assistant", result["answer"])
            result["session_id"] = session_id
        
        return result
    
    def list_agents(self, user_id: str = None) -> List[dict]:
        """List all agents, optionally filtered by user_id"""
        agents_list = []
        for key, agent in self.agents.items():
            # Filter by user_id if provided
            if user_id and agent.get("user_id") != user_id:
                continue
            
            # Filter out expired or used-up demo bots
            if agent.get("is_demo"):
                # Check if expired
                demo_expires_at = agent.get("demo_expires_at")
                if demo_expires_at:
                    try:
                        expiry_time = datetime.fromisoformat(demo_expires_at)
                        if datetime.now() > expiry_time:
                            continue  # Skip expired demo
                    except:
                        pass
                
                # Check if credit limit reached
                demo_credits_used = agent.get("demo_credits_used", 0)
                demo_credit_limit = agent.get("demo_credit_limit", 10)
                if demo_credits_used >= demo_credit_limit:
                    continue  # Skip exhausted demo
                
            agents_list.append({
                "id": agent.get("agent_id", key),  # Use agent_id UUID if available, fallback to key
                "key": key,  # Internal key for backward compatibility
                "name": agent["agent_name"],
                "domain": agent.get("domain", "general"),
                "description": agent.get("description", ""),
                "source_type": agent.get("source_type", "pdf"),
                "source_files": agent.get("source_files", agent.get("pdf_files", [])),
                "pdf_files": agent.get("pdf_files", []),
                "num_documents": agent.get("num_documents", 0),
                "embed_token": agent.get("embed_token"),
                "embed_enabled": agent.get("embed_enabled", False),
                "user_id": agent.get("user_id"),
                "created_at": agent.get("created_at"),
                "is_demo": agent.get("is_demo", False),
                "demo_expires_at": agent.get("demo_expires_at"),
                "demo_credits_used": agent.get("demo_credits_used", 0),
                "demo_credit_limit": agent.get("demo_credit_limit")
            })
        return agents_list
    
    def get_agent_info(self, agent_name: str, user_id: str) -> Optional[dict]:
        """Get information about a specific agent"""
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return None
        
        agent = self.agents[agent_key]
        
        # Check ownership
        if agent.get("user_id") != user_id:
            return None
            
        return {
            "id": agent_key,
            "name": agent["agent_name"],
            "domain": agent.get("domain", "general"),
            "description": agent.get("description", ""),
            "pdf_files": agent.get("pdf_files", []),
            "num_documents": agent.get("num_documents", 0),
            "embed_token": agent.get("embed_token"),
            "embed_enabled": agent.get("embed_enabled", False),
            "user_id": agent.get("user_id"),
            "created_at": agent.get("created_at")
        }
    
    def delete_agent(self, agent_name: str, user_id: str) -> dict:
        """Delete an agent and its data"""
        
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        # Check ownership
        if self.agents[agent_key].get("user_id") != user_id:
            return {"success": False, "error": "Access denied"}
        
        try:
            # Remove embed token mapping
            if self.agents[agent_key].get('embed_token'):
                token = self.agents[agent_key]['embed_token']
                if token in self.embed_tokens:
                    del self.embed_tokens[token]
            
            # Delete FAISS index from disk
            agent_path = self.get_agent_path(agent_name, user_id)
            if os.path.exists(agent_path):
                import shutil
                shutil.rmtree(agent_path)
            
            # Remove from memory
            if agent_key in self.vectorstores:
                del self.vectorstores[agent_key]
            del self.agents[agent_key]
            
            # Delete from MongoDB
            self.delete_agent_from_db(agent_key)
            
            return {"success": True, "message": f"Agent '{agent_name}' deleted"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_agent_settings(self, agent_name: str, user_id: str, settings: dict) -> dict:
        """Update agent settings like system_prompt, welcome_message, description"""
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        if self.agents[agent_key].get("user_id") != user_id:
            return {"success": False, "error": "Access denied"}
        
        try:
            # Allowed settings to update
            allowed_fields = ['system_prompt', 'welcome_message', 'description', 'domain']
            
            for field in allowed_fields:
                if field in settings:
                    self.agents[agent_key][field] = settings[field]
            
            self.agents[agent_key]["updated_at"] = datetime.now().isoformat()
            self.save_agent_to_db(agent_key, self.agents[agent_key])
            
            return {
                "success": True,
                "message": f"Agent '{agent_name}' settings updated",
                "updated_fields": [f for f in allowed_fields if f in settings]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def export_agent(self, agent_name: str, user_id: str) -> dict:
        """Export agent configuration as JSON (without vector store)"""
        agent_key = self.get_agent_key(agent_name, user_id)
        
        if agent_key not in self.agents:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        if self.agents[agent_key].get("user_id") != user_id:
            return {"success": False, "error": "Access denied"}
        
        agent = self.agents[agent_key]
        
        # Export config (exclude sensitive/internal data)
        export_data = {
            "agent_name": agent.get("agent_name"),
            "domain": agent.get("domain", ""),
            "description": agent.get("description", ""),
            "source_type": agent.get("source_type", "pdf"),
            "source_files": agent.get("source_files", []),
            "system_prompt": agent.get("system_prompt"),
            "welcome_message": agent.get("welcome_message"),
            "num_documents": agent.get("num_documents", 0),
            "created_at": agent.get("created_at"),
            "export_version": "1.0"
        }
        
        return {
            "success": True,
            "export": export_data
        }
    
    # ==================== BACKEND-ONLY WIDGET SUPPORT ====================
    
    def get_embed_rate_limit_info(self, token: str) -> dict:
        """Get rate limit information for an embed token"""
        current_time = time.time()
        
        # Clean old entries
        self.rate_limits[token] = [
            t for t in self.rate_limits[token] 
            if current_time - t < self.RATE_LIMIT_WINDOW
        ]
        
        requests_used = len(self.rate_limits[token])
        requests_remaining = max(0, self.RATE_LIMIT_MAX - requests_used)
        
        # Calculate reset time
        if self.rate_limits[token]:
            oldest_request = min(self.rate_limits[token])
            reset_at = oldest_request + self.RATE_LIMIT_WINDOW
        else:
            reset_at = current_time + self.RATE_LIMIT_WINDOW
        
        return {
            "limit": self.RATE_LIMIT_MAX,
            "remaining": requests_remaining,
            "used": requests_used,
            "window_seconds": self.RATE_LIMIT_WINDOW,
            "reset_at": datetime.fromtimestamp(reset_at).isoformat()
        }
    
    def store_embed_feedback(self, token: str, message_id: str, 
                             feedback_type: str, comment: str = "") -> dict:
        """Store feedback for embed widget messages"""
        try:
            # Get feedback collection (create if needed)
            from db import get_db
            db = get_db()
            if db is None:
                return {"success": False, "error": "Database not available"}
            
            feedback_collection = db['embed_feedback']
            
            # Get agent info for the token
            agent = self.get_agent_by_embed_token(token)
            agent_name = agent.get("agent_name") if agent else "unknown"
            user_id = agent.get("user_id") if agent else "unknown"
            
            feedback_doc = {
                "token": token,
                "agent_name": agent_name,
                "owner_user_id": user_id,
                "message_id": message_id,
                "feedback_type": feedback_type,  # 'positive' or 'negative'
                "comment": comment,
                "timestamp": datetime.now()
            }
            
            result = feedback_collection.insert_one(feedback_doc)
            
            return {
                "success": True,
                "feedback_id": str(result.inserted_id)
            }
            
        except Exception as e:
            print(f"[ERROR] Error storing feedback: {e}")
            return {"success": False, "error": str(e)}
    
    def track_embed_analytics(self, token: str, event_type: str, 
                              event_data: dict = None) -> dict:
        """Track analytics events for embed widgets"""
        try:
            from db import get_db
            db = get_db()
            if db is None:
                return {"success": False, "error": "Database not available"}
            
            analytics_collection = db['embed_analytics']
            
            # Get agent info for the token
            agent = self.get_agent_by_embed_token(token)
            agent_name = agent.get("agent_name") if agent else "unknown"
            user_id = agent.get("user_id") if agent else "unknown"
            
            analytics_doc = {
                "token": token,
                "agent_name": agent_name,
                "owner_user_id": user_id,
                "event_type": event_type,  # 'widget_open', 'widget_close', 'message_sent', etc.
                "event_data": event_data or {},
                "timestamp": datetime.now()
            }
            
            analytics_collection.insert_one(analytics_doc)
            
            return {"success": True}
            
        except Exception as e:
            print(f"[ERROR] Error tracking analytics: {e}")
            return {"success": False, "error": str(e)}
    
    def get_embed_analytics_summary(self, token: str = None, 
                                    user_id: str = None, 
                                    days: int = 30) -> dict:
        """Get analytics summary for embed widgets"""
        try:
            from db import get_db
            db = get_db()
            if db is None:
                return {"success": False, "error": "Database not available"}
            
            analytics_collection = db['embed_analytics']
            
            # Build query
            query = {}
            if token:
                query["token"] = token
            if user_id:
                query["owner_user_id"] = user_id
            
            # Add date filter
            cutoff_date = datetime.now() - timedelta(days=days)
            query["timestamp"] = {"$gte": cutoff_date}
            
            # Aggregate by event type
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1},
                    "last_event": {"$max": "$timestamp"}
                }},
                {"$sort": {"count": -1}}
            ]
            
            results = list(analytics_collection.aggregate(pipeline))
            
            return {
                "success": True,
                "period_days": days,
                "events": [{
                    "event_type": r["_id"],
                    "count": r["count"],
                    "last_event": r["last_event"].isoformat() if r["last_event"] else None
                } for r in results]
            }
            
        except Exception as e:
            print(f"[ERROR] Error getting analytics: {e}")
            return {"success": False, "error": str(e)}

