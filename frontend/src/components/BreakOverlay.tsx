import React from 'react';
import type { SystemAlert } from '../hooks/useTuringSocket';

interface BreakOverlayProps {
  systemAlert: SystemAlert;
}

const BreakOverlay: React.FC<BreakOverlayProps> = ({ systemAlert }) => {
  if (systemAlert.action !== 'TAKE_BREAK') return null;

  return (
    <div className="fixed inset-0 z-[9999] bg-slate-900/95 backdrop-blur-md flex items-center justify-center text-center p-8">
      <div className="max-w-md w-full bg-white rounded-3xl p-10 shadow-2xl space-y-8 animate-in fade-in zoom-in duration-300">
        <div className="w-24 h-24 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-12 w-12"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <div className="space-y-4">
          <h2 className="text-3xl font-black text-slate-800">Brain Break Time!</h2>
          <p className="text-slate-600 text-lg leading-relaxed">
            {systemAlert.reason || "You've been working hard. Let's step away for a moment to recharge."}
          </p>
        </div>
        <div className="bg-slate-50 rounded-2xl p-6">
          <span className="block text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">
            Duration
          </span>
          <span className="text-4xl font-black text-blue-600">
            {systemAlert.duration_minutes || 15} Minutes
          </span>
        </div>
        <p className="text-xs text-slate-400 font-medium">
          The screen will unlock automatically when the timer expires.
        </p>
      </div>
    </div>
  );
};

export default BreakOverlay;
