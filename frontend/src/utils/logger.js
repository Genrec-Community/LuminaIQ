/**
 * Frontend Console Logger
 *
 * Centralized logging utility for the LuminaIQ frontend.
 * Mirrors the backend logging philosophy using native browser console methods.
 *
 * Usage:
 *   import { createLogger } from '../utils/logger';
 *   const logger = createLogger('MyComponent');
 *   logger.info('User logged in', { userId: '123' });
 *
 * Output in browser console:
 *   [LuminaIQ:MyComponent] 2026-04-04T13:39:26.123Z INFO — User logged in {userId: '123'}
 *
 * Log levels (ascending severity): DEBUG < INFO < WARN < ERROR
 * In development: all levels are emitted.
 * In production: only WARN and ERROR are emitted.
 */

/**
 * Numeric values for log level comparison.
 * Higher value = higher severity.
 */
const LOG_LEVELS = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3,
};

/**
 * Minimum log level threshold.
 * In production builds, suppress DEBUG and INFO to keep the console clean
 * for end users while preserving warnings and errors for diagnostics.
 */
const CURRENT_LOG_LEVEL =
    import.meta.env.MODE === 'production' ? LOG_LEVELS.WARN : LOG_LEVELS.DEBUG;

/**
 * Format a log prefix string with module name, timestamp, and level.
 *
 * @param {string} moduleName - The module or component name
 * @param {string} level - The log level label (DEBUG, INFO, WARN, ERROR)
 * @returns {string} Formatted prefix
 */
const formatPrefix = (moduleName, level) => {
    const timestamp = new Date().toISOString();
    return `[LuminaIQ:${moduleName}] ${timestamp} ${level} —`;
};

/**
 * Create a scoped logger instance for a specific module or component.
 *
 * Each logger instance uses the module name as a prefix so that log
 * messages can be easily filtered in the browser DevTools console
 * (e.g., filter by "LuminaIQ:AuthContext").
 *
 * @param {string} moduleName - A short, descriptive name identifying the
 *   module, component, or context that owns the logger. Convention:
 *   PascalCase matching the source file name (e.g., 'AuthContext', 'API').
 * @returns {{ debug: Function, info: Function, warn: Function, error: Function }}
 */
export const createLogger = (moduleName) => {
    if (!moduleName || typeof moduleName !== 'string') {
        throw new Error('createLogger requires a non-empty string moduleName');
    }

    return {
        /**
         * Log detailed diagnostic information.
         * Visible only in development builds.
         *
         * @param {string} message - Human-readable log message
         * @param {...*} args - Optional structured context (objects, arrays, etc.)
         */
        debug(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.DEBUG) return;
            console.debug(formatPrefix(moduleName, 'DEBUG'), message, ...args);
        },

        /**
         * Log normal system behavior and key lifecycle events.
         * Visible only in development builds.
         *
         * @param {string} message - Human-readable log message
         * @param {...*} args - Optional structured context
         */
        info(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.INFO) return;
            console.info(formatPrefix(moduleName, 'INFO'), message, ...args);
        },

        /**
         * Log unexpected conditions that do not prevent operation
         * but may indicate a problem.
         * Visible in all environments.
         *
         * @param {string} message - Human-readable log message
         * @param {...*} args - Optional structured context
         */
        warn(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.WARN) return;
            console.warn(formatPrefix(moduleName, 'WARN'), message, ...args);
        },

        /**
         * Log failures that require attention and may impact users.
         * Visible in all environments.
         *
         * @param {string} message - Human-readable log message
         * @param {...*} args - Optional structured context (error objects, etc.)
         */
        error(message, ...args) {
            if (CURRENT_LOG_LEVEL > LOG_LEVELS.ERROR) return;
            console.error(formatPrefix(moduleName, 'ERROR'), message, ...args);
        },
    };
};
