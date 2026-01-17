"""
Agent Guardrails - Execution limits and abuse prevention
Controls: max steps, max tokens, timeout, credit exhaustion
"""
import logging
import time
import signal
from decimal import Decimal
from typing import Callable, Any, Optional
from dataclasses import dataclass
from functools import wraps

from billing.token_service import tokens_to_credits, estimate_credits_needed

logger = logging.getLogger(__name__)


# Agent execution limits
AGENT_LIMITS = {
    'max_agent_steps': 5,
    'max_llm_calls': 5,
    'max_tokens_per_run': 4000,
    'timeout_seconds': 30,
}


@dataclass
class ExecutionResult:
    """Result of a controlled agent execution"""
    success: bool
    result: Any = None
    error: str = None
    tokens_used: int = 0
    credits_used: Decimal = Decimal('0')
    execution_time: float = 0
    aborted: bool = False
    abort_reason: str = None


class ExecutionAborted(Exception):
    """Raised when execution is aborted due to limits"""
    pass


class AgentController:
    """
    Controls agent execution with guardrails.
    Tracks token usage and can abort if limits exceeded.
    """
    
    def __init__(
        self,
        max_tokens: int = None,
        max_steps: int = None,
        timeout_seconds: int = None,
        credits_available: Decimal = None
    ):
        self.max_tokens = max_tokens or AGENT_LIMITS['max_tokens_per_run']
        self.max_steps = max_steps or AGENT_LIMITS['max_agent_steps']
        self.timeout_seconds = timeout_seconds or AGENT_LIMITS['timeout_seconds']
        self.credits_available = credits_available
        
        # Tracking
        self.tokens_used = 0
        self.steps_taken = 0
        self.llm_calls = 0
        self.start_time = None
        self.aborted = False
        self.abort_reason = None
    
    def start(self):
        """Start execution tracking"""
        self.start_time = time.time()
        self.tokens_used = 0
        self.steps_taken = 0
        self.llm_calls = 0
        self.aborted = False
        self.abort_reason = None
    
    def check_limits(self, additional_tokens: int = 0) -> None:
        """
        Check if any limits are exceeded. Raises ExecutionAborted if so.
        
        Args:
            additional_tokens: Tokens to be added (for pre-check)
        """
        if self.aborted:
            raise ExecutionAborted(self.abort_reason)
        
        # Check timeout
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > self.timeout_seconds:
                self.abort(f"Timeout: execution exceeded {self.timeout_seconds}s")
        
        # Check token limit
        projected_tokens = self.tokens_used + additional_tokens
        if projected_tokens > self.max_tokens:
            self.abort(f"Token limit: {projected_tokens} > {self.max_tokens}")
        
        # Check credit availability
        if self.credits_available is not None:
            credits_needed = tokens_to_credits(projected_tokens)
            if credits_needed > self.credits_available:
                self.abort(f"Insufficient credits: need {credits_needed}, have {self.credits_available}")
        
        # Check step limit
        if self.steps_taken > self.max_steps:
            self.abort(f"Step limit: {self.steps_taken} > {self.max_steps}")
        
        # Check LLM call limit
        if self.llm_calls > AGENT_LIMITS['max_llm_calls']:
            self.abort(f"LLM call limit: {self.llm_calls} > {AGENT_LIMITS['max_llm_calls']}")
    
    def record_tokens(self, tokens: int):
        """Record token usage"""
        self.tokens_used += tokens
        self.check_limits()
    
    def record_step(self):
        """Record an agent step"""
        self.steps_taken += 1
        self.check_limits()
    
    def record_llm_call(self, tokens: int = 0):
        """Record an LLM call with its token usage"""
        self.llm_calls += 1
        if tokens > 0:
            self.tokens_used += tokens
        self.check_limits()
    
    def abort(self, reason: str):
        """Abort execution with reason"""
        self.aborted = True
        self.abort_reason = reason
        logger.warning(f"Agent execution aborted: {reason}")
        raise ExecutionAborted(reason)
    
    def get_result(self, result: Any = None, error: str = None) -> ExecutionResult:
        """Get execution result with stats"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return ExecutionResult(
            success=not self.aborted and error is None,
            result=result,
            error=error or self.abort_reason,
            tokens_used=self.tokens_used,
            credits_used=tokens_to_credits(self.tokens_used),
            execution_time=elapsed,
            aborted=self.aborted,
            abort_reason=self.abort_reason
        )


def pre_check_credits(
    mongo_user_id: str,
    query_length: int,
    k: int = 4
) -> tuple:
    """
    Pre-flight check before executing a query.
    
    Args:
        mongo_user_id: User ID
        query_length: Length of user query
        k: Number of RAG documents
        
    Returns:
        Tuple of (can_proceed, estimated_credits, message)
    """
    from billing.service_factory import get_db_context, get_wallet_service
    WalletService = get_wallet_service()
    
    estimated_credits = estimate_credits_needed(query_length, k)
    
    try:
        with get_db_context() as db:
            has_credits, message = WalletService.has_sufficient_credits(
                db, 
                mongo_user_id, 
                estimated_credits
            )
            
            if not has_credits:
                return False, estimated_credits, message
            
            return True, estimated_credits, "OK"
            
    except Exception as e:
        logger.error(f"Credit pre-check failed: {e}")
        # Block execution if billing check fails - prevent free usage
        return False, Decimal('0'), f"Billing system error: {str(e)}"


def require_credits(estimated_tokens: int = 1000):
    """
    Decorator that checks for sufficient credits before execution.
    
    Args:
        estimated_tokens: Estimated tokens for the operation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user_id from kwargs or first arg
            user_id = kwargs.get('user_id') or kwargs.get('mongo_user_id')
            if user_id is None and len(args) > 0:
                user_id = args[0]
            
            if user_id is None:
                return func(*args, **kwargs)
            
            estimated_credits = tokens_to_credits(estimated_tokens)
            
            try:
                from billing.service_factory import get_db_context, get_wallet_service
                WalletService = get_wallet_service()
                
                with get_db_context() as db:
                    has_credits, message = WalletService.has_sufficient_credits(
                        db, 
                        user_id, 
                        estimated_credits
                    )
                    
                    if not has_credits:
                        return {
                            'success': False,
                            'error': message,
                            'error_code': 'INSUFFICIENT_CREDITS'
                        }
                
            except Exception as e:
                logger.warning(f"Credit check failed, allowing execution: {e}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
