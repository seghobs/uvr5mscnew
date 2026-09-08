'use client';

import React, { useEffect, useState, useRef } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

const ToastItem: React.FC<{
  toast: ToastMessage;
  onDismiss: (id: string) => void;
}> = ({ toast, onDismiss }) => {
  const [isExiting, setIsExiting] = useState(false);
  const [paused, setPaused] = useState(false);
  const duration = toast.duration ?? (toast.type === 'error' ? 4500 : 3500);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (paused) return;

    timerRef.current = setTimeout(() => {
      handleClose();
    }, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [toast.id, duration, paused]);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      onDismiss(toast.id);
    }, 280);
  };

  const isSuccess = toast.type === 'success';
  const isError = toast.type === 'error';
  const isWarning = toast.type === 'warning';

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className={cn(
        'pointer-events-auto p-4 rounded-2xl border backdrop-blur-xl shadow-2xl flex items-start gap-3 transition-all duration-300 transform overflow-hidden relative group',
        isExiting
          ? 'opacity-0 translate-x-12 scale-95 pointer-events-none'
          : 'opacity-100 translate-x-0 scale-100',
        isSuccess && 'bg-emerald-950/95 border-emerald-500/40 text-emerald-200 shadow-emerald-950/40',
        isError && 'bg-rose-950/95 border-rose-500/40 text-rose-200 shadow-rose-950/40',
        isWarning && 'bg-amber-950/95 border-amber-500/40 text-amber-200 shadow-amber-950/40',
        !isSuccess && !isError && !isWarning && 'bg-slate-900/95 border-slate-700/60 text-slate-200 shadow-black/50'
      )}
    >
      <div className="mt-0.5 shrink-0">
        {isSuccess && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
        {isError && <XCircle className="w-5 h-5 text-rose-400" />}
        {isWarning && <AlertTriangle className="w-5 h-5 text-amber-400" />}
        {!isSuccess && !isError && !isWarning && <Info className="w-5 h-5 text-indigo-400" />}
      </div>

      <div className="flex-1 min-w-0">
        <h5 className="font-bold text-sm text-white truncate">{toast.title}</h5>
        {toast.message && (
          <p className="text-xs text-slate-300/90 mt-0.5 break-words line-clamp-3">{toast.message}</p>
        )}
      </div>

      <button
        onClick={handleClose}
        className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Auto-dismiss duration progress line */}
      <div
        className={cn(
          'absolute bottom-0 left-0 right-0 h-0.5 origin-left',
          isSuccess && 'bg-emerald-400/50',
          isError && 'bg-rose-400/50',
          isWarning && 'bg-amber-400/50',
          !isSuccess && !isError && !isWarning && 'bg-indigo-400/50'
        )}
        style={{
          animation: `toast-progress ${duration}ms linear forwards`,
          animationPlayState: paused ? 'paused' : 'running',
        }}
      />
    </div>
  );
};

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
};
