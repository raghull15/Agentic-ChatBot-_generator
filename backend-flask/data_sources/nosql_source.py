"""
NoSQL (MongoDB) Data Source Connector
Extracts data from MongoDB collections for RAG training.
"""
import os
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from .base import BaseDataSource

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("[WARN] pymongo not installed. MongoDB support disabled.")


class NoSQLSource(BaseDataSource):
    """Extract documents from MongoDB databases"""
    
    def __init__(self, connection_string: str, database: str, 
                 collections: Optional[List[str]] = None, sample_limit: int = 1000):
        """
        Initialize NoSQL source with MongoDB connection.
        
        Args:
            connection_string: MongoDB connection string (e.g., mongodb://localhost:27017)
            database: Database name to extract from
            collections: Optional list of specific collections. If None, extracts all.
            sample_limit: Maximum documents to extract per collection (default 1000)
        """
        self.connection_string = connection_string
        self.database_name = database
        self.collections = collections
        self.sample_limit = sample_limit
        self.documents: List[Document] = []
        self.client: Optional[MongoClient] = None
        
    def get_source_type(self) -> str:
        return "nosql"
    
    def _connect(self) -> bool:
        """Establish MongoDB connection"""
        if not PYMONGO_AVAILABLE:
            print("[ERROR] pymongo not installed. Run: pip install pymongo")
            return False
            
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            print(f"[OK] Connected to MongoDB: {self.database_name}")
            return True
        except ConnectionFailure as e:
            print(f"[ERROR] Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] MongoDB connection error: {e}")
            return False
    
    def extract_documents(self) -> List[Document]:
        """
        Extract documents from MongoDB collections.
        Each MongoDB document becomes a LangChain document.
        """
        if not self._connect():
            return []
            
        all_documents = []
        
        try:
            db = self.client[self.database_name]
            collection_names = self.collections or db.list_collection_names()
            
            for collection_name in collection_names:
                # Skip system collections
                if collection_name.startswith('system.'):
                    continue
                    
                try:
                    # Extract schema info from sample document
                    schema_doc = self._extract_schema(db, collection_name)
                    if schema_doc:
                        all_documents.append(schema_doc)
                    
                    # Extract documents
                    data_docs = self._extract_collection_data(db, collection_name)
                    all_documents.extend(data_docs)
                    print(f"[OK] Extracted {len(data_docs)} documents from collection '{collection_name}'")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to extract from collection '{collection_name}': {e}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to access database: {e}")
        finally:
            if self.client:
                self.client.close()
                
        self.documents = all_documents
        return all_documents
    
    def _extract_schema(self, db, collection_name: str) -> Optional[Document]:
        """Extract collection schema from sample document"""
        try:
            collection = db[collection_name]
            sample = collection.find_one()
            
            if not sample:
                return None
            
            # Analyze document structure
            schema_parts = [
                f"Collection: {collection_name}",
                f"Estimated document count: {collection.estimated_document_count()}",
                "Fields:"
            ]
            
            def describe_field(key, value, indent=2):
                """Recursively describe field types"""
                type_name = type(value).__name__
                prefix = " " * indent
                
                if isinstance(value, dict):
                    return f"{prefix}- {key}: object"
                elif isinstance(value, list):
                    if value and len(value) > 0:
                        elem_type = type(value[0]).__name__
                        return f"{prefix}- {key}: array of {elem_type}"
                    return f"{prefix}- {key}: array"
                else:
                    return f"{prefix}- {key}: {type_name}"
            
            for key, value in sample.items():
                schema_parts.append(describe_field(key, value))
            
            content = "\n".join(schema_parts)
            return Document(
                page_content=content,
                metadata={
                    "source": f"schema_{collection_name}",
                    "source_type": "nosql",
                    "collection_name": collection_name,
                    "is_schema": True
                }
            )
        except Exception as e:
            print(f"[WARN] Could not extract schema for {collection_name}: {e}")
            return None
    
    def _extract_collection_data(self, db, collection_name: str) -> List[Document]:
        """Extract documents from a MongoDB collection"""
        documents = []
        
        try:
            collection = db[collection_name]
            cursor = collection.find().limit(self.sample_limit)
            
            for doc_num, mongo_doc in enumerate(cursor, start=1):
                # Convert MongoDB document to readable text
                content = self._document_to_text(mongo_doc, collection_name)
                
                if content:
                    doc = Document(
                        page_content=content,
                        metadata={
                            "source": collection_name,
                            "source_type": "nosql",
                            "collection_name": collection_name,
                            "document_number": doc_num,
                            "document_id": str(mongo_doc.get('_id', ''))
                        }
                    )
                    documents.append(doc)
                    
        except Exception as e:
            print(f"[ERROR] Failed to extract data from {collection_name}: {e}")
        
        return documents
    
    def _document_to_text(self, mongo_doc: dict, collection_name: str) -> str:
        """Convert MongoDB document to readable text format"""
        text_parts = [f"[{collection_name}]"]
        
        def format_value(key, value, indent=0):
            """Recursively format document values"""
            prefix = "  " * indent
            
            if key == '_id':
                return f"{prefix}id: {value}"
            elif isinstance(value, dict):
                nested = [f"{prefix}{key}:"]
                for k, v in value.items():
                    nested.append(format_value(k, v, indent + 1))
                return "\n".join(nested)
            elif isinstance(value, list):
                if not value:
                    return f"{prefix}{key}: []"
                if len(value) <= 5:
                    items = [str(v) for v in value]
                    return f"{prefix}{key}: [{', '.join(items)}]"
                else:
                    items = [str(v) for v in value[:5]]
                    return f"{prefix}{key}: [{', '.join(items)}, ... +{len(value)-5} more]"
            else:
                return f"{prefix}{key}: {value}"
        
        for key, value in mongo_doc.items():
            text_parts.append(format_value(key, value))
        
        return "\n".join(text_parts)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the NoSQL source"""
        return {
            "source_type": "nosql",
            "database": self.database_name,
            "collections": self.collections,
            "document_count": len(self.documents),
            "sample_limit": self.sample_limit
        }
