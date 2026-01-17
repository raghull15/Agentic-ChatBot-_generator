from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from rag_agent_system import RAGAgentSystem
from db import get_users_collection, get_db
from api_helpers import api_success, api_error, ErrorCodes, add_rate_limit_headers
from token_manager import TokenManager
from validators import (
    validate_sql_connection_string,
    validate_mongodb_connection_string,
    validate_database_name,
    validate_table_names,
    validate_sample_limit,
    sanitize_string
)
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()
import json
import jwt
import time
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import wraps
from decimal import Decimal
from bson import ObjectId

# Billing imports - Using MongoDB via service factory
try:
    from billing.service_factory import (
        get_wallet_service, get_usage_service, get_settings_service,
        get_plan_service, get_payment_service, get_analytics_service,
        get_user_management_service, get_db_context, init_billing,
        USE_MONGODB
    )
    from billing.token_service import tokens_to_credits, estimate_credits_needed
    
    # Get service classes
    WalletService = get_wallet_service()
    UsageService = get_usage_service()
    SettingsService = get_settings_service()
    PlanService = get_plan_service()
    PaymentService = get_payment_service()
    AnalyticsService = get_analytics_service()
    UserManagementService = get_user_management_service()
    
    # MongoDB-specific imports
    if USE_MONGODB:
        from billing.mongodb import get_mongo_db, get_db_session
    else:
        from billing.database import get_db_session
        from sqlalchemy import text
    
    BILLING_ENABLED = True
except ImportError as e:
    BILLING_ENABLED = False
    USE_MONGODB = False
    logging.warning(f"Billing module not available: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS configuration - use environment variable or sensible defaults
ALLOWED_ORIGINS = os.environ.get(
    'ALLOWED_ORIGINS', 
    'http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173'
).split(',')
# Allow all origins only if explicitly set for embed widget support
if os.environ.get('ALLOW_ALL_ORIGINS', 'false').lower() == 'true':
    CORS(app, origins=['*'])
else:
    CORS(app, origins=ALLOWED_ORIGINS)

# JWT Secret - MUST be set in environment for production
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    logger.warning("JWT_SECRET not set in environment. Using default (INSECURE - for development only)")
    JWT_SECRET = 'your-super-secret-jwt-key-change-in-production'

# Initialize RAG system
rag_system = RAGAgentSystem()

# Initialize Token Manager
db = get_db()
token_manager = TokenManager(db) if db is not None else None

# Initialize Billing Database (MongoDB or PostgreSQL)
if BILLING_ENABLED:
    try:
        if init_billing():
            logger.info(f"Billing initialized successfully ({'MongoDB' if USE_MONGODB else 'PostgreSQL'})")
        else:
            logger.warning("Billing not initialized - continuing without billing")
            BILLING_ENABLED = False
    except Exception as e:
        logger.warning(f"Billing initialization failed: {e}")
        BILLING_ENABLED = False

# Upload folder for PDFs
UPLOAD_FOLDER = './uploads'
WIDGET_FOLDER = './widget'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WIDGET_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def cleanup_uploaded_files(file_paths: list):
    """Safely clean up uploaded files with logging"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Cleaned up uploaded file: {path}")
        except OSError as e:
            logger.warning(f"Failed to clean up file {path}: {e}")


def emit_credit_update(user_id: str, new_balance: float, change: float, reason: str = 'query', details: dict = None):
    """
    Notify Node.js WebSocket server about credit balance change.
    Node.js will emit to user's WebSocket connection for real-time updates.
    
    Args:
        user_id: MongoDB user ID
        new_balance: New credit balance after change
        change: Change amount (positive for add, negative for deduct)
        reason: Reason for change ('payment', 'query', 'agent_creation', etc.)
        details: Optional dict with additional context (agent name, tokens, etc.)
    """
    try:
        import requests
        response = requests.post(
            'http://localhost:3000/internal/credit-update',
            json={
                'userId': user_id,
                'newBalance': float(new_balance),
                'change': float(change),
                'reason': reason,
                'details': details or {}
            },
            timeout=0.5  # Short timeout - don't block the main operation
        )
        
        if response.status_code == 200:
            logger.debug(f"Credit update emitted for user {user_id}: {new_balance} ({change:+.4f})")
        else:
            logger.warning(f"Failed to emit credit update: HTTP {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.warning("Credit update notification timed out (non-critical)")
    except Exception as e:
        logger.warning(f"Failed to emit credit update: {e} (non-critical)")
        # Don't fail the main operation if WebSocket notification fails


def verify_jwt(f):
    """JWT verification decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "success": False,
                "error": "No token provided. Please login."
            }), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            request.user_id = decoded.get('id')
            if not request.user_id:
                return jsonify({
                    "success": False,
                    "error": "Invalid token payload"
                }), 401
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "Token expired. Please login again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "Invalid token. Please login."
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """Admin verification decorator - checks if user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "success": False,
                "error": "No token provided. Please login."
            }), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user_id = decoded.get('id')
            
            if not user_id:
                return jsonify({
                    "success": False,
                    "error": "Invalid token payload"
                }), 401
            
            # Check if user is admin in MongoDB
            users_collection = get_users_collection()
            user = users_collection.find_one({"_id": ObjectId(user_id)})
            
            if not user or not user.get('isAdmin', False):
                return jsonify({
                    "success": False,
                    "error": "Admin access required"
                }), 403
            
            request.user_id = user_id
            request.user = user
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "Token expired. Please login again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "Invalid token. Please login."
            }), 401
        except Exception as e:
            logger.error(f"Admin auth error: {e}")
            return jsonify({
                "success": False,
                "error": "Authentication failed"
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function



def verify_admin(f):
    """Admin verification decorator - requires JWT + admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "success": False,
                "error": "No token provided. Please login."
            }), 401
        
        token = auth_header.split(' ')[1]
        
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            user_id = decoded.get('id')
            if not user_id:
                return jsonify({
                    "success": False,
                    "error": "Invalid token payload"
                }), 401
            
            # Check if user is admin in MongoDB
            users_collection = get_users_collection()
            if users_collection is None:
                return jsonify({
                    "success": False,
                    "error": "Database not available"
                }), 500
            
            from bson.objectid import ObjectId
            user = users_collection.find_one({"_id": ObjectId(user_id)})
            
            if not user or not user.get('isAdmin', False):
                return jsonify({
                    "success": False,
                    "error": "Admin access required"
                }), 403
            
            request.user_id = user_id
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "Token expired. Please login again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "Invalid token. Please login."
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function


def validate_embed_token(f):
    """
    Embed token validation decorator
    Validates token, checks domain, rate limit, and quota
    """
    @wraps(f)
    def decorated_function(token, *args, **kwargs):
        # Get origin for domain validation
        origin = request.headers.get('Origin') or request.headers.get('Referer', '')
        
        # Use new TokenManager if available, fallback to old system
        if token_manager:
            validation = token_manager.validate_token(token, origin)
            
            if not validation.get("valid"):
                return api_error(
                    validation.get("error_code", ErrorCodes.INVALID_TOKEN),
                    validation.get("error_message", "Invalid token"),
                    404 if validation.get("error_code") == ErrorCodes.INVALID_TOKEN else 
                    429 if "QUOTA" in validation.get("error_code", "") or "RATE" in validation.get("error_code", "") else 403
                )
            
            # Check rate limit (in-memory, per-minute)
            token_data = validation.get("token", {})
            rate_limit = token_data.get("rate_limit", 20)
            
            if not rag_system.check_rate_limit(token):
                rate_info = rag_system.get_embed_rate_limit_info(token)
                return api_error(
                    ErrorCodes.RATE_LIMIT_EXCEEDED,
                    f"Rate limit of {rate_limit} requests per minute exceeded",
                    429,
                    metadata={"rate_limit": rate_info}
                )
            
            # Store token data for use in endpoint
            request.token_data = token_data
            request.agent_key = token_data.get("agent_key")
            
            # Increment usage counter
            token_manager.increment_usage(token)
        else:
            # Fallback to old system (no advanced security)
            agent_info = rag_system.get_agent_by_embed_token(token)
            if not agent_info:
                return api_error(
                    ErrorCodes.INVALID_TOKEN,
                    "Invalid or disabled embed token",
                    404
                )
            
            if not rag_system.check_rate_limit(token):
                return api_error(
                    ErrorCodes.RATE_LIMIT_EXCEEDED,
                    "Rate limit exceeded. Please try again later.",
                    429
                )
            
            request.token_data = None
            request.agent_key = None
        
        return f(token, *args, **kwargs)
    return decorated_function


# ==================== PUBLIC ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "RAG Agent System API is running",
        "total_agents": len(rag_system.agents)
    })


@app.route('/widget.js', methods=['GET'])
def serve_widget():
    """Serve the embeddable widget JavaScript"""
    return send_from_directory(WIDGET_FOLDER, 'widget.js', mimetype='application/javascript')


