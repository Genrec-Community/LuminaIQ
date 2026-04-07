import React, { useState, useEffect } from 'react';
import { Download, Trash2, X, FileText, AlertCircle, Info, AlertTriangle, XCircle, Filter } from 'lucide-react';
import { getLogs, clearLogs, downloadLogs, downloadLogsAsText, getLogStats } from '../utils/fileLogger';

/**
 * Development Log Viewer Component
 * 
 * Provides a UI to view, filter, and download frontend logs in development mode.
 * Only rendered when in development mode.
 */
const DevLogViewer = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [logs, setLogs] = useState([]);
    const [stats, setStats] = useState(null);
    const [filterLevel, setFilterLevel] = useState('ALL');
    const [filterModule, setFilterModule] = useState('ALL');
    const [searchTerm, setSearchTerm] = useState('');

    // Only render in development mode
    if (import.meta.env.MODE !== 'development') {
        return null;
    }

    const refreshLogs = () => {
        setLogs(getLogs());
        setStats(getLogStats());
    };

    useEffect(() => {
        if (isOpen) {
            refreshLogs();
            // Auto-refresh every 2 seconds when open
            const interval = setInterval(refreshLogs, 2000);
            return () => clearInterval(interval);
        }
    }, [isOpen]);

    const handleClearLogs = () => {
        if (confirm('Are you sure you want to clear all logs?')) {
            clearLogs();
            refreshLogs();
        }
    };

    const handleDownloadJSON = () => {
        downloadLogs();
    };

    const handleDownloadText = () => {
        downloadLogsAsText();
    };

    const getLevelIcon = (level) => {
        switch (level) {
            case 'DEBUG':
                return <Info className="h-4 w-4 text-blue-500" />;
            case 'INFO':
                return <Info className="h-4 w-4 text-green-500" />;
            case 'WARN':
                return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
            case 'ERROR':
                return <XCircle className="h-4 w-4 text-red-500" />;
            default:
                return <AlertCircle className="h-4 w-4 text-gray-500" />;
        }
    };

    const getLevelColor = (level) => {
        switch (level) {
            case 'DEBUG':
                return 'bg-blue-50 text-blue-700 border-blue-200';
            case 'INFO':
                return 'bg-green-50 text-green-700 border-green-200';
            case 'WARN':
                return 'bg-yellow-50 text-yellow-700 border-yellow-200';
            case 'ERROR':
                return 'bg-red-50 text-red-700 border-red-200';
            default:
                return 'bg-gray-50 text-gray-700 border-gray-200';
        }
    };

    const filteredLogs = logs.filter(log => {
        const levelMatch = filterLevel === 'ALL' || log.level === filterLevel;
        const moduleMatch = filterModule === 'ALL' || log.module === filterModule;
        const searchMatch = searchTerm === '' || 
            log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
            log.module.toLowerCase().includes(searchTerm.toLowerCase());
        return levelMatch && moduleMatch && searchMatch;
    });

    const uniqueModules = stats ? Object.keys(stats.byModule).sort() : [];

    return (
        <>
            {/* Floating Button */}
            <button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-4 right-4 z-50 p-3 bg-purple-600 text-white rounded-full shadow-lg hover:bg-purple-700 transition-colors"
                title="Open Dev Logs"
            >
                <FileText className="h-5 w-5" />
            </button>

            {/* Log Viewer Modal */}
            {isOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between p-4 border-b border-gray-200">
                            <div className="flex items-center gap-3">
                                <div className="h-10 w-10 bg-purple-100 rounded-lg flex items-center justify-center">
                                    <FileText className="h-5 w-5 text-purple-600" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-bold text-gray-900">Development Logs</h2>
                                    <p className="text-xs text-gray-500">
                                        {stats && `${stats.total} entries • ${Object.keys(stats.byModule).length} modules`}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleDownloadJSON}
                                    className="px-3 py-2 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors flex items-center gap-2"
                                    title="Download as JSON"
                                >
                                    <Download className="h-4 w-4" />
                                    JSON
                                </button>
                                <button
                                    onClick={handleDownloadText}
                                    className="px-3 py-2 text-sm bg-green-50 text-green-600 rounded-lg hover:bg-green-100 transition-colors flex items-center gap-2"
                                    title="Download as Text"
                                >
                                    <Download className="h-4 w-4" />
                                    TXT
                                </button>
                                <button
                                    onClick={handleClearLogs}
                                    className="px-3 py-2 text-sm bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition-colors flex items-center gap-2"
                                    title="Clear All Logs"
                                >
                                    <Trash2 className="h-4 w-4" />
                                    Clear
                                </button>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                                >
                                    <X className="h-5 w-5 text-gray-500" />
                                </button>
                            </div>
                        </div>

                        {/* Filters */}
                        <div className="p-4 border-b border-gray-200 bg-gray-50">
                            <div className="flex flex-wrap gap-3">
                                <div className="flex items-center gap-2">
                                    <Filter className="h-4 w-4 text-gray-500" />
                                    <span className="text-sm font-medium text-gray-700">Filters:</span>
                                </div>
                                <select
                                    value={filterLevel}
                                    onChange={(e) => setFilterLevel(e.target.value)}
                                    className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                                >
                                    <option value="ALL">All Levels</option>
                                    <option value="DEBUG">Debug</option>
                                    <option value="INFO">Info</option>
                                    <option value="WARN">Warn</option>
                                    <option value="ERROR">Error</option>
                                </select>
                                <select
                                    value={filterModule}
                                    onChange={(e) => setFilterModule(e.target.value)}
                                    className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                                >
                                    <option value="ALL">All Modules</option>
                                    {uniqueModules.map(module => (
                                        <option key={module} value={module}>{module}</option>
                                    ))}
                                </select>
                                <input
                                    type="text"
                                    placeholder="Search logs..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 outline-none"
                                />
                            </div>
                        </div>

                        {/* Stats Bar */}
                        {stats && (
                            <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex gap-4 text-xs">
                                <div className="flex items-center gap-1">
                                    <span className="font-semibold text-blue-600">{stats.byLevel.DEBUG || 0}</span>
                                    <span className="text-gray-600">Debug</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <span className="font-semibold text-green-600">{stats.byLevel.INFO || 0}</span>
                                    <span className="text-gray-600">Info</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <span className="font-semibold text-yellow-600">{stats.byLevel.WARN || 0}</span>
                                    <span className="text-gray-600">Warn</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <span className="font-semibold text-red-600">{stats.byLevel.ERROR || 0}</span>
                                    <span className="text-gray-600">Error</span>
                                </div>
                            </div>
                        )}

                        {/* Log Entries */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs">
                            {filteredLogs.length === 0 ? (
                                <div className="text-center py-12 text-gray-500">
                                    <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
                                    <p>No logs to display</p>
                                </div>
                            ) : (
                                filteredLogs.map((log, index) => (
                                    <div
                                        key={index}
                                        className={`p-3 rounded-lg border ${getLevelColor(log.level)}`}
                                    >
                                        <div className="flex items-start gap-2">
                                            {getLevelIcon(log.level)}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="font-semibold">{log.module}</span>
                                                    <span className="text-gray-500">•</span>
                                                    <span className="text-gray-500">
                                                        {new Date(log.timestamp).toLocaleTimeString()}
                                                    </span>
                                                </div>
                                                <div className="mb-1">{log.message}</div>
                                                {log.data && (
                                                    <details className="mt-2">
                                                        <summary className="cursor-pointer text-gray-600 hover:text-gray-800">
                                                            View data
                                                        </summary>
                                                        <pre className="mt-2 p-2 bg-white/50 rounded overflow-x-auto">
                                                            {JSON.stringify(log.data, null, 2)}
                                                        </pre>
                                                    </details>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default DevLogViewer;
