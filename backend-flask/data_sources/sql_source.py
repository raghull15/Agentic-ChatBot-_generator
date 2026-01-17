"""
SQL Database Data Source Connector
Extracts data from SQL databases (MySQL, PostgreSQL, SQLite) for RAG training.
"""
import os
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from .base import BaseDataSource

try:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import Engine
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    print("[WARN] sqlalchemy not installed. SQL database support disabled.")


class SQLSource(BaseDataSource):
    """Extract documents from SQL databases"""
    
    def __init__(self, connection_string: str, tables: Optional[List[str]] = None, 
                 sample_limit: int = 1000):
        """
        Initialize SQL source with connection string.
        
        Args:
            connection_string: SQLAlchemy connection string
                - SQLite: sqlite:///path/to/db.sqlite
                - PostgreSQL: postgresql://user:pass@host:5432/dbname
                - MySQL: mysql+pymysql://user:pass@host:3306/dbname
            tables: Optional list of specific tables to extract. If None, extracts all.
            sample_limit: Maximum rows to extract per table (default 1000)
        """
        self.connection_string = connection_string
        self.tables = tables
        self.sample_limit = sample_limit
        self.documents: List[Document] = []
        self.engine: Optional[Engine] = None
        
    def get_source_type(self) -> str:
        return "sql"
    
    def _normalize_connection_string(self, conn_str: str) -> str:
        """Normalize connection string to use correct SQLAlchemy dialect"""
        # Fix MySQL connection strings - must use pymysql driver
        if conn_str.startswith('mysql://'):
            conn_str = conn_str.replace('mysql://', 'mysql+pymysql://', 1)
            print(f"[INFO] Auto-corrected connection string to use pymysql driver")
        return conn_str
    
    def _connect(self) -> bool:
        """Establish database connection"""
        if not SQLALCHEMY_AVAILABLE:
            print("[ERROR] sqlalchemy not installed. Run: pip install sqlalchemy")
            return False
        
        # Normalize the connection string
        normalized_conn = self._normalize_connection_string(self.connection_string)
            
        try:
            self.engine = create_engine(normalized_conn)
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"[OK] Connected to SQL database")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect to database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_documents(self) -> List[Document]:
        """
        Extract documents from SQL database.
        Each table row becomes a document with column names as context.
        Also includes table schema information.
        """
        if not self._connect():
            return []
            
        all_documents = []
        
        try:
            inspector = inspect(self.engine)
            table_names = self.tables or inspector.get_table_names()
            
            for table_name in table_names:
                try:
                    # Extract schema info
                    schema_doc = self._extract_schema(inspector, table_name)
                    if schema_doc:
                        all_documents.append(schema_doc)
                    
                    # Extract data
                    data_docs = self._extract_table_data(table_name)
                    all_documents.extend(data_docs)
                    print(f"[OK] Extracted {len(data_docs)} documents from table '{table_name}'")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to extract from table '{table_name}': {e}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to inspect database: {e}")
        finally:
            if self.engine:
                self.engine.dispose()
                
        self.documents = all_documents
        return all_documents
    
    def _extract_schema(self, inspector, table_name: str) -> Optional[Document]:
        """Extract table schema as a document"""
        try:
            columns = inspector.get_columns(table_name)
            pk = inspector.get_pk_constraint(table_name)
            
            schema_parts = [f"Table: {table_name}", "Columns:"]
            for col in columns:
                col_info = f"  - {col['name']}: {col['type']}"
                if col.get('nullable') is False:
                    col_info += " (NOT NULL)"
                if col.get('default'):
                    col_info += f" (default: {col['default']})"
                schema_parts.append(col_info)
            
            if pk and pk.get('constrained_columns'):
                schema_parts.append(f"Primary Key: {', '.join(pk['constrained_columns'])}")
            
            content = "\n".join(schema_parts)
            return Document(
                page_content=content,
                metadata={
                    "source": f"schema_{table_name}",
                    "source_type": "sql",
                    "table_name": table_name,
                    "is_schema": True
                }
            )
        except Exception as e:
            print(f"[WARN] Could not extract schema for {table_name}: {e}")
            return None
    
    def _extract_table_data(self, table_name: str) -> List[Document]:
        """Extract data rows from a table"""
        documents = []
        
        try:
            with self.engine.connect() as conn:
                # Get column names
                result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 1"))
                columns = list(result.keys())
                
                # Fetch rows with limit
                result = conn.execute(
                    text(f"SELECT * FROM {table_name} LIMIT {self.sample_limit}")
                )
                
                for row_num, row in enumerate(result, start=1):
                    # Convert row to readable text format
                    text_parts = []
                    for col_name, value in zip(columns, row):
                        if value is not None:
                            text_parts.append(f"{col_name}: {value}")
                    
                    if text_parts:
                        content = f"[{table_name}]\n" + "\n".join(text_parts)
                        doc = Document(
                            page_content=content,
                            metadata={
                                "source": table_name,
                                "source_type": "sql",
                                "table_name": table_name,
                                "row_number": row_num
                            }
                        )
                        documents.append(doc)
                        
        except Exception as e:
            print(f"[ERROR] Failed to extract data from {table_name}: {e}")
        
        return documents
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the SQL source"""
        return {
            "source_type": "sql",
            "connection": self.connection_string.split('@')[-1] if '@' in self.connection_string else "local",
            "tables": self.tables,
            "document_count": len(self.documents),
            "sample_limit": self.sample_limit
        }
