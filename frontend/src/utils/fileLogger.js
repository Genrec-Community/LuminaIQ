/**
 * File-Based Logger for Frontend (Development Mode)
 *
 * This module extends the console logger with file-based logging capabilities
 * for development environments. Logs are buffered in memory and can be:
 * 1. Downloaded as a file
 * 2. Sent to a backend endpoint for persistent storage
 * 3. Automatically persisted to localStorage
 *
 * Usage:
 *   import { createFileLogger, downloadLogs, clearLogs } from '../utils/fileLogger';
 *   const logger = createFileLogger('MyComponent');
 *   logger.info('User logged in', { userId: '123' });
 *
 *   // Download logs
 *   downloadLogs();
 *
 *   // Clear logs
 *   clearLogs();
 */

const LOG_LEVELS = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3,
};

const CURRENT_LOG_LEVEL =
    import.meta.env.MODE === 'production' ? LOG_LEVELS.WARN : LOG_LEVELS.DEBUG;

// Configuration
const CONFIG = {
    enabled: import.meta.env.MODE === 'development',
    maxBufferSize: 1000, // Maximum number of log entries to keep in memory
    persistToLocalStorage: true,
    localStorageKey: 'lumina_dev_logs',
    autoFlushInterval: 30000, // Auto-flush to localStorage every 30 seconds
};

// In-memory log buffer
let logBuffer = [];
let autoFlushTimer = null;

/**
 * Initialize the file logger system
 */
const initializeFileLogger = () => {
    if (!CONFIG.enabled) return;

    // Load existing logs from localStorage
    if (CONFIG.persistToLocalStorage) {
        try {
            const stored = localStorage.getItem(CONFIG.localStorageKey);
            if (stored) {
                const parsed = JSON.parse(stored);
                logBuffer = Array.isArray(parsed) ? parsed : [];
                console.info(`[FileLogger] Loaded ${logBuffer.length} log entries from localStorage`);
            }
        } catch (error) {
            console.error('[FileLogger] Failed to load logs from localStorage:', error);
        }
    }

    // Set up auto-flush timer
    if (CONFIG.persistToLocalStorage && CONFIG.autoFlushInterval > 0) {
        autoFlushTimer = setInterval(() => {
            flushToLocalStorage();
        }, CONFIG.autoFlushInterval);
    }

    // Flush logs before page unload
    window.addEventListener('beforeunload', () => {
        flushToLocalStorage();
    });

    console.info('[FileLogger] File-based logging initialized');
};

/**
 * Flush log buffer to localStorage
 */
const flushToLocalStorage = () => {
    if (!CONFIG.enabled || !CONFIG.persistToLocalStorage) return;

    try {
        localStorage.setItem(CONFIG.localStorageKey, JSON.stringify(logBuffer));
    } catch (error) {
        console.error('[FileLogger] Failed to flush logs to localStorage:', error);
    }
};

/**
 * Add a log entry to the buffer
 */
const addLogEntry = (moduleName, level, message, args) => {
    if (!CONFIG.enabled) return;

    const entry = {
        timestamp: new Date().toISOString(),
        module: moduleName,
        level,
        message,
        data: args.length > 0 ? args : undefined,
        userAgent: navigator.userAgent,
        url: window.location.href,
    };

    logBuffer.push(entry);

    // Trim buffer if it exceeds max size
    if (logBuffer.length > CONFIG.maxBufferSize) {
        logBuffer = logBuffer.slice(-CONFIG.maxBufferSize);
    }
};

/**
 * Format a log prefix string
 */
const formatPrefix = (moduleName, level) => {
    const timestamp = new Date().toISOString();
    return `[LuminaIQ:${moduleName}] ${timestamp} ${level} —`;
};

/**
 * Serialize arguments for file logging (handles circular references)
 */
const serializeArgs = (args) => {
    return args.map(arg => {
        if (arg instanceof Error) {
            return {
                name: arg.name,
                message: arg.message,
                stack: arg.stack,
            };
        }
        try {
            // Test if object can be stringified
            JSON.stringify(arg);
            return arg;
        } catch (error) {
            // Handle circular references
            return String(arg);
        }
    });
};

/**
 * Create a file-based logger instance
 */
