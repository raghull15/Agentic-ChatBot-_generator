"""Text file (.txt) data source connector"""
import os
from typing import List, Dict, Any
from langchain_core.documents import Document
from .base import BaseDataSource


class TXTSource(BaseDataSource):
    """Extract documents from plain text (.txt) files"""
    
    def __init__(self, file_paths: List[str]):
        """
        Initialize TXT source with file paths.
        
        Args:
            file_paths: List of paths to .txt files
        """
        self.file_paths = file_paths
        self.documents: List[Document] = []
        
    def get_source_type(self) -> str:
        return "txt"
    
    def extract_documents(self) -> List[Document]:
        """
        Extract documents from text files.
        Each file becomes one or more documents based on content.
        """
        documents = []
        
        for file_path in self.file_paths:
            if not os.path.exists(file_path):
                continue
                
            filename = os.path.basename(file_path)
            
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if not content or not content.strip():
                continue
            
            # Split large files into chunks by paragraphs
            paragraphs = content.split('\n\n')
            
            for i, para in enumerate(paragraphs):
                para = para.strip()
                if not para or len(para) < 10:
                    continue
                    
                doc = Document(
                    page_content=para,
                    metadata={
                        "source": filename,
                        "source_type": "txt",
                        "paragraph_index": i
                    }
                )
                documents.append(doc)
        
        self.documents = documents
        return documents
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the TXT source"""
        return {
            "source_type": "txt",
            "file_count": len(self.file_paths),
            "document_count": len(self.documents),
            "files": [os.path.basename(f) for f in self.file_paths]
        }
