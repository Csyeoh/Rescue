"use client";

import React, { useState, createContext, useContext, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Info, AlertCircle, CheckCircle, X } from 'lucide-react';

type ToastType = 'info' | 'success' | 'warning' | 'error';

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-8 right-8 z-[9999] flex flex-col gap-3 pointer-events-none">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.9, x: 20 }}
              animate={{ opacity: 1, y: 0, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.9, x: 20 }}
              transition={{ duration: 0.3, ease: "circOut" }}
              className={`pointer-events-auto flex items-center gap-4 px-6 py-4 rounded-2xl shadow-2xl border min-w-[320px] max-w-md ${
                toast.type === 'success' ? 'bg-white border-emerald-100 text-emerald-900' :
                toast.type === 'error' ? 'bg-white border-alert-red/20 text-alert-red' :
                toast.type === 'warning' ? 'bg-white border-alert-yellow/50 text-alert-orange' :
                'bg-neutral-dark border-white/10 text-white'
              }`}
            >
              <div className={`shrink-0 p-2 rounded-xl ${
                toast.type === 'success' ? 'bg-emerald-50 text-emerald-600' :
                toast.type === 'error' ? 'bg-alert-red/10 text-alert-red' :
                toast.type === 'warning' ? 'bg-alert-yellow/10 text-alert-orange' :
                'bg-white/5 text-azure-light'
              }`}>
                {toast.type === 'success' && <CheckCircle size={18} />}
                {toast.type === 'error' && <AlertCircle size={18} />}
                {toast.type === 'warning' && <AlertCircle size={18} />}
                {toast.type === 'info' && <Info size={18} />}
              </div>
              <p className="flex-1 text-sm font-semibold tracking-tight leading-snug">{toast.message}</p>
              <button 
                onClick={() => removeToast(toast.id)}
                className="shrink-0 opacity-30 hover:opacity-100 transition-opacity p-1"
              >
                <X size={16} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
};

