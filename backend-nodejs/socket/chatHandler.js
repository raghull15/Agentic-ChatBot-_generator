/**
 * ChatHandler - Manages WebSocket chat streaming
 * Proxies Flask SSE endpoints to WebSocket for bidirectional communication
 * Supports query cancellation, typing indicators, and better error handling
 */

class ChatHandler {
    constructor(io) {
        this.io = io;
        this.activeQueries = new Map(); // messageId -> { controller, socket, agentName }
    }

    /**
     * Setup chat event handlers for a socket connection
     */
    setupHandlers(socket) {
        // Handle new chat query
        socket.on('chat:send', async (data) => {
            await this.handleChatSend(socket, data);
        });

        // Handle query cancellation
        socket.on('chat:cancel', (data) => {
            this.handleChatCancel(socket, data);
        });

        // Cleanup on disconnect
        socket.on('disconnect', () => {
            this.cleanupSocketQueries(socket.id);
        });
    }

    /**
     * Handle incoming chat query from client
     */
    async handleChatSend(socket, data) {
        const { agentName, agentId, query, k = 4, messageId } = data;
        const userId = socket.userId;

        if (!messageId || !query) {
            socket.emit('chat:error', {
                messageId: messageId || 'unknown',
                error: 'Missing required fields: messageId and query',
                code: 'INVALID_REQUEST'
            });
            return;
        }

        console.log(`📨 Chat query from user ${userId}: agent=${agentName || agentId}, messageId=${messageId}`);

        try {
            // Emit typing indicator
            socket.emit('chat:typing', { isTyping: true });

            // Create abort controller for cancellation support
            const abortController = new AbortController();
            this.activeQueries.set(messageId, {
                controller: abortController,
                socket: socket,
                agentName: agentName || agentId,
                userId
            });

            // Prepare Flask endpoint URL
            const flaskUrl = process.env.FLASK_API_URL || 'http://localhost:5000';
            let endpoint;

            if (agentId) {
                endpoint = `${flaskUrl}/agents/id/${agentId}/query/stream`;
            } else if (agentName) {
                endpoint = `${flaskUrl}/agents/${agentName}/query/stream`;
            } else {
                throw new Error('Either agentName or agentId required');
            }

            // Forward token for authentication
            const token = socket.handshake.auth.token;

            // Call Flask streaming endpoint
            const fetch = (await import('node-fetch')).default;
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : ''
                },
                body: JSON.stringify({ query, k }),
                signal: abortController.signal
            });

            // Handle non-OK responses
            if (!response.ok) {
                let errorMessage = 'Query failed';
                let errorCode = 'SERVER_ERROR';

                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;

                    if (response.status === 402) {
                        errorCode = 'INSUFFICIENT_CREDITS';
                    } else if (response.status === 404) {
                        errorCode = 'AGENT_NOT_FOUND';
                    }
                } catch (e) {
                    // Failed to parse error response
                }

                socket.emit('chat:typing', { isTyping: false });
                socket.emit('chat:error', {
                    messageId,
                    error: errorMessage,
                    code: errorCode
                });

                this.activeQueries.delete(messageId);
                return;
            }

            // Stream SSE response to WebSocket
            await this.streamResponseToSocket(socket, response, messageId);

            // Cleanup
            socket.emit('chat:typing', { isTyping: false });
            this.activeQueries.delete(messageId);

        } catch (error) {
            console.error(`Chat error for messageId ${messageId}:`, error);

            socket.emit('chat:typing', { isTyping: false });

            if (error.name === 'AbortError') {
                socket.emit('chat:error', {
                    messageId,
                    error: 'Query cancelled by user',
                    code: 'CANCELLED'
                });
            } else {
                socket.emit('chat:error', {
                    messageId,
                    error: error.message || 'Unknown error occurred',
                    code: 'NETWORK_ERROR'
                });
            }

            this.activeQueries.delete(messageId);
        }
    }

    /**
     * Stream Flask SSE response to WebSocket client
     */
    async streamResponseToSocket(socket, response, messageId) {
        const decoder = new TextDecoder();
        let buffer = '';
        let finalData = null;

        for await (const chunk of response.body) {
            const text = decoder.decode(chunk, { stream: true });
            buffer += text;

            // Process complete SSE lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();

                    // Check for done signal
                    if (data === '[DONE]') {
                        // Send final message
                        if (finalData) {
                            socket.emit('chat:done', {
                                messageId,
                                ...finalData
                            });
                        } else {
                            socket.emit('chat:done', { messageId });
                        }
                        return;
                    }

                    // Try to parse as JSON
                    try {
                        const parsed = JSON.parse(data);

                        if (parsed.type === 'chunk' && parsed.content) {
                            // Stream chunk to client
                            socket.emit('chat:chunk', {
                                messageId,
                                chunk: parsed.content
                            });
                        } else if (parsed.type === 'done') {
                            // Store final data but don't emit yet (wait for [DONE])
                            finalData = {
                                answer: parsed.answer,
                                sources: parsed.sources || [],
                                credits_used: parsed.credits_used,
                                token_usage: parsed.token_usage
                            };
                        } else if (parsed.type === 'error' || parsed.type === 'billing_error') {
                            socket.emit('chat:error', {
                                messageId,
                                error: parsed.error || parsed.content || 'Unknown error',
                                code: parsed.type === 'billing_error' ? 'INSUFFICIENT_CREDITS' : 'QUERY_ERROR'
                            });
                            return;
                        } else if (parsed.token) {
                            // Legacy format support
                            socket.emit('chat:chunk', {
                                messageId,
                                chunk: parsed.token
                            });
                        }
                    } catch (e) {
                        // Not JSON, treat as raw chunk
                        if (data) {
                            socket.emit('chat:chunk', {
                                messageId,
                                chunk: data
                            });
                        }
                    }
                }
            }
        }

        // If we exit loop without [DONE], emit done with any accumulated data
        if (finalData) {
            socket.emit('chat:done', {
                messageId,
                ...finalData
            });
        } else {
            socket.emit('chat:done', { messageId });
        }
    }

    /**
     * Handle query cancellation request
     */
    handleChatCancel(socket, data) {
        const { messageId } = data;
        const queryInfo = this.activeQueries.get(messageId);

        if (queryInfo && queryInfo.socket.id === socket.id) {
            console.log(`🚫 Cancelling query: ${messageId}`);
            queryInfo.controller.abort();
            this.activeQueries.delete(messageId);
        }
    }

    /**
     * Cleanup all queries for a disconnected socket
     */
    cleanupSocketQueries(socketId) {
        let cancelled = 0;
        for (const [messageId, queryInfo] of this.activeQueries.entries()) {
            if (queryInfo.socket.id === socketId) {
                queryInfo.controller.abort();
                this.activeQueries.delete(messageId);
                cancelled++;
            }
        }
        if (cancelled > 0) {
            console.log(`🧹 Cleaned up ${cancelled} active queries for socket ${socketId}`);
        }
    }

    /**
     * Get statistics for monitoring
     */
    getStats() {
        return {
            activeQueries: this.activeQueries.size,
            queries: Array.from(this.activeQueries.entries()).map(([messageId, info]) => ({
                messageId,
                userId: info.userId,
                agentName: info.agentName
            }))
        };
    }
}

export default ChatHandler;