@app.route('/v1/embed/<token>/query', methods=['POST', 'OPTIONS'])
@app.route('/embed/<token>/query', methods=['POST', 'OPTIONS'])  # Legacy route
def embed_query(token):
    """Public endpoint for embed widget queries (no JWT needed)"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        query = data['query']
        
        # Get agent info to find owner for billing
        agent_info = rag_system.get_agent_by_embed_token(token)
        if not agent_info:
            return jsonify({
                "success": False,
                "error": "Invalid embed token"
            }), 404
        
        owner_user_id = agent_info.get("user_id")
        agent_name = agent_info.get("agent_name")
        
        # Check owner credits before query (billing enforcement)
        if BILLING_ENABLED and owner_user_id:
            try:
                with get_db_session() as db:
                    # Estimate credits needed based on query length
                    estimated_credits = estimate_credits_needed(len(query), 4)
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, owner_user_id, estimated_credits
                    )
                    if not has_credits:
                        return jsonify({
                            "success": False,
                            "error": "Widget owner has insufficient credits",
                            "credits_required": float(estimated_credits)
                        }), 402
            except Exception as e:
                logger.error(f"Billing check failed for embed: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        result = rag_system.query_by_embed_token(token, query)
        
        if result.get("rate_limited"):
            return jsonify(result), 429
        
        # Deduct credits from owner after successful query
        if result["success"] and BILLING_ENABLED and owner_user_id:
            try:
                token_usage = result.get("token_usage", {})
                total_tokens = token_usage.get("total_tokens", 0)
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
                if total_tokens > 0:
                    with get_db_session() as db:
                        # Use admin-configurable conversion rate
                        tokens_per_credit = SettingsService.get_tokens_per_credit(db)
                        credits_used = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
                       
                        success, msg = WalletService.deduct_credits(db, owner_user_id, credits_used)
                        if not success:
                            # Block query result if billing fails - prevent unlimited queries
                            logger.error(f"Credit deduction failed for embed user {owner_user_id}: {msg}")
                            return jsonify({
                                "success": False,
                                "error": "Widget owner has insufficient credits",
                                "billing_error": msg,
                                "credits_attempted": float(credits_used)
                            }), 402
                        else:
                            UsageService.log_usage(
                                db, owner_user_id, agent_name, input_tokens, output_tokens
                            )
                            result["credits_used"] = float(credits_used)
            except Exception as e:
                logger.error(f"Billing deduction failed for embed: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 404
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/v1/embed/<token>/info', methods=['GET'])
@app.route('/embed/<token>/info', methods=['GET'])  # Legacy route
def embed_info(token):
    """Get agent info for embed widget"""
    agent_info = rag_system.get_agent_by_embed_token(token)
    
    if agent_info:
        return jsonify({
            "success": True,
            "agent_name": agent_info["agent_name"],
            "domain": agent_info["domain"],
            "description": agent_info["description"]
        })
    return jsonify({
        "success": False,
        "error": "Invalid embed token"
    }), 404


# ==================== BACKEND-ONLY WIDGET API ====================
# These endpoints allow users to build their own UI with full customization

@app.route('/v1/embed/<token>/config', methods=['GET'])
@app.route('/embed/<token>/config', methods=['GET'])  # Legacy route
def embed_config(token):
    """
    Get widget configuration for custom implementations.
    Returns styling options, rate limits, and feature flags.
    """
    agent_info = rag_system.get_agent_by_embed_token(token)
    
    if not agent_info:
        return jsonify({
            "success": False,
            "error": "Invalid embed token"
        }), 404
    
    # Get rate limit info
    rate_limit_info = rag_system.get_embed_rate_limit_info(token)
    
    return jsonify({
        "success": True,
        "config": {
            "agent": {
                "name": agent_info["agent_name"],
                "domain": agent_info["domain"],
                "description": agent_info["description"],
                "created_at": agent_info.get("created_at")
            },
            "features": {
                "streaming": False,
                "file_upload": False,
                "voice_input": False,
                "feedback": True,
                "conversation_history": True
            },
            "rate_limit": rate_limit_info,
            "ui_hints": {
                "placeholder": f"Ask about {agent_info['domain'] or 'anything'}...",
                "welcome_message": f"Hi! I'm {agent_info['agent_name']}. How can I help you today?",
                "suggested_questions": []
            }
        }
    })


@app.route('/v1/embed/<token>/conversation', methods=['GET'])
@app.route('/embed/<token>/conversation', methods=['GET'])  # Legacy route
def get_conversation(token):
    """Get conversation history hints for a session."""
    agent_info = rag_system.get_agent_by_embed_token(token)
    
    if not agent_info:
        return jsonify({
            "success": False,
            "error": "Invalid embed token"
        }), 404
    
    return jsonify({
        "success": True,
        "message": "Conversation history is managed client-side",
        "storage_hint": "localStorage",
        "key_format": f"agentic_chat_{token}_history"
    })


@app.route('/v1/embed/<token>/conversation', methods=['DELETE'])
@app.route('/embed/<token>/conversation', methods=['DELETE'])  # Legacy route
def clear_conversation(token):
    """Signal to clear conversation."""
    agent_info = rag_system.get_agent_by_embed_token(token)
    
    if not agent_info:
        return jsonify({
            "success": False,
            "error": "Invalid embed token"
        }), 404
    
    return jsonify({
        "success": True,
        "message": "Conversation cleared",
        "action": "Client should clear localStorage"
    })


@app.route('/v1/embed/<token>/feedback', methods=['POST'])
@app.route('/embed/<token>/feedback', methods=['POST'])  # Legacy route
def submit_feedback(token):
    """Submit feedback for a message (thumbs up/down)."""
    agent_info = rag_system.get_agent_by_embed_token(token)
    
    if not agent_info:
        return jsonify({
            "success": False,
            "error": "Invalid embed token"
        }), 404
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Feedback data required"
            }), 400
        
        feedback_type = data.get('type')
        if feedback_type not in ['positive', 'negative']:
            return jsonify({
                "success": False,
                "error": "Feedback type must be 'positive' or 'negative'"
            }), 400
        
        result = rag_system.store_embed_feedback(
            token=token,
            message_id=data.get('message_id'),
            feedback_type=feedback_type,
            comment=data.get('comment', '')
        )
        
        return jsonify({
            "success": True,
            "message": "Feedback recorded",
            "feedback_id": result.get("feedback_id")
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/v1/embed/<token>/analytics', methods=['POST'])
@app.route('/embed/<token>/analytics', methods=['POST'])  # Legacy route
def track_analytics(token):
    """Track widget analytics events."""
    agent_info = rag_system.get_agent_by_embed_token(token)
    
    if not agent_info:
        return jsonify({
            "success": False,
            "error": "Invalid embed token"
        }), 404
    
    try:
        data = request.get_json()
        rag_system.track_embed_analytics(
            token=token,
            event_type=data.get('event'),
            event_data=data.get('data', {})
        )
        
        return jsonify({
            "success": True,
            "message": "Event tracked"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



# ==================== INTERNAL API (for auth-server) ====================

@app.route('/billing/add-credits-internal', methods=['POST'])
def add_free_credits_internal():
    """Internal endpoint for auth-server to add free credits to new users"""
    try:
        # Verify internal secret
        internal_secret = request.headers.get('X-Internal-Secret')
        expected_secret = os.getenv('INTERNAL_API_SECRET', 'shared-secret')
        
        if internal_secret != expected_secret:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        
        data = request.get_json()
        user_id = data.get('user_id')
        email = data.get('email')
        
        if not user_id:
            return jsonify({"success": False, "error": "user_id required"}), 400
        
        if not BILLING_ENABLED:
            return jsonify({"success": True, "message": "Billing disabled, no credits added"}), 200
        
        # Get free_credits amount from admin settings
        free_credits_amount = Decimal('10')  # Default
        try:
            with get_db_session() as db:
                setting_value = SettingsService.get_setting(db, 'free_credits')
                if setting_value:
                    free_credits_amount = Decimal(str(setting_value))
        except Exception as e:
            logger.warning(f"Failed to get free_credits setting: {e}")
        
        # Add credits to user wallet
        try:
            with get_db_session() as db:
                success, new_balance = WalletService.add_credits(db, user_id, free_credits_amount, email)
                if success:
                    logger.info(f"Added {free_credits_amount} free credits to new user {user_id}")
                    return jsonify({
                        "success": True,
                        "credits_added": float(free_credits_amount),
                        "new_balance": float(new_balance)
                    })
                else:
                    return jsonify({"success": False, "error": "Failed to add credits"}), 500
        except Exception as e:
            logger.error(f"Failed to add free credits: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== PROTECTED ENDPOINTS ====================

@app.route('/agents', methods=['GET'])
@verify_jwt
def get_agents():
    """Get all agents for the authenticated user"""
    user_id = request.user_id
    agents = rag_system.list_agents(user_id=user_id)
    return jsonify({
        "success": True,
        "count": len(agents),
        "agents": agents
    })


@app.route('/user/stats', methods=['GET'])
@verify_jwt
def get_user_stats():
    """Get current user's token usage statistics"""
    user_id = request.user_id
    
    # Get token usage for this user
    usage = rag_system.get_user_token_usage(user_id)
    
    if usage:
        stats = usage[0]  # First (and only) result for this user
        return jsonify({
            "success": True,
            "stats": {
                "total_queries": stats.get("total_queries", 0),
                "total_prompt_tokens": stats.get("total_prompt_tokens", 0),
                "total_completion_tokens": stats.get("total_completion_tokens", 0),
                "total_tokens": stats.get("total_tokens", 0),
                "last_query": stats.get("last_query").isoformat() if stats.get("last_query") else None
            }
        })
    else:
        return jsonify({
            "success": True,
            "stats": {
                "total_queries": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "last_query": None
            }
        })


@app.route('/agents/<agent_name>', methods=['GET'])
@verify_jwt
def get_agent(agent_name):
    """Get specific agent information"""
    user_id = request.user_id
    agent_info = rag_system.get_agent_info(agent_name, user_id)
    if agent_info:
        return jsonify({
            "success": True,
            "agent": agent_info
        })
    return jsonify({
        "success": False,
        "error": "Agent not found or access denied"
    }), 404


