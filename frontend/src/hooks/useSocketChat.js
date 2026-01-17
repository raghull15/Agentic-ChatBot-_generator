import { useState, useEffect, useCallback, useRef } from 'react';
import { useSocket } from '../context/SocketContext';
import { v4 as uuidv4 } from 'uuid';

/**
 * useSocketChat - React hook for WebSocket-based chat streaming
 * 
 * Features:
 * - Real-time streaming responses
 * - Query cancellation
 * - Typing indicators
 * - Connection status
 * - Automatic error handling
 * 
 * @param {string} agentName - Name of the agent to chat with
 * @param {string} agentId - ID of the agent (alternative to agentName)
 * @returns {object} Chat interface
 */
export function useSocketChat(agentName, agentId) {
    const { socket, connected } = useSocket();
    const [messages, setMessages] = useState([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [error, setError] = useState(null);

    const currentMessageId = useRef(null);
    const streamingContent = useRef('');

    /**
     * Send a query to the agent
     */
    const sendQuery = useCallback((query, k = 4) => {
        if (!socket || !connected) {
            setError('Not connected to server. Please check your connection.');
            return null;
        }

        if (!query || !query.trim()) {
            setError('Query cannot be empty');
            return null;
        }

        const messageId = uuidv4();
        currentMessageId.current = messageId;
        streamingContent.current = '';

        // Add user message to UI
        setMessages(prev => [...prev, {
            id: uuidv4(),
            role: 'user',
            content: query,
            timestamp: new Date()
        }]);

        // Add placeholder for assistant response
        setMessages(prev => [...prev, {
            id: messageId,
            role: 'assistant',
            content: '',
            messageId,
            isStreaming: true,
            timestamp: new Date()
        }]);

        setIsStreaming(true);
        setError(null);

        // Emit query to server
        socket.emit('chat:send', {
            agentName,
            agentId,
            query,
            k,
            messageId
        });

        console.log('📤 Sent query:', { agentName, agentId, messageId });

        return messageId;
    }, [socket, connected, agentName, agentId]);

    /**
     * Cancel the current streaming query
     */
    const cancelQuery = useCallback(() => {
        if (currentMessageId.current && socket) {
            socket.emit('chat:cancel', {
                messageId: currentMessageId.current
            });

            console.log('🚫 Cancelled query:', currentMessageId.current);

            setIsStreaming(false);
            setIsTyping(false);

            // Mark message as cancelled
            setMessages(prev => prev.map(msg =>
                msg.messageId === currentMessageId.current
                    ? { ...msg, content: msg.content || '(Query cancelled)', isStreaming: false, isCancelled: true }
                    : msg
            ));
        }
    }, [socket]);

    /**
     * Clear all messages
     */
    const clearMessages = useCallback(() => {
        setMessages([]);
        setError(null);
    }, []);

    // Setup WebSocket event listeners
    useEffect(() => {
        if (!socket) return;

        // Handle streaming chunks
        const handleChunk = (data) => {
            if (data.messageId !== currentMessageId.current) return;

            streamingContent.current += data.chunk;

            setMessages(prev => prev.map(msg =>
                msg.messageId === data.messageId
                    ? { ...msg, content: streamingContent.current }
                    : msg
            ));
        };

        // Handle completion
        const handleDone = (data) => {
            if (data.messageId !== currentMessageId.current) return;

            console.log('✅ Query complete:', data);

            setMessages(prev => prev.map(msg =>
                msg.messageId === data.messageId
                    ? {
                        ...msg,
                        content: data.answer || streamingContent.current,
                        isStreaming: false,
                        sources: data.sources || [],
                        creditsUsed: data.credits_used,
                        tokenUsage: data.token_usage,
                        completedAt: new Date()
                    }
                    : msg
            ));

            setIsStreaming(false);
            setIsTyping(false);
            currentMessageId.current = null;
            streamingContent.current = '';
        };

        // Handle errors
        const handleError = (data) => {
            if (data.messageId && data.messageId !== currentMessageId.current) return;

            console.error('❌ Chat error:', data);

            setError(data.error);
            setIsStreaming(false);
            setIsTyping(false);

            // Remove placeholder message or mark as error
            setMessages(prev => {
                if (data.messageId) {
                    return prev.map(msg =>
                        msg.messageId === data.messageId
                            ? { ...msg, content: `Error: ${data.error}`, isStreaming: false, isError: true, errorCode: data.code }
                            : msg
                    );
                } else {
                    // No messageId, just remove last assistant message if it's streaming
                    return prev.filter(msg => !msg.isStreaming);
                }
            });
        };

        // Handle typing indicator
        const handleTyping = (data) => {
            setIsTyping(data.isTyping);
        };

        // Register listeners
        socket.on('chat:chunk', handleChunk);
        socket.on('chat:done', handleDone);
        socket.on('chat:error', handleError);
        socket.on('chat:typing', handleTyping);

        // Cleanup
        return () => {
            socket.off('chat:chunk', handleChunk);
            socket.off('chat:done', handleDone);
            socket.off('chat:error', handleError);
            socket.off('chat:typing', handleTyping);
        };
    }, [socket]);

    return {
        // State
        messages,
        isStreaming,
        isTyping,
        error,
        connected,

        // Actions
        sendQuery,
        cancelQuery,
        clearMessages,

        // Utility
        canSend: connected && !isStreaming
    };
}
