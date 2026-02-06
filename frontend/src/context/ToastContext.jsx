import React, { createContext, useContext, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

const TOAST_TYPES = {
    success: {
        icon: CheckCircle,
        bgColor: 'bg-green-50',
        borderColor: 'border-green-200',
        iconColor: 'text-green-500',
        textColor: 'text-green-800'
    },
    error: {
        icon: AlertCircle,
        bgColor: 'bg-red-50',
        borderColor: 'border-red-200',
        iconColor: 'text-red-500',
        textColor: 'text-red-800'
    },
    warning: {
        icon: AlertTriangle,
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-200',
        iconColor: 'text-amber-500',
        textColor: 'text-amber-800'
    },
    info: {
        icon: Info,
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        iconColor: 'text-blue-500',
        textColor: 'text-blue-800'
    }
};

export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback((message, type = 'info', duration = 4000) => {
        const id = Date.now() + Math.random();
        setToasts(prev => [...prev, { id, message, type }]);

        if (duration > 0) {
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== id));
            }, duration);
        }

        return id;
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    // Convenience methods
    const toast = {
        success: (message, duration) => addToast(message, 'success', duration),
        error: (message, duration) => addToast(message, 'error', duration),
        warning: (message, duration) => addToast(message, 'warning', duration),
        info: (message, duration) => addToast(message, 'info', duration),
        dismiss: removeToast
    };

    return (
        <ToastContext.Provider value={toast}>
            {children}
            
            {/* Toast Container */}
            <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
                <AnimatePresence mode="popLayout">
                    {toasts.map(t => {
                        const config = TOAST_TYPES[t.type] || TOAST_TYPES.info;
                        const Icon = config.icon;
                        
                        return (
                            <motion.div
                                key={t.id}
                                layout
                                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, x: 100, scale: 0.95 }}
                                transition={{ duration: 0.2 }}
                                className={`flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg ${config.bgColor} ${config.borderColor}`}
                            >
                                <Icon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.iconColor}`} />
                                <p className={`text-sm font-medium flex-1 ${config.textColor}`}>
                                    {t.message}
                                </p>
                                <button
                                    onClick={() => removeToast(t.id)}
                                    className={`p-0.5 hover:bg-black/5 rounded-full transition-colors ${config.iconColor}`}
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            </motion.div>
                        );
                    })}
                </AnimatePresence>
            </div>
        </ToastContext.Provider>
    );
};

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};

export default ToastContext;
