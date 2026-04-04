import React from 'react';
import { createLogger } from '../utils/logger';

const logger = createLogger('ErrorBoundary');

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        // Update state so the next render will show the fallback UI.
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        // You can also log the error to an error reporting service
        logger.error("ErrorBoundary caught an error:", error, errorInfo);
        this.setState({
            error: error,
            errorInfo: errorInfo
        });
    }

    render() {
        if (this.state.hasError) {
            // You can render any custom fallback UI
            return (
                <div className="flex flex-col items-center justify-center p-8 bg-red-50 text-red-800 rounded-xl border border-red-200">
                    <h2 className="text-lg font-bold mb-2">Something went wrong.</h2>
                    <p className="text-sm mb-4">An error occurred while rendering this component.</p>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
                    >
                        Try again
                    </button>
                    {this.state.error && (
                        <details className="mt-4 text-xs bg-white p-3 rounded shadow-inner whitespace-pre-wrap text-left w-full overflow-auto max-h-64">
                            <summary className="cursor-pointer font-semibold mb-2">Error Details</summary>
                            {this.state.error.toString()}
                            <br />
                            {this.state.errorInfo.componentStack}
                        </details>
                    )}
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
