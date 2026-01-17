// API Service for communicating with Flask backend
import { safeParseJson } from './utils/safeJson';

const API_BASE = '/api';

// Configuration
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const MAX_RETRIES = 3;
const RETRY_DELAY_BASE = 1000; // 1 second

// Helper to get auth header
const getAuthHeader = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Fetch with timeout and retry logic
 * @param {string} url - URL to fetch
 * @param {object} options - Fetch options
 * @param {number} timeout - Timeout in milliseconds
 * @param {number} retries - Number of retries
 * @returns {Promise<Response>}
 */
async function fetchWithRetry(url, options = {}, timeout = DEFAULT_TIMEOUT, retries = MAX_RETRIES) {
    let lastError = null;

    for (let attempt = 0; attempt < retries; attempt++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            // Don't retry on client errors (4xx), only on server errors (5xx) and network issues
            if (response.status >= 400 && response.status < 500) {
                return response;
            }

            if (response.ok || attempt === retries - 1) {
                return response;
            }

            // Server error, will retry
            lastError = new Error(`Server error: ${response.status}`);
        } catch (error) {
            clearTimeout(timeoutId);
            lastError = error;

            if (error.name === 'AbortError') {
                lastError = new Error('Request timeout - server took too long to respond');
            }

            // Don't retry if it's the last attempt
            if (attempt === retries - 1) {
                throw lastError;
            }
        }

        // Wait before retrying (exponential backoff)
        const delay = RETRY_DELAY_BASE * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
    }

    throw lastError || new Error('Request failed after retries');
}

// ==================== AUTH API ====================

/**
 * Request password reset email
 * @param {string} email - User's email address
 */
export async function forgotPassword(email) {
    const response = await fetchWithRetry('/auth/forgot-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
    });

    const data = await safeParseJson(response);

    if (!response.ok) {
        throw new Error(data.error || 'Failed to send reset email');
    }

    return data;
}

/**
 * Reset password with token
 * @param {string} token - Reset token from email link
 * @param {string} password - New password
 */
export async function resetPassword(token, password) {
    const response = await fetchWithRetry('/auth/reset-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token, password }),
    });

    const data = await safeParseJson(response);

    if (!response.ok) {
        throw new Error(data.error || 'Failed to reset password');
    }

    return data;
}

// ==================== AGENTS API ====================

/**
 * Fetch all agents from the backend (filtered by authenticated user)
 */
export async function fetchAgents() {
    const response = await fetchWithRetry(`${API_BASE}/agents`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view agents');
    }

    if (!response.ok) {
        throw new Error('Failed to fetch agents');
    }
    const data = await safeParseJson(response);
    return data.agents || [];
}

/**
 * Get a specific agent's information
 */
export async function getAgent(agentName) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view agent');
    }

    if (!response.ok) {
        throw new Error('Agent not found');
    }
    const data = await safeParseJson(response);
    return data.agent;
}

/**
 * Create a new agent with PDF files
 */
export async function createAgent(agentName, domain, description, files) {
    const formData = new FormData();
    formData.append('agent_name', agentName);
    formData.append('domain', domain);
    formData.append('description', description);

    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    const response = await fetchWithRetry(`${API_BASE}/agents/create`, {
        method: 'POST',
        headers: {
            ...getAuthHeader(),
        },
        body: formData,
    }, 120000, 2); // 2 min timeout, 2 retries for file uploads

    if (response.status === 401) {
        throw new Error('Please login to create agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to create agent');
    }
    return data;
}

/**
 * Create a demo agent (first-time users only, no credit cost)
 */
export async function createDemoAgent(agentName, domain, description, files) {
    const formData = new FormData();
    formData.append('agent_name', agentName);
    formData.append('domain', domain);
    formData.append('description', description);

    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    const response = await fetchWithRetry(`${API_BASE}/agents/create-demo`, {
        method: 'POST',
        headers: {
            ...getAuthHeader(),
        },
        body: formData,
    }, 120000, 2);

    if (response.status === 401) {
        throw new Error('Please login to create demo agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to create demo agent');
    }
    return data;
}

/**
 * Create a new agent from various data sources (CSV, Word, SQL, NoSQL)
 */
