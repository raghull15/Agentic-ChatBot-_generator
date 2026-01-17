/**
 * Safe JSON Parser Utility
 * Handles edge cases when parsing fetch Response objects
 */

/**
 * Safely parse JSON from a fetch Response
 * @param {Response} response - Fetch API Response object
 * @returns {Promise<any>} Parsed JSON or empty object
 * @throws {Error} On HTTP errors or invalid JSON
 */
export async function safeParseJson(response) {
    // Read response body as text
    const text = await response.text();

    // Check HTTP status
    if (!response.ok) {
        // Try to parse error message from JSON
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        if (text) {
            try {
                const errorData = JSON.parse(text);
                errorMessage = errorData.error || errorData.message || errorMessage;
            } catch {
                // If error response isn't JSON, include truncated text
                errorMessage += ` - ${text.substring(0, 200)}`;
            }
        }
        throw new Error(errorMessage);
    }

    // Empty response - return empty object
    if (!text || text.trim() === '') {
        return {};
    }

    // Parse JSON
    try {
        return JSON.parse(text);
    } catch (e) {
        throw new Error(`Invalid JSON response: ${e.message}. Body: ${text.substring(0, 200)}`);
    }
}
