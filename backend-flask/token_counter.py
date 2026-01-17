"""
Token Counting Utility for RAG Agent System
Uses tiktoken for accurate token counting compatible with OpenAI models
For Ollama/Llama models, we use cl100k_base encoding as approximation
"""
import tiktoken

# Use cl100k_base encoding (GPT-4/ChatGPT default) as approximation for Llama tokenization
# This gives reasonably accurate estimates for most purposes
ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a text string"""
    if not text:
        return 0
    try:
        return len(ENCODING.encode(text))
    except Exception:
        # Fallback: rough estimate based on words
        return len(text.split()) * 1.3


def count_system_prompt_tokens(prompt_template: str, domain: str = "general knowledge") -> int:
    """Count tokens in the system prompt template"""
    # Fill in the template with domain
    filled_prompt = prompt_template.replace("{domain}", domain)
    # Remove placeholders that will be filled later
    filled_prompt = filled_prompt.replace("{context}", "").replace("{question}", "")
    return count_tokens(filled_prompt)


def count_rag_context_tokens(documents: list) -> int:
    """Count tokens in retrieved RAG context documents"""
    if not documents:
        return 0
    
    # Handle both string list and Document objects
    total = 0
    for doc in documents:
        if hasattr(doc, 'page_content'):
            total += count_tokens(doc.page_content)
        elif isinstance(doc, str):
            total += count_tokens(doc)
    return total


def count_query_tokens(query: str) -> int:
    """Count tokens in user query"""
    return count_tokens(query)


def count_completion_tokens(response: str) -> int:
    """Count tokens in model response"""
    return count_tokens(response)


def calculate_token_usage(
    system_prompt: str,
    query: str,
    rag_documents: list,
    response: str,
    domain: str = "general knowledge"
) -> dict:
    """
    Calculate comprehensive token usage breakdown
    
    Returns:
        dict with detailed token counts
    """
    system_prompt_tokens = count_system_prompt_tokens(system_prompt, domain)
    user_query_tokens = count_query_tokens(query)
    rag_context_tokens = count_rag_context_tokens(rag_documents)
    completion_tokens = count_completion_tokens(response)
    
    prompt_tokens = system_prompt_tokens + user_query_tokens + rag_context_tokens
    total_tokens = prompt_tokens + completion_tokens
    
    return {
        "system_prompt_tokens": system_prompt_tokens,
        "user_query_tokens": user_query_tokens,
        "rag_context_tokens": rag_context_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens
    }
