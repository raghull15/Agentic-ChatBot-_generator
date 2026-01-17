"""
Base class for all data source connectors.
Provides a unified interface for extracting text from different data sources.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document


class BaseDataSource(ABC):
    """Abstract base class for data source connectors"""
    
    @abstractmethod
    def extract_documents(self) -> List[Document]:
        """
        Extract text content as LangChain Documents.
        Returns a list of Document objects ready for embedding.
        """
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """Return the type of data source (pdf, csv, word, sql, nosql)"""
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the data source"""
        return {"source_type": self.get_source_type()}
