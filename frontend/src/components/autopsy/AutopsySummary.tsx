import React from 'react';
import type { ResearchAutopsyResponse } from '../../api/types';
import { CheckCircle2, XCircle, AlertTriangle, Clock } from 'lucide-react';

interface AutopsySummaryProps {
  autopsy: ResearchAutopsyResponse;
}

export const AutopsySummary: React.FC<AutopsySummaryProps> = ({ autopsy }) => {
  const { status_counts, total_experiments } = autopsy;

  const qualifiedPct = total_experiments ? ((status_counts.qualified / total_experiments) * 100).toFixed(1) : '0';
  const rejectedPct = total_experiments ? ((status_counts.rejected / total_experiments) * 100).toFixed(1) : '0';
  const incompletePct = total_experiments ? ((status_counts.incomplete / total_experiments) * 100).toFixed(1) : '0';
  const pendingPct = total_experiments ? ((status_counts.pending / total_experiments) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-4">
      {/* 4 Status Breakdown Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        {/* Qualified */}
        <div className="bg-[#1D2024] rounded-lg p-4 border border-emerald-800/40 bg-emerald-950/15 flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between text-xs font-mono text-emerald-400">
            <span className="flex items-center gap-1.5 uppercase font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Qualified
            </span>
            <span>{qualifiedPct}%</span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-mono font-bold text-emerald-300">
              {status_counts.qualified.toLocaleString()}
            </span>
            <span className="text-[11px] font-mono text-emerald-500/80 ml-2">
              of {total_experiments}
            </span>
          </div>
        </div>

        {/* Rejected */}
        <div className="bg-[#1D2024] rounded-lg p-4 border border-rose-800/40 bg-rose-950/15 flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between text-xs font-mono text-rose-400">
            <span className="flex items-center gap-1.5 uppercase font-semibold">
              <XCircle className="w-3.5 h-3.5" />
              Rejected
            </span>
            <span>{rejectedPct}%</span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-mono font-bold text-rose-300">
              {status_counts.rejected.toLocaleString()}
            </span>
            <span className="text-[11px] font-mono text-rose-500/80 ml-2">
              of {total_experiments}
            </span>
          </div>
        </div>

        {/* Incomplete / Insufficient Data */}
        <div className="bg-[#1D2024] rounded-lg p-4 border border-[#D5A35D]/30 bg-[#252219]/60 flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between text-xs font-mono text-[#D5A35D]">
            <span className="flex items-center gap-1.5 uppercase font-semibold">
              <AlertTriangle className="w-3.5 h-3.5" />
              Incomplete Data
            </span>
            <span>{incompletePct}%</span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-mono font-bold text-[#D5A35D]">
              {status_counts.incomplete.toLocaleString()}
            </span>
            <span className="text-[11px] font-mono text-[#D5A35D]/70 ml-2">
              of {total_experiments}
            </span>
          </div>
        </div>

        {/* Pending */}
        <div className="bg-[#1D2024] rounded-lg p-4 border border-[#35383C] bg-[#16181C] flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between text-xs font-mono text-[#A6A8AB]">
            <span className="flex items-center gap-1.5 uppercase font-semibold">
              <Clock className="w-3.5 h-3.5" />
              Pending
            </span>
            <span>{pendingPct}%</span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-mono font-bold text-[#E8E5DC]">
              {status_counts.pending.toLocaleString()}
            </span>
            <span className="text-[11px] font-mono text-[#A6A8AB] ml-2">
              of {total_experiments}
            </span>
          </div>
        </div>
      </div>

      {/* Visual Stacked Distribution Bar */}
      {total_experiments > 0 && (
        <div className="bg-[#1D2024] rounded-lg p-4 border border-[#35383C] space-y-2.5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-mono text-[#A6A8AB]">
            <span className="text-[#E8E5DC] font-medium">Deterministic Qualification Outcome Distribution</span>
            <span>{total_experiments.toLocaleString()} Total Passes</span>
          </div>
          <div className="w-full h-2.5 rounded-full overflow-hidden flex bg-[#16181C] border border-[#35383C]/60">
            {status_counts.qualified > 0 && (
              <div
                style={{ width: `${qualifiedPct}%` }}
                className="bg-emerald-400 transition-all"
                title={`Qualified: ${status_counts.qualified} (${qualifiedPct}%)`}
              />
            )}
            {status_counts.rejected > 0 && (
              <div
                style={{ width: `${rejectedPct}%` }}
                className="bg-rose-500 transition-all"
                title={`Rejected: ${status_counts.rejected} (${rejectedPct}%)`}
              />
            )}
            {status_counts.incomplete > 0 && (
              <div
                style={{ width: `${incompletePct}%` }}
                className="bg-[#D5A35D] transition-all"
                title={`Incomplete: ${status_counts.incomplete} (${incompletePct}%)`}
              />
            )}
            {status_counts.pending > 0 && (
              <div
                style={{ width: `${pendingPct}%` }}
                className="bg-[#35383C] transition-all"
                title={`Pending: ${status_counts.pending} (${pendingPct}%)`}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};
