# Backend-Only Widget API Documentation (v1)

Build your own custom chatbot UI with full control over styling and behavior.

## Base URL
```
http://localhost:5000/v1
```

## Security Features

| Feature | Description |
|---------|-------------|
| **API Versioning** | All endpoints prefixed with `/v1/` |
| **Domain Allowlist** | Restrict tokens to specific domains |
| **Rate Limiting** | 20 requests per minute per token |
| **Monthly Quota** | 10,000 requests per month (configurable) |
| **Token Status** | Active, suspended, or revoked |

---

## Response Envelope

All API responses follow this standardized format:

### Success Response
```json
{
  "success": true,
  "data": { ... },
  "metadata": {
    "response_time_ms": 120,
    "tokens_used": 150
  },
  "error": null,
  "request_id": "abc12345",
  "timestamp": "2024-01-01T12:00:00Z",
  "api_version": "v1"
}
```

### Error Response
```json
{
  "success": false,
  "data": null,
  "metadata": null,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit of 20 requests per minute exceeded"
  },
  "request_id": "abc12345",
  "timestamp": "2024-01-01T12:00:00Z",
  "api_version": "v1"
}
```

### Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_TOKEN` | 404 | Token not found |
| `TOKEN_EXPIRED` | 403 | Token has expired |
| `TOKEN_SUSPENDED` | 403 | Token temporarily suspended |
| `TOKEN_REVOKED` | 403 | Token permanently revoked |
| `DOMAIN_NOT_ALLOWED` | 403 | Origin not in allowlist |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `MONTHLY_QUOTA_EXCEEDED` | 429 | Monthly limit reached |
| `VALIDATION_ERROR` | 400 | Invalid request data |

---

## Endpoints

### 1. Get Widget Configuration
```http
GET /v1/embed/{token}/config
```

Returns agent info, feature flags, rate limit status, and UI hints.

**Response:**
```json
{
  "success": true,
  "data": {
    "config": {
      "agent": {
        "name": "My Agent",
        "domain": "Customer Support",
        "description": "Answers product questions"
      },
      "features": {
        "streaming": false,
        "file_upload": false,
        "feedback": true
      },
      "rate_limit": {
        "limit": 20,
        "remaining": 18,
        "window_seconds": 60
      },
      "ui_hints": {
        "placeholder": "Ask about Customer Support...",
        "welcome_message": "Hi! How can I help?"
      }
    }
  }
}
```

---

### 2. Send Query
```http
POST /v1/embed/{token}/query
Content-Type: application/json

{
  "query": "How do I reset my password?",
  "conversation_id": "optional-session-id"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "answer": "To reset your password, go to Settings > Security...",
    "agent_name": "My Agent"
  },
  "metadata": {
    "response_time_ms": 1200,
    "tokens_used": 150,
    "sources_count": 3
  },
  "request_id": "abc12345"
}
```

---

### 3. Get Agent Info
```http
GET /v1/embed/{token}/info
```

Returns basic agent information.

---

### 4. Conversation Management
```http
GET /v1/embed/{token}/conversation
```
Returns hints for client-side conversation storage.

```http
DELETE /v1/embed/{token}/conversation
```
Signals that conversation should be cleared.

---

### 5. Submit Feedback
```http
POST /v1/embed/{token}/feedback
Content-Type: application/json

{
  "message_id": "msg-123",
  "type": "positive",
  "comment": "Very helpful!"
}
```

**type**: `positive` or `negative`

---

### 6. Track Analytics
```http
POST /v1/embed/{token}/analytics
Content-Type: application/json

{
  "event": "widget_open",
  "data": {
    "page_url": "https://example.com/help"
  }
}
```

**Event Types:** `widget_open`, `widget_close`, `message_sent`, `message_received`

---

## Rate Limiting

| Limit | Value |
|-------|-------|
| Per-minute | 20 requests |
| Monthly quota | 10,000 requests |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Reset timestamp

---

## Example: JavaScript Integration

```javascript
const API_BASE = 'http://localhost:5000/v1';
const TOKEN = 'your-embed-token';

async function sendMessage(query) {
  const res = await fetch(`${API_BASE}/embed/${TOKEN}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  
  const result = await res.json();
  
  if (result.success) {
    return result.data.answer;
  } else {
    throw new Error(result.error.message);
  }
}
```

## Example: cURL

```bash
# Get config
curl http://localhost:5000/v1/embed/YOUR_TOKEN/config

# Send query
curl -X POST http://localhost:5000/v1/embed/YOUR_TOKEN/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello"}'

# Submit feedback
curl -X POST http://localhost:5000/v1/embed/YOUR_TOKEN/feedback \
  -H "Content-Type: application/json" \
  -d '{"type": "positive", "message_id": "msg-1"}'
```

---

## Legacy Routes

For backward compatibility, non-versioned routes still work:
- `/embed/{token}/query` → `/v1/embed/{token}/query`

**Recommendation:** Migrate to `/v1/` endpoints for future compatibility.