@app.route('/agents/<agent_name>/embed-token', methods=['POST'])
@verify_jwt
def generate_embed_token(agent_name):
    """Generate or get embed token for an agent"""
    user_id = request.user_id
    result = rag_system.generate_embed_token(agent_name, user_id)
    
    if result["success"]:
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/agents/create', methods=['POST'])
@verify_jwt
def create_agent():
    """Create a new agent for the authenticated user"""
    try:
        user_id = request.user_id
        
        # Check if files are present
        if 'files' not in request.files:
            return jsonify({
                "success": False,
                "error": "No PDF files provided"
            }), 400
        
        files = request.files.getlist('files')
        agent_name = request.form.get('agent_name')
        domain = request.form.get('domain', '')
        description = request.form.get('description', '')
        
        if not agent_name:
            return jsonify({
                "success": False,
                "error": "Agent name is required"
            }), 400
        
        if not files:
            return jsonify({
                "success": False,
                "error": "At least one PDF file is required"
            }), 400
        
        # Save uploaded files
        pdf_paths = []
        for file in files:
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
                file.save(filepath)
                pdf_paths.append(filepath)
        
        if not pdf_paths:
            return jsonify({
                "success": False,
                "error": "No valid PDF files provided"
            }), 400
        
        # Check credits before creating agent (read cost from admin settings)
        bot_creation_cost = Decimal("0")
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    # Get bot creation cost from admin settings
                    bot_creation_cost = Decimal(str(SettingsService.get_setting(db, 'bot_creation_cost') or 50))
                    
                    # Check if user has enough credits
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, bot_creation_cost
                    )
                    if not has_credits:
                        cleanup_uploaded_files(pdf_paths)
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(bot_creation_cost)
                        }), 402
            except Exception as e:
                logger.warning(f"Billing check failed for agent creation: {e}")
        
        # Create agent with user_id
        result = rag_system.create_agent(
            agent_name=agent_name,
            pdf_paths=pdf_paths,
            user_id=user_id,
            description=description,
            domain=domain
        )
        
        # Clean up uploaded files
        for path in pdf_paths:
            try:
                os.remove(path)
            except:
                pass
        
        if result["success"]:
            # Deduct credits after successful creation
            if BILLING_ENABLED and bot_creation_cost > 0:
                try:
                    with get_db_session() as db:
                        success, msg = WalletService.deduct_credits(db, user_id, bot_creation_cost)
                        if success:
                            db.commit()  # Ensure deduction is persisted
                            logger.info(f"Deducted {bot_creation_cost} credits for bot creation: {agent_name}")
                        else:
                            logger.error(f"Failed to deduct credits for bot creation: {msg}")
                except Exception as e:
                    logger.error(f"Failed to deduct credits for bot creation: {e}")
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/create-demo', methods=['POST'])
@verify_jwt
def create_demo_agent():
    """Create a demo agent for first-time users"""
    try:
        user_id = request.user_id
        
        # Check if user is eligible for demo (never created demo before)
        existing_agents = rag_system.list_agents(user_id=user_id)
        has_demo = any(a.get('is_demo') for a in existing_agents)
        
        if has_demo:
            return jsonify({
                "success": False,
                "error": "You have already created a demo bot. Please create a real bot."
            }), 400
        
        # Get demo settings from admin
        demo_time_limit_hours = 24
        demo_credit_limit = 10
        
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    demo_time_limit_hours = SettingsService.get_setting(db, 'demo_bot_time_limit_hours') or 24
                    demo_credit_limit = SettingsService.get_setting(db, 'demo_bot_credit_limit') or 10
            except Exception as e:
                logger.warning(f"Failed to get demo settings: {e}")
        
        # Check if files are present
        if 'files' not in request.files:
            return jsonify({"success": False, "error": "No PDF files provided"}), 400
        
        files = request.files.getlist('files')
        agent_name = request.form.get('agent_name', 'Demo Bot')
        domain = request.form.get('domain', 'Demo')
        description = request.form.get('description', 'Demo bot with limited usage')
        
        if not files:
            return jsonify({"success": False, "error": "At least one PDF file is required"}), 400
        
        # Save uploaded files
        pdf_paths = []
        for file in files:
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
                file.save(filepath)
                pdf_paths.append(filepath)
        
        if not pdf_paths:
            return jsonify({"success": False, "error": "No valid PDF files provided"}), 400
        
        # Create demo agent (no credit deduction)
        result = rag_system.create_agent(
            agent_name=agent_name, pdf_paths=pdf_paths, user_id=user_id,
            description=description, domain=domain
        )
        
        # Clean up uploaded files
        for path in pdf_paths:
            try:
                os.remove(path)
            except:
                pass
        
        if result["success"]:
            # Mark as demo bot with limits
            agent_key = f"{user_id}_{agent_name}"
            if agent_key in rag_system.agents:
                from datetime import timedelta
                rag_system.agents[agent_key]["is_demo"] = True
                rag_system.agents[agent_key]["demo_expires_at"] = (datetime.now() + timedelta(hours=demo_time_limit_hours)).isoformat()
                rag_system.agents[agent_key]["demo_credit_limit"] = demo_credit_limit
                rag_system.agents[agent_key]["demo_credits_used"] = 0
                rag_system.save_agent_to_db(agent_key, rag_system.agents[agent_key])
            
            result["is_demo"] = True
            result["demo_expires_at"] = rag_system.agents.get(agent_key, {}).get("demo_expires_at")
            result["demo_credit_limit"] = demo_credit_limit
            logger.info(f"Created demo bot for user {user_id}: {agent_name}")
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/agents/create-from-source', methods=['POST'])
@verify_jwt
def create_agent_from_source():
    """Create a new agent from various data sources (CSV, Word, SQL, NoSQL)"""
    try:
        user_id = request.user_id
        
        # Get source type
        source_type = request.form.get('source_type', 'pdf')
        agent_name = request.form.get('agent_name')
        domain = request.form.get('domain', '')
        description = request.form.get('description', '')
        
        if not agent_name:
            return jsonify({
                "success": False,
                "error": "Agent name is required"
            }), 400
        
        source_config = {}
        
        # Handle file-based sources (pdf, csv, word)
        if source_type in ['pdf', 'csv', 'word']:
            if 'files' not in request.files:
                return jsonify({
                    "success": False,
                    "error": f"No files provided for {source_type} source"
                }), 400
            
            files = request.files.getlist('files')
            if not files:
                return jsonify({
                    "success": False,
                    "error": f"At least one file is required"
                }), 400
            
            # Validate file extensions
            valid_extensions = {
                'pdf': ['.pdf'],
                'csv': ['.csv'],
                'word': ['.docx', '.doc']
            }
            
            file_paths = []
            for file in files:
                if file and file.filename:
                    ext = os.path.splitext(file.filename)[1].lower()
                    if ext in valid_extensions.get(source_type, []):
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
                        file.save(filepath)
                        file_paths.append(filepath)
            
            if not file_paths:
                return jsonify({
                    "success": False,
                    "error": f"No valid {source_type.upper()} files provided"
                }), 400
            
            source_config = {'file_paths': file_paths}
            
        # Handle SQL source
        elif source_type == 'sql':
            connection_string = request.form.get('connection_string', '')
            tables_json = request.form.get('tables', '')
            sample_limit_raw = request.form.get('sample_limit', 1000)
            
            if not connection_string:
                return jsonify({
                    "success": False,
                    "error": "SQL connection string is required"
                }), 400
            
            # Validate SQL connection string
            is_valid, error_msg = validate_sql_connection_string(connection_string)
            if not is_valid:
                logger.warning(f"Invalid SQL connection string from user {user_id}: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": f"Invalid connection string: {error_msg}"
                }), 400
            
            # Validate sample limit
            is_valid, error_msg, sample_limit = validate_sample_limit(sample_limit_raw)
            if not is_valid:
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 400
            
            # Parse and validate tables
            tables = None
            if tables_json:
                try:
                    tables = json.loads(tables_json)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid tables JSON from user {user_id}: {e}")
                    return jsonify({
                        "success": False,
                        "error": "Invalid tables format. Expected JSON array."
                    }), 400
            
            # Validate table names
            if tables:
                is_valid, error_msg, tables = validate_table_names(','.join(tables) if isinstance(tables, list) else tables)
                if not is_valid:
                    return jsonify({
                        "success": False,
                        "error": error_msg
                    }), 400
            
            source_config = {
                'connection_string': connection_string,
                'tables': tables,
                'sample_limit': sample_limit
            }
            
        # Handle NoSQL (MongoDB) source
        elif source_type == 'nosql':
            connection_string = request.form.get('connection_string', '')
            database = request.form.get('database', '')
            collections_json = request.form.get('collections', '')
            sample_limit_raw = request.form.get('sample_limit', 1000)
            
            if not connection_string or not database:
                return jsonify({
                    "success": False,
                    "error": "MongoDB connection string and database name are required"
                }), 400
            
            # Validate MongoDB connection string
            is_valid, error_msg = validate_mongodb_connection_string(connection_string)
            if not is_valid:
                logger.warning(f"Invalid MongoDB connection string from user {user_id}: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": f"Invalid connection string: {error_msg}"
                }), 400
            
            # Validate database name
            is_valid, error_msg = validate_database_name(database)
            if not is_valid:
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 400
            
            # Validate sample limit
            is_valid, error_msg, sample_limit = validate_sample_limit(sample_limit_raw)
            if not is_valid:
                return jsonify({
                    "success": False,
                    "error": error_msg
                }), 400
            
            # Parse and validate collections
            collections = None
            if collections_json:
                try:
                    collections = json.loads(collections_json)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid collections JSON from user {user_id}: {e}")
                    return jsonify({
                        "success": False,
                        "error": "Invalid collections format. Expected JSON array."
                    }), 400
            
            # Validate collection names
            if collections:
                is_valid, error_msg, collections = validate_table_names(','.join(collections) if isinstance(collections, list) else collections)
                if not is_valid:
                    return jsonify({
                        "success": False,
                        "error": error_msg
                    }), 400
            
            source_config = {
                'connection_string': connection_string,
                'database': database,
                'collections': collections,
                'sample_limit': sample_limit
            }
            
        else:
            return jsonify({
                "success": False,
                "error": f"Unsupported source type: {source_type}"
            }), 400
        
        # Check credits before creating agent (read cost from admin settings)
        bot_creation_cost = Decimal("0")
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    # Get bot creation cost from admin settings
                    bot_creation_cost = Decimal(str(SettingsService.get_setting_value(db, 'bot_creation_cost', 50)))
                    
                    # Check if user has enough credits
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, bot_creation_cost
                    )
                    if not has_credits:
                        # Clean up any uploaded files
                        if 'file_paths' in source_config:
                            cleanup_uploaded_files(source_config['file_paths'])
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(bot_creation_cost)
                        }), 402
            except Exception as e:
                logger.warning(f"Billing check failed for agent creation: {e}")
        
        # Create agent
        result = rag_system.create_agent_from_source(
            agent_name=agent_name,
            source_type=source_type,
            source_config=source_config,
            user_id=user_id,
            description=description,
            domain=domain
        )
        
        # Clean up uploaded files if any
        if 'file_paths' in source_config:
            for path in source_config['file_paths']:
                try:
                    os.remove(path)
                except:
                    pass
        
        if result["success"]:
            # Deduct credits after successful creation
            if BILLING_ENABLED and bot_creation_cost > 0:
                try:
                    with get_db_session() as db:
                        success, msg = WalletService.deduct_credits(db, user_id, bot_creation_cost)
                        if success:
                            db.commit()  # Ensure deduction is persisted
                            logger.info(f"Deducted {bot_creation_cost} credits for bot creation: {agent_name}")
                        else:
                            logger.error(f"Failed to deduct credits for bot creation: {msg}")
                except Exception as e:
                    logger.error(f"Failed to deduct credits for bot creation: {e}")
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/<agent_name>/update', methods=['POST'])
@verify_jwt
def update_agent(agent_name):
    """Add more data to an existing agent"""
    try:
        user_id = request.user_id
        
        # Get source type
        source_type = request.form.get('source_type', 'pdf')
        
        source_config = {}
        
        # Handle file-based sources (pdf, csv, word)
        if source_type in ['pdf', 'csv', 'word']:
            if 'files' not in request.files:
                return jsonify({
                    "success": False,
                    "error": f"No files provided for {source_type} source"
                }), 400
            
            files = request.files.getlist('files')
            if not files:
                return jsonify({
                    "success": False,
                    "error": "At least one file is required"
                }), 400
            
            # Validate file extensions
            valid_extensions = {
                'pdf': ['.pdf'],
                'csv': ['.csv'],
                'word': ['.docx', '.doc']
            }
            
            file_paths = []
            for file in files:
                if file and file.filename:
                    ext = os.path.splitext(file.filename)[1].lower()
                    if ext in valid_extensions.get(source_type, []):
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
                        file.save(filepath)
                        file_paths.append(filepath)
            
            if not file_paths:
                return jsonify({
                    "success": False,
                    "error": f"No valid {source_type.upper()} files provided"
                }), 400
            
            source_config = {'file_paths': file_paths}
            
        # Handle SQL source
        elif source_type == 'sql':
            connection_string = request.form.get('connection_string', '')
            tables_json = request.form.get('tables', '')
            sample_limit = int(request.form.get('sample_limit', 1000))
            
            if not connection_string:
                return jsonify({
                    "success": False,
                    "error": "SQL connection string is required"
                }), 400
            
            tables = None
            if tables_json:
                try:
                    tables = json.loads(tables_json)
                except:
                    pass
            
            source_config = {
                'connection_string': connection_string,
                'tables': tables,
                'sample_limit': sample_limit
            }
            
        # Handle NoSQL (MongoDB) source
        elif source_type == 'nosql':
            connection_string = request.form.get('connection_string', '')
            database = request.form.get('database', '')
            collections_json = request.form.get('collections', '')
            sample_limit = int(request.form.get('sample_limit', 1000))
            
            if not connection_string or not database:
                return jsonify({
                    "success": False,
                    "error": "MongoDB connection string and database name are required"
                }), 400
            
            collections = None
            if collections_json:
                try:
                    collections = json.loads(collections_json)
                except:
                    pass
            
            source_config = {
                'connection_string': connection_string,
                'database': database,
                'collections': collections,
                'sample_limit': sample_limit
            }
        # Handle TXT source
        elif source_type == 'txt':
            if 'files' not in request.files:
                return jsonify({
                    "success": False,
                    "error": "No TXT files provided"
                }), 400
            
            files = request.files.getlist('files')
            file_paths = []
            for file in files:
                if file and file.filename.endswith('.txt'):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}_{filename}")
                    file.save(filepath)
                    file_paths.append(filepath)
            
            source_config = {'file_paths': file_paths}
            
        else:
            return jsonify({
                "success": False,
                "error": f"Unsupported source type: {source_type}"
            }), 400
        
        # Update agent with new data
        result = rag_system.update_agent_data(
            agent_name=agent_name,
            user_id=user_id,
            source_type=source_type,
            source_config=source_config
        )
        
        # Clean up uploaded files if any
        if 'file_paths' in source_config:
            for path in source_config['file_paths']:
                try:
                    os.remove(path)
                except:
                    pass
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/<agent_name>/settings', methods=['PUT'])
@verify_jwt
def update_agent_settings(agent_name):
    """Update agent settings (system_prompt, welcome_message, etc.)"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No settings provided"}), 400
        
        result = rag_system.update_agent_settings(agent_name, user_id, data)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/agents/<agent_name>/export', methods=['GET'])
@verify_jwt
def export_agent(agent_name):
    """Export agent configuration as JSON"""
    user_id = request.user_id
    result = rag_system.export_agent(agent_name, user_id)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 404


@app.route('/agents/<agent_name>/analytics', methods=['GET'])
@verify_jwt
def get_agent_analytics(agent_name):
    """Get analytics for a specific agent"""
    user_id = request.user_id
    
    # Get agent queries from token_usage collection
    if rag_system.token_usage_collection is None:
        return jsonify({
            "success": True,
            "analytics": {
                "total_queries": 0,
                "total_tokens": 0,
                "queries_today": 0
            }
        })
    
    try:
        # Aggregate queries for this agent
        pipeline = [
            {"$match": {"user_id": user_id, "agent_name": agent_name}},
            {"$group": {
                "_id": None,
                "total_queries": {"$sum": 1},
                "total_tokens": {"$sum": "$token_usage.total_tokens"},
                "avg_response_tokens": {"$avg": "$token_usage.completion_tokens"}
            }}
        ]
        
        results = list(rag_system.token_usage_collection.aggregate(pipeline))
        
        if results:
            stats = results[0]
            return jsonify({
                "success": True,
                "analytics": {
                    "total_queries": stats.get("total_queries", 0),
                    "total_tokens": stats.get("total_tokens", 0),
                    "avg_response_tokens": round(stats.get("avg_response_tokens", 0), 1)
                }
            })
        else:
            return jsonify({
                "success": True,
                "analytics": {
                    "total_queries": 0,
                    "total_tokens": 0,
                    "avg_response_tokens": 0
                }
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/agents/<agent_name>/query', methods=['POST'])
@verify_jwt
def query_agent(agent_name):
    """Query an agent"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        query = data['query']
        k = data.get('k', 4)
        
        # Check credits before query (billing enforcement)
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    # Estimate credits needed based on query length
                    estimated_credits = estimate_credits_needed(len(query), k)
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, estimated_credits
                    )
                    if not has_credits:
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(estimated_credits)
                        }), 402  # Payment Required
            except Exception as e:
                logger.error(f"Billing check failed: {e}")
                # Block query if billing check fails - prevent free usage
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        result = rag_system.query_agent(
            agent_name=agent_name,
            query=query,
            k=k,
            user_id=user_id  # Pass user_id for usage logging
        )
        
        # Deduct actual credits based on token usage
        if BILLING_ENABLED and result.get("success"):
            try:
                token_usage = result.get("token_usage", {})
                total_tokens = token_usage.get("total_tokens", 0)
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
                
                if total_tokens > 0:
                    with get_db_session() as db:
                        # Check max tokens limit
                        max_tokens = SettingsService.get_max_tokens_per_query(db)
                        if total_tokens > max_tokens:
                            return jsonify({
                                "success": False,
                                "error": f"Query exceeds maximum token limit ({max_tokens} tokens)",
                                "tokens_used": total_tokens,
                                "max_allowed": max_tokens
                            }), 400
                        
                        # Use admin-configurable conversion rate
                        tokens_per_credit = SettingsService.get_tokens_per_credit(db)
                        credits_used = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
                        
                        success, msg = WalletService.deduct_credits(db, user_id, credits_used)
                        if not success:
                            db.rollback()
                            # Block query result if billing fails - prevent unlimited queries
                            logger.error(f"Credit deduction failed for user {user_id}: {msg}")
                            return jsonify({
                                "success": False,
                                "error": "Credit deduction failed: " + msg,
                                "billing_error": True
                            }), 402
                        else:
                            # Log usage
                            UsageService.log_usage(db, user_id, agent_name, input_tokens, output_tokens)
                            
                            # 🆕 Phase 2: Emit real-time credit update
                            wallet_info = WalletService.get_wallet_info(db, user_id)
                            if wallet_info:
                                emit_credit_update(
                                    user_id=user_id,
                                    new_balance=wallet_info['credits_remaining'],
                                    change=-float(credits_used),
                                    reason='query',
                                    details={
                                        'agentName': agent_name,
                                        'inputTokens': input_tokens,
                                        'outputTokens': output_tokens,
                                        'totalTokens': total_tokens
                                    }
                                )
                            
                            # Add credits used to result for frontend display
                            result["credits_used"] = float(credits_used)
            except Exception as e:
                logger.error(f"Billing deduction failed: {e}")
                # Don't fail the query if billing notification fails
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 404
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/<agent_name>/query/stream', methods=['POST'])
@verify_jwt
def query_agent_stream(agent_name):
    """Stream query response in real-time using SSE"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        query = data['query']
        k = data.get('k', 4)
        
        # Check if this is a demo bot - enforce limits
        agent_key = f"{user_id}_{agent_name}"
        agent_data = rag_system.agents.get(agent_key)
        if agent_data and agent_data.get("is_demo"):
            # Check if demo has expired
            demo_expires_at = agent_data.get("demo_expires_at")
            if demo_expires_at:
                from datetime import datetime
                expiry_time = datetime.fromisoformat(demo_expires_at)
                if datetime.now() > expiry_time:
                    return jsonify({
                        "success": False,
                        "error": "Demo bot has expired. Please create a real bot.",
                        "demo_expired": True
                    }), 403
            
            # Check if demo credit limit reached
            demo_credits_used = agent_data.get("demo_credits_used", 0)
            demo_credit_limit = agent_data.get("demo_credit_limit", 10)
            if demo_credits_used >= demo_credit_limit:
                return jsonify({
                    "success": False,
                    "error": f"Demo bot credit limit ({demo_credit_limit}) reached. Please create a real bot.",
                    "demo_limit_reached": True
                }), 403
        
        # Check credits before stream (billing enforcement)
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    # Estimate credits needed based on query length
                    estimated_credits = estimate_credits_needed(len(query), k)
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, estimated_credits
                    )
                    if not has_credits:
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(estimated_credits)
                        }), 402
            except Exception as e:
                logger.error(f"Billing check failed for stream: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        def generate():
            token_usage_data = None
            for chunk_data in rag_system.query_agent_stream(
                agent_name=agent_name,
                user_id=user_id,
                query=query,
                k=k
            ):
                # Capture token usage from the final 'done' chunk
                if chunk_data.get("type") == "done" and chunk_data.get("token_usage"):
                    token_usage_data = chunk_data.get("token_usage")
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # Deduct credits after stream completes
            if token_usage_data and BILLING_ENABLED:
                try:
                    total_tokens = token_usage_data.get("total_tokens", 0)
                    input_tokens = token_usage_data.get("prompt_tokens", 0)
                    output_tokens = token_usage_data.get("completion_tokens", 0)
                    if total_tokens > 0:
                        with get_db_session() as db:
                            # Check max tokens limit
                            max_tokens = SettingsService.get_max_tokens_per_query(db)
                            if total_tokens > max_tokens:
                                yield f"data: {json.dumps({'type': 'error', 'error': f'Query exceeds maximum token limit ({max_tokens} tokens)', 'tokens_used': total_tokens})}\n\n"
                                return
                            
                            # Use admin-configurable conversion rate
                            tokens_per_credit = SettingsService.get_tokens_per_credit(db)
                            credits_used = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
                           
                            success, msg = WalletService.deduct_credits(db, user_id, credits_used)
                            if not success:
                                # Send billing error through stream
                                logger.error(f"Credit deduction failed for streaming user {user_id}: {msg}")
                                yield f"data: {json.dumps({'type': 'billing_error', 'error': msg, 'credits_attempted': float(credits_used)})}\n\n"
                            else:
                                db.commit()
                                UsageService.log_usage(
                                    db, user_id, agent_name, input_tokens, output_tokens
                                )
                                # Track demo bot credit usage
                                agent_key_track = f"{user_id}_{agent_name}"
                                if agent_key_track in rag_system.agents and rag_system.agents[agent_key_track].get("is_demo"):
                                    rag_system.agents[agent_key_track]["demo_credits_used"] = rag_system.agents[agent_key_track].get("demo_credits_used", 0) + float(credits_used)
                                    rag_system.save_agent_to_db(agent_key_track, rag_system.agents[agent_key_track])
                                # Send credits used info
                                yield f"data: {json.dumps({'type': 'billing', 'credits_used': float(credits_used)})}\n\n"
                except Exception as e:
                    logger.error(f"Billing deduction failed for stream: {e}")
                    yield f"data: {json.dumps({'type': 'billing_error', 'error': 'Billing system error'})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ==================== ID-BASED AGENT ROUTES ====================
# These routes use agent_id (UUID) instead of agent_name for unique addressing

@app.route('/agents/id/<agent_id>', methods=['GET'])
@verify_jwt
def get_agent_by_id_route(agent_id):
    """Get agent by its unique ID"""
    user_id = request.user_id
    agent_info = rag_system.get_agent_by_id(agent_id, user_id)
    if agent_info:
        return jsonify({
            "success": True,
            "agent": agent_info
        })
    return jsonify({
        "success": False,
        "error": "Agent not found or access denied"
    }), 404


@app.route('/agents/id/<agent_id>/query', methods=['POST'])
@verify_jwt
def query_agent_by_id(agent_id):
    """Query an agent by its unique ID"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        # Get agent info by ID
        agent_info = rag_system.get_agent_by_id(agent_id, user_id)
        if not agent_info:
            return jsonify({
                "success": False,
                "error": "Agent not found or access denied"
            }), 404
        
        agent_name = agent_info['name']
        query = data['query']
        k = data.get('k', 4)
        
        # Pre-check credits before query (billing enforcement)
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    estimated_credits = estimate_credits_needed(len(query), k)
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, estimated_credits
                    )
                    if not has_credits:
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(estimated_credits)
                        }), 402
            except Exception as e:
                logger.error(f"Billing check failed for ID query: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        # Execute query
        result = rag_system.query_agent(agent_name, query, user_id, k)
        
        # Deduct credits after successful query
        if result.get("success") and BILLING_ENABLED:
            try:
                token_usage = result.get("token_usage", {})
                total_tokens = token_usage.get("total_tokens", 0)
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
                if total_tokens > 0:
                    with get_db_session() as db:
                        # Use admin-configurable conversion rate
                        tokens_per_credit = SettingsService.get_tokens_per_credit(db)
                        credits_used = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
                       
                        success, msg = WalletService.deduct_credits(db, user_id, credits_used)
                        if not success:
                            logger.error(f"Credit deduction failed for user {user_id}: {msg}")
                            return jsonify({
                                "success": False,
                                "error": msg,
                                "credits_attempted": float(credits_used)
                            }), 402
                        else:
                            UsageService.log_usage(db, user_id, agent_name, input_tokens, output_tokens)
                            result["credits_used"] = float(credits_used)
                            logger.info(f"Deducted {credits_used} credits from user {user_id} for ID query")
            except Exception as e:
                logger.error(f"Billing deduction failed for ID query: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/agents/id/<agent_id>', methods=['DELETE'])
@verify_jwt
def delete_agent_by_id(agent_id):
    """Delete an agent by its unique ID"""
    user_id = request.user_id
    
    # Get agent info to verify ownership
    agent_info = rag_system.get_agent_by_id(agent_id, user_id)
    if not agent_info:
        return jsonify({
            "success": False,
            "error": "Agent not found or access denied"
        }), 404
    
    agent_name = agent_info['name']
    
    try:
        success = rag_system.delete_agent(agent_name, user_id)
        if success:
            return jsonify({
                "success": True,
                "message": f"Agent '{agent_name}' deleted successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to delete agent"
            }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/id/<agent_id>/query/stream', methods=['POST'])
@verify_jwt
def query_agent_by_id_stream(agent_id):
    """Stream query responses for an agent by ID"""
    logger.info(f"=== ID STREAM QUERY START === agent_id={agent_id}")
    try:
        user_id = request.user_id
        data = request.get_json()
        logger.info(f"User {user_id} querying agent {agent_id} via ID stream")
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        # Get agent info by ID
        agent_info = rag_system.get_agent_by_id(agent_id, user_id)
        if not agent_info:
            return jsonify({
                "success": False,
                "error": "Agent not found or access denied"
            }), 404
        
        agent_name = agent_info['name']
        query = data['query']
        k = data.get('k', 4)
        
        logger.info(f"BILLING_ENABLED={BILLING_ENABLED}, agent_name={agent_name}")
        
        # Check credits before query (billing enforcement)
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    estimated_credits = estimate_credits_needed(len(query), k)
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, estimated_credits
                    )
                    logger.info(f"Credit pre-check: has_credits={has_credits}, reason={reason}")
                    if not has_credits:
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(estimated_credits)
                        }), 402
            except Exception as e:
                logger.error(f"Billing check failed for ID stream: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        def generate():
            token_usage_data = None
            logger.info(f"Starting stream generation for user {user_id}")
            for chunk_data in rag_system.query_agent_stream(
                agent_name=agent_name,
                user_id=user_id,
                query=query,
                k=k
            ):
                if chunk_data.get("type") == "done" and chunk_data.get("token_usage"):
                    token_usage_data = chunk_data.get("token_usage")
                    logger.info(f"Got token_usage from stream: {token_usage_data}")
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
            logger.info(f"Stream complete. token_usage_data={token_usage_data}, BILLING_ENABLED={BILLING_ENABLED}")
            
            # Deduct credits after stream completes
            if token_usage_data and BILLING_ENABLED:
                try:
                    total_tokens = token_usage_data.get("total_tokens", 0)
                    input_tokens = token_usage_data.get("prompt_tokens", 0)
                    output_tokens = token_usage_data.get("completion_tokens", 0)
                    if total_tokens > 0:
                        with get_db_session() as db:
                            # Check max tokens limit
                            max_tokens = SettingsService.get_max_tokens_per_query(db)
                            if total_tokens > max_tokens:
                                yield f"data: {json.dumps({'type': 'error', 'error': f'Query exceeds maximum token limit ({max_tokens} tokens)', 'tokens_used': total_tokens})}\n\n"
                                return
                            
                            # Use admin-configurable conversion rate
                            tokens_per_credit = SettingsService.get_tokens_per_credit(db)
                            credits_to_deduct = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
                           
                            success, msg = WalletService.deduct_credits(db, user_id, credits_to_deduct)
                            if success:
                                UsageService.log_usage(db, user_id, agent_name, input_tokens, output_tokens)
                                logger.info(f"Deducted {credits_to_deduct} credits from user {user_id} for ID stream")
                                yield f"data: {json.dumps({'type': 'billing', 'credits_used': float(credits_to_deduct)})}\n\n"
                            else:
                                logger.error(f"Credit deduction failed for stream user {user_id}: {msg}")
                                yield f"data: {json.dumps({'type': 'billing_error', 'error': msg})}\n\n"
                except Exception as e:
                    logger.error(f"Failed to deduct credits after ID stream: {e}")
                    yield f"data: {json.dumps({'type': 'billing_error', 'error': 'Billing system error'})}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/<agent_name>/query/memory', methods=['POST'])
@verify_jwt
def query_agent_with_memory(agent_name):
    """Query agent with conversation memory enabled"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        query = data['query']
        session_id = data.get('session_id', f"{user_id}_{agent_name}_default")
        k = data.get('k', 4)
        
        # Pre-check credits before query (billing enforcement)
        if BILLING_ENABLED:
            try:
                with get_db_session() as db:
                    # Estimate credits needed based on query length
                    estimated_credits = estimate_credits_needed(len(query), k)
                    has_credits, reason = WalletService.has_sufficient_credits(
                        db, user_id, estimated_credits
                    )
                    if not has_credits:
                        return jsonify({
                            "success": False,
                            "error": reason,
                            "credits_required": float(estimated_credits)
                        }), 402  # Payment Required
            except Exception as e:
                logger.warning(f"Billing check failed for memory query: {e}")
        
        result = rag_system.query_with_memory(
            agent_name=agent_name,
            user_id=user_id,
            query=query,
            session_id=session_id,
            k=k
        )
        
        # Deduct credits after successful query
        if result["success"] and BILLING_ENABLED:
            try:
                token_usage = result.get("token_usage", {})
                total_tokens = token_usage.get("total_tokens", 0)
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
                if total_tokens > 0:
                    with get_db_session() as db:
                        # Use admin-configurable conversion rate
                        tokens_per_credit = SettingsService.get_tokens_per_credit(db)
                        credits_used = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
                       
                        success, msg = WalletService.deduct_credits(db, user_id, credits_used)
                        if not success:
                            logger.error(f"Credit deduction failed for memory query user {user_id}: {msg}")
                            return jsonify({
                                "success": False,
                                "error": msg,
                                "credits_attempted": float(credits_used)
                            }), 402
                        else:
                            UsageService.log_usage(
                                db, user_id, agent_name, input_tokens, output_tokens
                            )
                            result["credits_used"] = float(credits_used)
            except Exception as e:
                logger.error(f"Billing deduction failed for memory query: {e}")
                return jsonify({
                    "success": False,
                    "error": "Billing system error. Please try again."
                }), 500
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 404
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/agents/<agent_name>/conversation', methods=['DELETE'])
@verify_jwt
def clear_agent_conversation(agent_name):
    """Clear conversation history for an agent session"""
    user_id = request.user_id
    data = request.get_json() or {}
    session_id = data.get('session_id', f"{user_id}_{agent_name}_default")
    
    cleared = rag_system.clear_conversation(session_id)
    
    return jsonify({
        "success": True,
        "cleared": cleared,
        "session_id": session_id
    })


@app.route('/agents/<agent_name>', methods=['DELETE'])
@verify_jwt
def delete_agent(agent_name):
    """Delete an agent"""
    user_id = request.user_id
    success = rag_system.delete_agent(agent_name, user_id)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Failed to delete agent"}), 404

# ==================== ADMIN ENDPOINTS ====================

@app.route('/admin/users', methods=['GET'])
@verify_admin
def admin_list_users():
    """Get all users with their token usage and bot counts (admin only)"""
    try:
        users_collection = get_users_collection()
        if users_collection is None:
            return jsonify({"success": False, "error": "Database not available"}), 500
        
        # Get all users
        users = list(users_collection.find({}, {"password": 0}))
        
        # Get token usage per user
        token_usage = rag_system.get_user_token_usage()
        usage_map = {u["_id"]: u for u in token_usage}
        
        # Get bot counts per user
        bot_counts = rag_system.get_agent_counts_by_user()
        
        result = []
        for user in users:
            user_id = str(user["_id"])
            usage = usage_map.get(user_id, {})
            result.append({
                "id": user_id,
                "name": user.get("name", "Unknown"),
                "email": user.get("email", ""),
                "isAdmin": user.get("isAdmin", False),
                "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
                "bot_count": bot_counts.get(user_id, 0),
                "token_usage": {
                    "total_queries": usage.get("total_queries", 0),
                    "total_prompt_tokens": usage.get("total_prompt_tokens", 0),
                    "total_completion_tokens": usage.get("total_completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "last_query": usage.get("last_query").isoformat() if usage.get("last_query") else None
                }
            })
        
        return jsonify({"success": True, "users": result})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/usage', methods=['GET'])
@verify_admin
def admin_get_usage():
    """Get aggregated token usage statistics (admin only)"""
    try:
        usage = rag_system.get_user_token_usage()
        bot_counts = rag_system.get_agent_counts_by_user()
        
        # Calculate totals
        totals = {
            "total_users": len(usage),
            "total_bots": sum(bot_counts.values()),
            "total_queries": sum(u.get("total_queries", 0) for u in usage),
            "total_prompt_tokens": sum(u.get("total_prompt_tokens", 0) for u in usage),
            "total_completion_tokens": sum(u.get("total_completion_tokens", 0) for u in usage),
            "total_tokens": sum(u.get("total_tokens", 0) for u in usage)
        }
        
        return jsonify({
            "success": True,
            "totals": totals,
            "per_user": [{
                "user_id": u["_id"],
                "total_queries": u.get("total_queries", 0),
                "total_prompt_tokens": u.get("total_prompt_tokens", 0),
                "total_completion_tokens": u.get("total_completion_tokens", 0),
                "total_tokens": u.get("total_tokens", 0),
                "last_query": u.get("last_query").isoformat() if u.get("last_query") else None
            } for u in usage]
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/usage/<user_id>', methods=['GET'])
@verify_admin
def admin_get_user_usage(user_id):
    """Get detailed token usage for a specific user (admin only)"""
    try:
        limit = request.args.get('limit', 50, type=int)
        usage = rag_system.get_detailed_token_usage(user_id, limit)
        
        return jsonify({
            "success": True,
            "user_id": user_id,
            "queries": usage
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/users/<user_id>/credits', methods=['POST'])
@verify_admin
def admin_add_credits(user_id):
    """Add credits to a user's wallet (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        data = request.get_json()
        amount = data.get('amount')
        
        if not amount or float(amount) <= 0:
            return jsonify({
                "success": False,
                "error": "Valid positive amount is required"
            }), 400
        
        credits_to_add = Decimal(str(amount))
        
        # Get user email from MongoDB
        users_collection = get_users_collection()
        user_email = None
        if users_collection is not None:
            from bson.objectid import ObjectId
            mongo_user = users_collection.find_one({"_id": ObjectId(user_id)})
            if mongo_user:
                user_email = mongo_user.get('email')
            else:
                return jsonify({
                    "success": False,
                    "error": "User not found"
                }), 404
        
        with get_db_session() as db:
            success, new_balance = WalletService.add_credits(
                db, user_id, credits_to_add, user_email
            )
            
            if success:
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "credits_added": float(credits_to_add),
                    "new_balance": float(new_balance)
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Failed to add credits"
                }), 500
                
    except Exception as e:
        logger.error(f"Admin add credits error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/users/<user_id>/balance', methods=['GET'])
@verify_admin
def admin_get_user_balance(user_id):
    """Get a user's credit balance (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            wallet_info = WalletService.get_wallet_info(db, user_id)
            
            if wallet_info:
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "wallet": wallet_info
                })
            else:
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "wallet": {
                        "credits_remaining": 0,
                        "total_purchased": 0,
                        "daily_usage": 0
                    }
                })
                
    except Exception as e:
        logger.error(f"Admin get balance error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== ADMIN SETTINGS ENDPOINTS ====================

@app.route('/admin/settings', methods=['GET'])
@verify_admin
def admin_get_settings():
    """Get all billing settings (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            settings = SettingsService.get_all_settings(db)
            return jsonify({"success": True, "settings": settings})
    except Exception as e:
        logger.error(f"Admin get settings error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/settings/<key>', methods=['PUT'])
@verify_admin
def admin_update_setting(key):
    """Update a billing setting (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        data = request.get_json()
        value = data.get('value')
        
        if value is None:
            return jsonify({"success": False, "error": "Value is required"}), 400
        
        admin_email = getattr(request, 'user_email', 'admin')
        
        with get_db_session() as db:
            success = SettingsService.update_setting(db, key, value, admin_email)
            
            if success:
                return jsonify({"success": True, "key": key, "value": value})
            else:
                return jsonify({"success": False, "error": "Failed to update setting"}), 500
    except Exception as e:
        logger.error(f"Admin update setting error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/plans', methods=['GET'])
@verify_admin
def admin_get_plans():
    """Get all subscription plans (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            plans = PlanService.get_all_plans(db, active_only=False)
            return jsonify({"success": True, "plans": plans})
    except Exception as e:
        logger.error(f"Admin get plans error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/plans', methods=['POST'])
@verify_admin
def admin_create_plan():
    """Create a new subscription plan (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        data = request.get_json()
        
        required = ['id', 'name', 'amount_paise', 'credits']
        for field in required:
            if field not in data:
                return jsonify({"success": False, "error": f"{field} is required"}), 400
        
        with get_db_session() as db:
            plan = PlanService.create_plan(db, data)
            return jsonify({"success": True, "plan": plan}), 201
    except Exception as e:
        logger.error(f"Admin create plan error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/plans/<plan_id>', methods=['PUT'])
@verify_admin
def admin_update_plan(plan_id):
    """Update a subscription plan (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        data = request.get_json()
        
        with get_db_session() as db:
            plan = PlanService.update_plan(db, plan_id, data)
            
            if plan:
                return jsonify({"success": True, "plan": plan})
            else:
                return jsonify({"success": False, "error": "Plan not found"}), 404
    except Exception as e:
        logger.error(f"Admin update plan error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/plans/<plan_id>', methods=['DELETE'])
@verify_admin
def admin_delete_plan(plan_id):
    """Delete (deactivate) a subscription plan (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            success = PlanService.delete_plan(db, plan_id, soft_delete=True)
            
            if success:
                return jsonify({"success": True, "plan_id": plan_id, "deactivated": True})
            else:
                return jsonify({"success": False, "error": "Plan not found"}), 404
    except Exception as e:
        logger.error(f"Admin delete plan error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/users/<user_id>/suspend', methods=['POST'])
@verify_admin
def admin_suspend_user(user_id):
    """Suspend a user (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            success = UserManagementService.suspend_user(db, user_id)
            
            if success:
                return jsonify({"success": True, "user_id": user_id, "suspended": True})
            else:
                return jsonify({"success": False, "error": "User not found in billing system"}), 404
    except Exception as e:
        logger.error(f"Admin suspend user error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/users/<user_id>/unsuspend', methods=['POST'])
@verify_admin
def admin_unsuspend_user(user_id):
    """Unsuspend a user (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            success = UserManagementService.unsuspend_user(db, user_id)
            
            if success:
                return jsonify({"success": True, "user_id": user_id, "suspended": False})
            else:
                return jsonify({"success": False, "error": "User not found in billing system"}), 404
    except Exception as e:
        logger.error(f"Admin unsuspend user error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/analytics', methods=['GET'])
@verify_admin
def admin_get_analytics():
    """Get usage and revenue analytics (admin only)"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        days = request.args.get('days', 30, type=int)
        
        with get_db_session() as db:
            analytics = {
                'usage_stats': AnalyticsService.get_usage_stats(db, days),
                'daily_usage': AnalyticsService.get_daily_usage(db, days),
                'top_users': AnalyticsService.get_top_users(db, 10, days),
                'top_agents': AnalyticsService.get_top_agents(db, 10, days),
                'user_summary': AnalyticsService.get_user_summary(db)
            }
            return jsonify({"success": True, "analytics": analytics})
    except Exception as e:
        logger.error(f"Admin analytics error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/billing/balance', methods=['GET'])
@verify_jwt
def get_billing_balance():
    """Get user's credit balance and wallet info"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            wallet_info = WalletService.get_wallet_info(db, request.user_id)
            
            if wallet_info is None:
                # Create wallet for new user
                WalletService.get_or_create_user(db, request.user_id)
                wallet_info = WalletService.get_wallet_info(db, request.user_id)
            
            return jsonify({
                "success": True,
                "wallet": wallet_info
            })
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/billing/plans', methods=['GET'])
def get_billing_plans():
    """Get available pricing plans from database"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    try:
        with get_db_session() as db:
            # Get active plans from database
            plans = PlanService.get_all_plans(db, active_only=True)
            return jsonify({
                "success": True,
                "plans": plans
            })
    except Exception as e:
        logger.error(f"Error fetching plans: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/billing/create-order', methods=['POST'])
@verify_jwt
def create_billing_order():
    """Create a Razorpay order for purchasing credits"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    data = request.get_json()
    plan_id = data.get('plan_id')
    
    if not plan_id:
        return jsonify({"success": False, "error": "plan_id is required"}), 400
    
    try:
        with get_db_session() as db:
            # Get user email from MongoDB for record
            users_collection = get_users_collection()
            user_email = None
            if users_collection:
                from bson.objectid import ObjectId
                mongo_user = users_collection.find_one({"_id": ObjectId(request.user_id)})
                if mongo_user:
                    user_email = mongo_user.get('email')
            
            success, result = PaymentService.create_order(
                db, 
                request.user_id, 
                plan_id,
                user_email
            )
            
            if success:
                return jsonify({"success": True, "order": result})
            else:
                return jsonify({"success": False, "error": result.get('error')}), 400
                
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/billing/verify-payment', methods=['POST'])
@verify_jwt
def verify_billing_payment():
    """Verify Razorpay payment and add credits"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    data = request.get_json()
    order_id = data.get('razorpay_order_id')
    payment_id = data.get('razorpay_payment_id')
    signature = data.get('razorpay_signature')
    
    if not all([order_id, payment_id, signature]):
        return jsonify({
            "success": False, 
            "error": "razorpay_order_id, razorpay_payment_id, and razorpay_signature are required"
        }), 400
    
    try:
        with get_db_session() as db:
            success, result = PaymentService.complete_payment(
                db, order_id, payment_id, signature
            )
            
            if success:
                return jsonify({"success": True, **result})
            else:
                return jsonify({"success": False, "error": result.get('error')}), 400
                
    except Exception as e:
        logger.error(f"Error verifying payment: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/billing/webhook', methods=['POST'])
def billing_webhook():
    """Razorpay webhook endpoint"""
    if not BILLING_ENABLED:
        return jsonify({"status": "billing_disabled"}), 200
    
    # Verify webhook signature
    signature = request.headers.get('X-Razorpay-Signature', '')
    payload = request.get_data()
    
    if not PaymentService.verify_webhook_signature(payload, signature):
        logger.warning("Invalid webhook signature")
        return jsonify({"status": "invalid_signature"}), 400
    
    try:
        data = request.get_json()
        event = data.get('event', '')
        
        with get_db_session() as db:
            success, message = PaymentService.process_webhook(db, event, data)
            
        return jsonify({"status": "processed", "message": message})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Internal API secret for auth-server communication
INTERNAL_API_SECRET = os.environ.get('INTERNAL_API_SECRET', 'internal-secret')

@app.route('/internal/add-credits', methods=['POST'])
def internal_add_credits():
    """
    Internal endpoint for auth-server to add credits after successful payment.
    Uses shared secret for authentication.
    """
    # Verify internal secret
    provided_secret = request.headers.get('X-Internal-Secret', '')
    if provided_secret != INTERNAL_API_SECRET:
        logger.warning(f"Invalid internal API secret - Expected: '{INTERNAL_API_SECRET}', Received: '{provided_secret}'")
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    data = request.get_json()
    user_id = data.get('user_id')
    credits = data.get('credits')
    payment_id = data.get('payment_id')
    order_id = data.get('order_id')
    plan_id = data.get('plan_id', 'unknown')
    amount = data.get('amount', 0)
    
    if not user_id or credits is None:
        return jsonify({"success": False, "error": "user_id and credits required"}), 400
    
    try:
        credits_decimal = Decimal(str(credits))
        
        with get_db_session() as db:
            # Add credits to wallet
            success, new_balance = WalletService.add_credits(db, user_id, credits_decimal)
            
            if success:
                # Save payment record using MongoDB-compatible method
                if USE_MONGODB:
                    # MongoDB mode - use PaymentServiceMongo
                    PaymentService.create_payment_record(
                        db, user_id, order_id or f"internal_{payment_id}",
                        amount, plan_id, credits_decimal
                    )
                    # Mark it as completed
                    db.payments.update_one(
                        {'razorpayOrderId': order_id or f"internal_{payment_id}"},
                        {'$set': {
                            'status': 'completed',
                            'razorpayPaymentId': payment_id,
                            'completedAt': datetime.utcnow()
                        }}
                    )
                else:
                    # PostgreSQL mode - use SQLAlchemy model
                    from billing.models import Payment
                    user = WalletService.get_or_create_user(db, user_id)
                    payment = Payment(
                        user_id=user.id,
                        razorpay_payment_id=payment_id,
                        razorpay_order_id=order_id,
                        amount_inr=amount,
                        credits_added=credits_decimal,
                        plan_id=plan_id,
                        status='completed'
                    )
                    db.add(payment)
                    db.commit()
                
                logger.info(f"Added {credits} credits for user {user_id} via payment {payment_id}")
                return jsonify({
                    "success": True,
                    "credits_added": float(credits_decimal),
                    "new_balance": float(new_balance)
                })
            else:
                return jsonify({"success": False, "error": "Failed to add credits"}), 500
                
    except Exception as e:
        logger.error(f"Internal add credits error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/billing/usage', methods=['GET'])
@verify_jwt
def get_billing_usage():
    """Get user's usage history"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    limit = request.args.get('limit', 50, type=int)
    chatbot_id = request.args.get('chatbot_id')
    
    try:
        with get_db_session() as db:
            usage = UsageService.get_usage_history(
                db, request.user_id, limit=limit, chatbot_id=chatbot_id
            )
            summary = UsageService.get_usage_summary(db, request.user_id)
            
            return jsonify({
                "success": True,
                "usage": usage,
                "summary": summary
            })
    except Exception as e:
        logger.error(f"Error getting usage: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/billing/payments', methods=['GET'])
@verify_jwt
def get_billing_payments():
    """Get user's payment history"""
    if not BILLING_ENABLED:
        return jsonify({"success": False, "error": "Billing not available"}), 503
    
    limit = request.args.get('limit', 20, type=int)
    
    try:
        with get_db_session() as db:
            payments = PaymentService.get_payment_history(db, request.user_id, limit)
            
            return jsonify({
                "success": True,
                "payments": payments
            })
    except Exception as e:
        logger.error(f"Error getting payments: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===================================================================
# ADMIN ENDPOINTS
# ===================================================================

@app.route('/billing/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
    """Get all users with usage statistics (Admin only)"""
    try:
        users_collection = get_users_collection()
        users = list(users_collection.find({}))
        
        enriched_users = []
        with get_db_session() as db:
            for user in users:
                user_id = str(user['_id'])
                
                # Get bot count
                try:
                    user_agents = [a for a in rag_system.agents.values() if a.get('user_id') == user_id]
                    bot_count = len(user_agents)
                except:
                    bot_count = 0
                
                # Get usage stats
                try:
                    total_queries, total_tokens, last_query = UsageService.get_user_total_usage(db, user_id)
                    prompt_tokens, completion_tokens = UsageService.get_user_token_breakdown(db, user_id)
                    
                    token_usage = {
                        'total_queries': total_queries,
                        'total_tokens': total_tokens,
                        'total_prompt_tokens': prompt_tokens,
                        'total_completion_tokens': completion_tokens,
                        'last_query': last_query.isoformat() if last_query else None
                    }
                except:
                    token_usage = {
                        'total_queries': 0,
                        'total_tokens': 0,
                        'total_prompt_tokens': 0,
                        'total_completion_tokens': 0,
                        'last_query': None
                    }
                
                enriched_users.append({
                    'id': user_id,
                    'name': user.get('name'),
                    'email': user.get('email'),
                    'isAdmin': user.get('isAdmin', False),
                    'createdAt': user.get('createdAt'),
                    'bot_count': bot_count,
                    'token_usage': token_usage
                })
        
        return jsonify({'users': enriched_users})
    except Exception as e:
        logger.error(f"Admin get users error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/usage', methods=['GET'])
@require_admin
def billing_admin_get_usage():
    """Get system-wide usage statistics (Admin only)"""
    try:
        users_collection = get_users_collection()
        total_users = users_collection.count_documents({})
        total_bots = len(rag_system.agents)
        
        with get_db_session() as db:
            # Get totals from usage logs
            result = db.execute(text("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_users,
                    COUNT(*) as total_queries,
                    SUM(input_tokens) as total_prompt_tokens,
                    SUM(output_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens
                FROM usage_logs
            """)).fetchone()
            
            totals = {
                'total_users': total_users,
                'total_bots': total_bots,
                'active_users': result[0] if result[0] else 0,
                'total_queries': result[1] if result[1] else 0,
                'total_prompt_tokens': result[2] if result[2] else 0,
                'total_completion_tokens': result[3] if result[3] else 0,
                'total_tokens': result[4] if result[4] else 0
            }
        
        return jsonify({'totals': totals})
    except Exception as e:
        logger.error(f"Admin get usage error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/users/<user_id>/balance', methods=['GET'])
@require_admin
def billing_admin_get_user_balance(user_id):
    """Get user's wallet balance (Admin only)"""
    try:
        with get_db_session() as db:
            wallet = WalletService.get_or_create_user(db, user_id)
            return jsonify({
                'wallet': {
                    'credits_remaining': float(wallet.credits_remaining),
                    'total_purchased': float(wallet.total_purchased),
                    'daily_usage': float(wallet.daily_usage),
                    'last_topped_up': wallet.last_topped_up.isoformat() if wallet.last_topped_up else None
                }
            })
    except Exception as e:
        logger.error(f"Admin get balance error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/users/<user_id>/credits', methods=['POST'])
@require_admin
def billing_admin_add_credits(user_id):
    """Add credits to user's wallet (Admin only)"""
    try:
        data = request.get_json()
        credits = Decimal(str(data.get('credits', 0)))
        
        if credits <= 0:
            return jsonify({"error": "Credits must be greater than 0"}), 400
        
        with get_db_session() as db:
            success, new_balance = WalletService.add_credits(db, user_id, credits)
            
            if success:
                logger.info(f"Admin added {credits} credits to user {user_id}")
                return jsonify({
                    'success': True,
                    'credits_added': float(credits),
                    'new_balance': float(new_balance)
                })
            return jsonify({"error": "Failed to add credits"}), 500
    except Exception as e:
        logger.error(f"Admin add credits error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/users/<user_id>/suspend', methods=['POST'])
@require_admin
def billing_admin_suspend_user(user_id):
    """Suspend a user (Admin only)"""
    try:
        with get_db_session() as db:
            success = UserManagementService.suspend_user(db, user_id)
            if success:
                logger.info(f"Admin suspended user {user_id}")
                return jsonify({'success': True})
            return jsonify({"error": "Failed to suspend user"}), 500
    except Exception as e:
        logger.error(f"Admin suspend user error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/users/<user_id>/unsuspend', methods=['POST'])
@require_admin
def billing_admin_unsuspend_user(user_id):
    """Unsuspend a user (Admin only)"""
    try:
        with get_db_session() as db:
            success = UserManagementService.unsuspend_user(db, user_id)
            if success:
                logger.info(f"Admin unsuspended user {user_id}")
                return jsonify({'success': True})
            return jsonify({"error": "Failed to unsuspend user"}), 500
    except Exception as e:
        logger.error(f"Admin unsuspend user error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/settings', methods=['GET'])
@require_admin
def billing_admin_get_settings():
    """Get all billing settings (Admin only)"""
    try:
        with get_db_session() as db:
            settings = SettingsService.get_all_settings(db)
            return jsonify({'settings': settings})
    except Exception as e:
        logger.error(f"Admin get settings error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/settings/<key>', methods=['PUT'])
@require_admin
def billing_admin_update_setting(key):
    """Update a billing setting (Admin only)"""
    try:
        data = request.get_json()
        value = data.get('value')
        
        with get_db_session() as db:
            success = SettingsService.update_setting(db, key, value, updated_by=request.user.get('email', 'admin'))
            if success:
                logger.info(f"Admin updated setting {key} to {value}")
                return jsonify({'success': True})
            return jsonify({"error": "Failed to update setting"}), 500
    except Exception as e:
        logger.error(f"Admin update setting error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/plans', methods=['GET'])
@require_admin
def billing_admin_get_plans():
    """Get all subscription plans including inactive (Admin only)"""
    try:
        with get_db_session() as db:
            plans = PlanService.get_all_plans(db, admin_view=True)
            return jsonify({'plans': plans})
    except Exception as e:
        logger.error(f"Admin get plans error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/plans', methods=['POST'])
@require_admin
def billing_admin_create_plan():
    """Create a new subscription plan (Admin only)"""
    try:
        data = request.get_json()
        
        with get_db_session() as db:
            plan = PlanService.create_plan(db, data)
            logger.info(f"Admin created plan: {plan['id']}")
            return jsonify({'plan': plan}), 201
    except Exception as e:
        logger.error(f"Admin create plan error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/plans/<plan_id>', methods=['PUT'])
@require_admin
def billing_admin_update_plan(plan_id):
    """Update a subscription plan (Admin only)"""
    try:
        data = request.get_json()
        
        with get_db_session() as db:
            plan = PlanService.update_plan(db, plan_id, data)
            if plan:
                logger.info(f"Admin updated plan: {plan_id}")
                return jsonify({'plan': plan})
            return jsonify({"error": "Plan not found"}), 404
    except Exception as e:
        logger.error(f"Admin update plan error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/plans/<plan_id>', methods=['DELETE'])
@require_admin
def billing_admin_delete_plan(plan_id):
    """Delete a subscription plan (Admin only)"""
    try:
        with get_db_session() as db:
            success = PlanService.delete_plan(db, plan_id)
            if success:
                logger.info(f"Admin deleted plan: {plan_id}")
                return jsonify({'success': True})
            return jsonify({"error": "Failed to delete plan"}), 500
    except Exception as e:
        logger.error(f"Admin delete plan error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/billing/admin/analytics', methods=['GET'])
@require_admin
def billing_admin_get_analytics():
    """Get analytics data (Admin only)"""
    try:
        with get_db_session() as db:
            analytics = AnalyticsService.get_dashboard_analytics(db)
            return jsonify(analytics)
    except Exception as e:
        logger.error(f"Admin get analytics error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("RAG AGENT SYSTEM - REST API SERVER")
    print("="*60)
    print(f"Server starting on http://localhost:5000")
    print(f"Total agents loaded: {len(rag_system.agents)}")
    print(f"Token Manager: {'Enabled' if token_manager else 'Disabled (fallback mode)'}")
    print(f"Billing System: {'Enabled' if BILLING_ENABLED else 'Disabled'}")
    print("\nProtected Endpoints (JWT Required):")
    print("  GET    /agents                      - List user's agents")
    print("  GET    /agents/<name>               - Get agent info")
    print("  POST   /agents/create               - Create new agent")
    print("  POST   /agents/<name>/query         - Query agent")
    print("  POST   /agents/<name>/embed-token   - Generate embed token")
    print("  DELETE /agents/<name>               - Delete agent")
    print("\nBilling Endpoints:")
    print("  GET    /billing/balance             - Get credit balance")
    print("  GET    /billing/plans               - Get pricing plans")
    print("  POST   /billing/create-order        - Create Razorpay order")
    print("  POST   /billing/verify-payment      - Verify payment")
    print("  POST   /billing/webhook             - Razorpay webhook")
    print("  GET    /billing/usage               - Get usage history")
    print("  GET    /billing/payments            - Get payment history")
    print("\nPublic Endpoints (No Auth):")
    print("  GET    /health                      - Health check")
    print("  GET    /widget.js                   - Embed widget script")
    print("\n" + "="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)