export async function createAgentFromSource(agentName, domain, description, sourceType, sourceConfig) {
    const formData = new FormData();
    formData.append('agent_name', agentName);
    formData.append('domain', domain);
    formData.append('description', description);
    formData.append('source_type', sourceType);

    // Handle file-based sources
    if (['csv', 'word', 'txt'].includes(sourceType) && sourceConfig.files) {
        for (let i = 0; i < sourceConfig.files.length; i++) {
            formData.append('files', sourceConfig.files[i]);
        }
    }

    // Handle SQL source
    if (sourceType === 'sql') {
        formData.append('connection_string', sourceConfig.connection_string || '');
        if (sourceConfig.tables) {
            formData.append('tables', JSON.stringify(sourceConfig.tables));
        }
        formData.append('sample_limit', String(sourceConfig.sample_limit || 1000));
    }

    // Handle NoSQL source
    if (sourceType === 'nosql') {
        formData.append('connection_string', sourceConfig.connection_string || '');
        formData.append('database', sourceConfig.database || '');
        if (sourceConfig.collections) {
            formData.append('collections', JSON.stringify(sourceConfig.collections));
        }
        formData.append('sample_limit', String(sourceConfig.sample_limit || 1000));
    }

    const response = await fetchWithRetry(`${API_BASE}/agents/create-from-source`, {
        method: 'POST',
        headers: {
            ...getAuthHeader(),
        },
        body: formData,
    }, 120000, 2); // 2 min timeout, 2 retries for data source processing

    if (response.status === 401) {
        throw new Error('Please login to create agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to create agent');
    }
    return data;
}

/**
 * Update an existing agent with more data
 */
export async function updateAgentData(agentName, sourceType, sourceConfig) {
    const formData = new FormData();
    formData.append('source_type', sourceType);

    // Handle file-based sources
    if (['pdf', 'csv', 'word'].includes(sourceType) && sourceConfig.files) {
        for (let i = 0; i < sourceConfig.files.length; i++) {
            formData.append('files', sourceConfig.files[i]);
        }
    }

    // Handle SQL source
    if (sourceType === 'sql') {
        formData.append('connection_string', sourceConfig.connection_string || '');
        if (sourceConfig.tables) {
            formData.append('tables', JSON.stringify(sourceConfig.tables));
        }
        formData.append('sample_limit', String(sourceConfig.sample_limit || 1000));
    }

    // Handle NoSQL source
    if (sourceType === 'nosql') {
        formData.append('connection_string', sourceConfig.connection_string || '');
        formData.append('database', sourceConfig.database || '');
        if (sourceConfig.collections) {
            formData.append('collections', JSON.stringify(sourceConfig.collections));
        }
        formData.append('sample_limit', String(sourceConfig.sample_limit || 1000));
    }

    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}/update`, {
        method: 'POST',
        headers: {
            ...getAuthHeader(),
        },
        body: formData,
    }, 120000, 2); // 2 min timeout, 2 retries for file uploads

    if (response.status === 401) {
        throw new Error('Please login to update agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to update agent');
    }
    return data;
}

/**
 * Query an agent with a question
 */
export async function queryAgent(agentName, query, k = 4) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}/query`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
        },
        body: JSON.stringify({ query, k }),
    }, 60000, 2); // 1 min timeout for queries

    if (response.status === 401) {
        throw new Error('Please login to query agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to query agent');
    }
    return data;
}

/**
 * Delete an agent
 */
export async function deleteAgent(agentName) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}`, {
        method: 'DELETE',
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to delete agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to delete agent');
    }
    return data;
}

/**
 * Generate embed token for an agent
 */
export async function generateEmbedToken(agentName) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}/embed-token`, {
        method: 'POST',
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to generate embed token');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to generate embed token');
    }
    return data;
}

/**
 * Check if the backend is healthy
 */
export async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        if (!response.ok) return false;
        const data = await safeParseJson(response);
        return data.status === 'healthy';
    } catch {
        return false;
    }
}

/**
 * Check if auth server is healthy
 */
export async function checkAuthHealth() {
    try {
        const response = await fetch('/auth/health');
        if (!response.ok) return false;
        const data = await safeParseJson(response);
        return data.status === 'healthy';
    } catch {
        return false;
    }
}

/**
 * Get current user's token usage stats
 */
export async function getUserStats() {
    const response = await fetchWithRetry(`${API_BASE}/user/stats`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view stats');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch stats');
    }
    return data.stats || {};
}

/**
 * Update agent settings (system_prompt, welcome_message, etc.)
 */
