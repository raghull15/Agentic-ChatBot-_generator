"""
CSV Data Source Connector
Extracts text from CSV files for RAG training.
"""
import csv
import os
from typing import List, Dict, Any
from langchain_core.documents import Document
from .base import BaseDataSource


class CSVSource(BaseDataSource):
    """Extract documents from CSV files"""
    
    def __init__(self, file_paths: List[str]):
        """
        Initialize CSV source with file paths.
        
        Args:
            file_paths: List of paths to CSV files
        """
        self.file_paths = file_paths
        self.documents: List[Document] = []
        
    def get_source_type(self) -> str:
        return "csv"
    
    def extract_documents(self) -> List[Document]:
        """
        Extract documents from CSV files.
        Each row becomes a document with column headers as context.
        """
        all_documents = []
        
        for file_path in self.file_paths:
            if not os.path.exists(file_path):
                print(f"[WARN] CSV file not found: {file_path}")
                continue
                
            try:
                docs = self._process_csv_file(file_path)
                all_documents.extend(docs)
                print(f"[OK] Extracted {len(docs)} documents from {os.path.basename(file_path)}")
            except Exception as e:
                print(f"[ERROR] Failed to process {file_path}: {e}")
                
        self.documents = all_documents
        return all_documents
    
    def _process_csv_file(self, file_path: str) -> List[Document]:
        """Process a single CSV file into documents"""
        documents = []
        filename = os.path.basename(file_path)
        
        # Try different encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding, newline='') as f:
                    # Detect delimiter
                    sample = f.read(4096)
                    f.seek(0)
                    
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    except csv.Error:
                        dialect = csv.excel
                    
                    reader = csv.DictReader(f, dialect=dialect)
                    headers = reader.fieldnames or []
                    
                    # Create documents from rows
                    for row_num, row in enumerate(reader, start=1):
                        # Convert row to readable text format
                        text_parts = []
                        for header in headers:
                            value = row.get(header, '').strip()
                            if value:
                                text_parts.append(f"{header}: {value}")
                        
                        if text_parts:
                            content = "\n".join(text_parts)
                            doc = Document(
                                page_content=content,
                                metadata={
                                    "source": filename,
                                    "source_type": "csv",
                                    "row_number": row_num,
                                    "columns": headers
                                }
                            )
                            documents.append(doc)
                    
                    break  # Successfully parsed
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                if encoding == encodings[-1]:
                    raise e
                continue
        
        return documents
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the CSV source"""
        return {
            "source_type": "csv",
            "file_count": len(self.file_paths),
            "document_count": len(self.documents),
            "files": [os.path.basename(f) for f in self.file_paths]
        }
