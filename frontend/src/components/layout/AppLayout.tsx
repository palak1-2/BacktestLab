import React from 'react';
import { Outlet } from 'react-router-dom';
import { AppHeader } from './AppHeader';
import { ShieldAlert } from 'lucide-react';

export const AppLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-[#111317] text-[#E8E5DC]">
      <AppHeader />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-7">
        <Outlet />
      </main>

      <footer className="border-t border-[#35383C] bg-[#16181C] py-4 text-xs text-[#A6A8AB] font-mono">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-[#A6A8AB]">
            <ShieldAlert className="w-3.5 h-3.5 text-[#D5A35D] shrink-0" />
            <span>
              Quantitative Research Studio. For strategy evaluation and post-mortem analysis. Not financial advice.
            </span>
          </div>
          <div className="text-[11px] text-[#A6A8AB]/80">
            Local-First MetaTrader 5 Research Lab • Deterministic Evaluation Engine
          </div>
        </div>
      </footer>
    </div>
  );
};