export async function updateAgentSettings(agentName, settings) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}/settings`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
        },
        body: JSON.stringify(settings),
    });

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to update settings');
    }
    return data;
}

/**
 * Export agent configuration
 */
export async function exportAgent(agentName) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}/export`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to export agent');
    }
    return data.export;
}

/**
 * Get agent analytics
 */
export async function getAgentAnalytics(agentName) {
    const response = await fetchWithRetry(`${API_BASE}/agents/${encodeURIComponent(agentName)}/analytics`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch analytics');
    }
    return data.analytics || {};
}

// ==================== ID-BASED AGENT API FUNCTIONS ====================
// These functions use agent IDs (UUIDs) instead of names for unique routing

/**
 * Get agent by ID
 */
export async function getAgentById(agentId) {
    const response = await fetchWithRetry(`${API_BASE}/agents/id/${agentId}`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch agent');
    }
    return data.agent;
}

/**
 * Query an agent by ID
 */
export async function queryAgentById(agentId, query, k = 4) {
    const response = await fetchWithRetry(`${API_BASE}/agents/id/${agentId}/query`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
        },
        body: JSON.stringify({ query, k }),
    }, 60000, 2);

    if (response.status === 401) {
        throw new Error('Please login to query agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to query agent');
    }
    return data;
}

/**
 * Delete an agent by ID
 */
export async function deleteAgentById(agentId) {
    const response = await fetchWithRetry(`${API_BASE}/agents/id/${agentId}`, {
        method: 'DELETE',
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to delete agent');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to delete agent');
    }
    return data;
}

// ==================== ADMIN API FUNCTIONS ====================

/**
 * Get all users with token usage (admin only)
 */
export async function getAdminUsers() {
    const response = await fetchWithRetry(`${API_BASE}/admin/users`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to access admin panel');
    }

    if (response.status === 403) {
        throw new Error('Admin access required');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch users');
    }
    return data.users || [];
}

/**
 * Get aggregated token usage statistics (admin only)
 */
export async function getAdminUsage() {
    const response = await fetch(`${API_BASE}/admin/usage`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to access admin panel');
    }

    if (response.status === 403) {
        throw new Error('Admin access required');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch usage');
    }
    return data;
}

/**
 * Get detailed token usage for a specific user (admin only)
 */
export async function getAdminUserUsage(userId, limit = 50) {
    const response = await fetch(`${API_BASE}/admin/usage/${userId}?limit=${limit}`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to access admin panel');
    }

    if (response.status === 403) {
        throw new Error('Admin access required');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch user usage');
    }
    return data.queries || [];
}

/**
 * Add credits to a user's wallet (admin only)
 */
export async function adminAddCredits(userId, amount) {
    const response = await fetch(`${API_BASE}/admin/users/${userId}/credits`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
        },
        body: JSON.stringify({ amount }),
    });

    if (response.status === 401) {
        throw new Error('Please login to access admin panel');
    }

    if (response.status === 403) {
        throw new Error('Admin access required');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to add credits');
    }
    return data;
}

/**
 * Get a user's credit balance (admin only)
 */
export async function adminGetUserBalance(userId) {
    const response = await fetch(`${API_BASE}/admin/users/${userId}/balance`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to access admin panel');
    }

    if (response.status === 403) {
        throw new Error('Admin access required');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch user balance');
    }
    return data.wallet;
}

/**
 * Get all billing settings (admin only)
 */
export async function adminGetSettings() {
    const response = await fetch(`${API_BASE}/admin/settings`, {
        headers: { ...getAuthHeader() },
    });
    if (!response.ok) throw new Error('Failed to fetch settings');
    const data = await safeParseJson(response);
    return data.settings;
}

/**
 * Update a billing setting (admin only)
 */
export async function adminUpdateSetting(key, value) {
    const response = await fetch(`${API_BASE}/admin/settings/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({ value }),
    });
    if (!response.ok) throw new Error('Failed to update setting');
    return safeParseJson(response);
}

/**
 * Get all subscription plans (admin only)
 */
export async function adminGetPlans() {
    const response = await fetch(`${API_BASE}/admin/plans`, {
        headers: { ...getAuthHeader() },
    });
    if (!response.ok) throw new Error('Failed to fetch plans');
    const data = await safeParseJson(response);
    return data.plans;
}

/**
 * Create a subscription plan (admin only)
 */
export async function adminCreatePlan(planData) {
    const response = await fetch(`${API_BASE}/admin/plans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(planData),
    });
    if (!response.ok) throw new Error('Failed to create plan');
    return safeParseJson(response);
}