export const createFileLogger = (moduleName) => {
    if (!moduleName || typeof moduleName !== 'string') {
        throw new Error('createFileLogger requires a non-empty string moduleName');
    }

    return {
        debug(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.DEBUG) return;
            console.debug(formatPrefix(moduleName, 'DEBUG'), message, ...args);
            addLogEntry(moduleName, 'DEBUG', message, serializeArgs(args));
        },

        info(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.INFO) return;
            console.info(formatPrefix(moduleName, 'INFO'), message, ...args);
            addLogEntry(moduleName, 'INFO', message, serializeArgs(args));
        },

        warn(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.WARN) return;
            console.warn(formatPrefix(moduleName, 'WARN'), message, ...args);
            addLogEntry(moduleName, 'WARN', message, serializeArgs(args));
        },

        error(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.ERROR) return;
            console.error(formatPrefix(moduleName, 'ERROR'), message, ...args);
            addLogEntry(moduleName, 'ERROR', message, serializeArgs(args));
        },
    };
};

/**
 * Download logs as a JSON file
 */
export const downloadLogs = (filename = null) => {
    if (!CONFIG.enabled) {
        console.warn('[FileLogger] File logging is not enabled');
        return;
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const defaultFilename = `lumina-logs-${timestamp}.json`;
    const finalFilename = filename || defaultFilename;

    const dataStr = JSON.stringify(logBuffer, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = finalFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    console.info(`[FileLogger] Downloaded ${logBuffer.length} log entries as ${finalFilename}`);
};

/**
 * Download logs as a human-readable text file
 */
export const downloadLogsAsText = (filename = null) => {
    if (!CONFIG.enabled) {
        console.warn('[FileLogger] File logging is not enabled');
        return;
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const defaultFilename = `lumina-logs-${timestamp}.txt`;
    const finalFilename = filename || defaultFilename;

    const lines = logBuffer.map(entry => {
        const dataStr = entry.data ? ` ${JSON.stringify(entry.data)}` : '';
        return `[${entry.timestamp}] [${entry.level}] [${entry.module}] ${entry.message}${dataStr}`;
    });

    const content = lines.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = finalFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    console.info(`[FileLogger] Downloaded ${logBuffer.length} log entries as ${finalFilename}`);
};

/**
 * Get current log buffer
 */
export const getLogs = () => {
    return [...logBuffer];
};

/**
 * Get logs filtered by level
 */
export const getLogsByLevel = (level) => {
    return logBuffer.filter(entry => entry.level === level);
};

/**
 * Get logs filtered by module
 */
export const getLogsByModule = (moduleName) => {
    return logBuffer.filter(entry => entry.module === moduleName);
};

/**
 * Clear all logs
 */
export const clearLogs = () => {
    logBuffer = [];
    if (CONFIG.persistToLocalStorage) {
        try {
            localStorage.removeItem(CONFIG.localStorageKey);
            console.info('[FileLogger] Cleared all logs');
        } catch (error) {
            console.error('[FileLogger] Failed to clear logs from localStorage:', error);
        }
    }
};

/**
 * Get log statistics
 */
export const getLogStats = () => {
    const stats = {
        total: logBuffer.length,
        byLevel: {},
        byModule: {},
        oldestEntry: logBuffer[0]?.timestamp,
        newestEntry: logBuffer[logBuffer.length - 1]?.timestamp,
    };

    logBuffer.forEach(entry => {
        // Count by level
        stats.byLevel[entry.level] = (stats.byLevel[entry.level] || 0) + 1;
        // Count by module
        stats.byModule[entry.module] = (stats.byModule[entry.module] || 0) + 1;
    });

    return stats;
};

/**
 * Send logs to backend endpoint
 */
export const sendLogsToBackend = async (endpoint = '/api/v1/logs/frontend') => {
    if (!CONFIG.enabled) {
        console.warn('[FileLogger] File logging is not enabled');
        return;
    }

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
            body: JSON.stringify({
                logs: logBuffer,
                stats: getLogStats(),
            }),
        });

        if (!response.ok) {
            throw new Error(`Failed to send logs: ${response.statusText}`);
        }

        console.info(`[FileLogger] Sent ${logBuffer.length} log entries to backend`);
        return true;
    } catch (error) {
        console.error('[FileLogger] Failed to send logs to backend:', error);
        return false;
    }
};

// Initialize on module load
if (CONFIG.enabled) {
    initializeFileLogger();
}

// Expose logger controls to window for debugging
if (CONFIG.enabled && typeof window !== 'undefined') {
    window.LuminaLogger = {
        download: downloadLogs,
        downloadText: downloadLogsAsText,
        clear: clearLogs,
        stats: getLogStats,
        logs: getLogs,
        send: sendLogsToBackend,
    };
    console.info('[FileLogger] Logger controls available at window.LuminaLogger');
}