/**
 * Update a subscription plan (admin only)
 */
export async function adminUpdatePlan(planId, planData) {
    const response = await fetch(`${API_BASE}/admin/plans/${planId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(planData),
    });
    if (!response.ok) throw new Error('Failed to update plan');
    return safeParseJson(response);
}

/**
 * Delete (deactivate) a subscription plan (admin only)
 */
export async function adminDeletePlan(planId) {
    const response = await fetch(`${API_BASE}/admin/plans/${planId}`, {
        method: 'DELETE',
        headers: { ...getAuthHeader() },
    });
    if (!response.ok) throw new Error('Failed to delete plan');
    return safeParseJson(response);
}

/**
 * Suspend a user (admin only)
 */
export async function adminSuspendUser(userId) {
    const response = await fetch(`${API_BASE}/admin/users/${userId}/suspend`, {
        method: 'POST',
        headers: { ...getAuthHeader() },
    });
    if (!response.ok) throw new Error('Failed to suspend user');
    return safeParseJson(response);
}

/**
 * Unsuspend a user (admin only)
 */
export async function adminUnsuspendUser(userId) {
    const response = await fetch(`${API_BASE}/admin/users/${userId}/unsuspend`, {
        method: 'POST',
        headers: { ...getAuthHeader() },
    });
    if (!response.ok) throw new Error('Failed to unsuspend user');
    return safeParseJson(response);
}

/**
 * Get usage and revenue analytics (admin only)
 */
export async function adminGetAnalytics(days = 30) {
    const response = await fetch(`${API_BASE}/admin/analytics?days=${days}`, {
        headers: { ...getAuthHeader() },
    });
    if (!response.ok) throw new Error('Failed to fetch analytics');
    const data = await safeParseJson(response);
    return data.analytics;
}

// ==================== BILLING API FUNCTIONS ====================

/**
 * Get user's credit balance and wallet info
 */
export async function getBalance() {
    const response = await fetchWithRetry(`${API_BASE}/billing/balance`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view balance');
    }

    if (response.status === 503) {
        throw new Error('Billing service not available');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch balance');
    }
    return data.wallet;
}

/**
 * Get available pricing plans
 */
export async function getPlans() {
    const response = await fetchWithRetry(`${API_BASE}/billing/plans`);

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch plans');
    }
    return data.plans || [];
}

/**
 * Create a Razorpay order for purchasing credits
 * Calls auth-server which handles Razorpay integration
 */
export async function createOrder(plan) {
    // Call auth-server for Razorpay order creation
    const response = await fetchWithRetry(`/payment/create-order`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
        },
        body: JSON.stringify({
            plan_id: plan.id,
            amount: plan.amount_inr,
            credits: plan.total_credits || plan.credits,
            plan_name: plan.name
        }),
    });

    if (response.status === 401) {
        throw new Error('Please login to purchase credits');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to create order');
    }
    return data.order;
}

/**
 * Verify Razorpay payment and add credits
 * Calls auth-server which verifies signature and adds credits via Flask
 */
export async function verifyPayment(orderId, paymentId, signature, credits) {
    // Call auth-server for payment verification
    const response = await fetchWithRetry(`/payment/verify`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...getAuthHeader(),
        },
        body: JSON.stringify({
            razorpay_order_id: orderId,
            razorpay_payment_id: paymentId,
            razorpay_signature: signature,
            credits: credits
        }),
    });

    if (response.status === 401) {
        throw new Error('Please login to verify payment');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Payment verification failed');
    }
    return data;
}

/**
 * Get user's usage history
 */
export async function getUsageHistory(limit = 50, chatbotId = null) {
    let url = `${API_BASE}/billing/usage?limit=${limit}`;
    if (chatbotId) {
        url += `&chatbot_id=${encodeURIComponent(chatbotId)}`;
    }

    const response = await fetchWithRetry(url, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view usage');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch usage');
    }
    return data;
}

/**
 * Get user's payment history
 */
export async function getPaymentHistory(limit = 20) {
    const response = await fetchWithRetry(`${API_BASE}/billing/payments?limit=${limit}`, {
        headers: {
            ...getAuthHeader(),
        },
    });

    if (response.status === 401) {
        throw new Error('Please login to view payments');
    }

    const data = await safeParseJson(response);
    if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch payments');
    }
    return data.payments || [];
}
