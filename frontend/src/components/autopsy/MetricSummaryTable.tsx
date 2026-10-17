import React from 'react';
import type { MetricDistribution } from '../../api/types';

interface MetricSummaryTableProps {
  metrics: Record<string, MetricDistribution>;
  totalExperiments: number;
}

export const MetricSummaryTable: React.FC<MetricSummaryTableProps> = ({
  metrics,
  totalExperiments,
}) => {
  const metricEntries = Object.entries(metrics).sort(([a], [b]) => a.localeCompare(b));

  if (metricEntries.length === 0) {
    return (
      <div className="surface-card rounded-lg p-6 border border-slate-800 text-center text-xs text-slate-400 font-mono">
        No metric summary data recorded for this batch.
      </div>
    );
  }

  const formatNum = (val: number | null) => {
    if (val === null || val === undefined || !Number.isFinite(val)) return '—';
    return Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 3,
    });
  };

  return (
    <div className="bg-[#1D2024] rounded-lg border border-[#35383C] overflow-hidden shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs font-mono">
          <thead>
            <tr className="bg-[#16181C] border-b border-[#35383C] text-[#A6A8AB] text-[11px] uppercase tracking-wider select-none">
              <th className="py-2.5 px-4 font-semibold">Metric</th>
              <th className="py-2.5 px-4 font-semibold text-center w-36">Coverage</th>
              <th className="py-2.5 px-4 font-semibold text-right w-28">Min</th>
              <th className="py-2.5 px-4 font-semibold text-right w-28">Median</th>
              <th className="py-2.5 px-4 font-semibold text-right w-28">Max</th>
              <th className="py-2.5 px-4 font-semibold w-48 text-center hidden lg:table-cell">
                Spread Range
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#35383C]/60">
            {metricEntries.map(([name, dist]) => {
              const coveragePct = totalExperiments
                ? ((dist.available_count / totalExperiments) * 100).toFixed(0)
                : '0';

              const isComplete = dist.missing_count === 0;

              // Compute median position in [min, max] range for bar
              let medianPos = 50;
              if (
                dist.min !== null &&
                dist.max !== null &&
                dist.median !== null &&
                dist.max > dist.min
              ) {
                medianPos = Math.max(
                  5,
                  Math.min(95, ((dist.median - dist.min) / (dist.max - dist.min)) * 100)
                );
              }

              return (
                <tr key={name} className="hover:bg-[#23272D] transition-colors">
                  <td className="py-2.5 px-4 font-medium text-[#E8E5DC]">
                    {name}
                  </td>

                  <td className="py-2.5 px-4 text-center">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] ${
                        isComplete
                          ? 'bg-[#16181C] text-[#E8E5DC] border border-[#35383C]'
                          : 'bg-[#D5A35D]/15 text-[#D5A35D] border border-[#D5A35D]/30'
                      }`}
                    >
                      {dist.available_count}/{totalExperiments} ({coveragePct}%)
                    </span>
                  </td>

                  <td className="py-2.5 px-4 text-right text-[#A6A8AB]">
                    {formatNum(dist.min)}
                  </td>

                  <td className="py-2.5 px-4 text-right text-[#D5A35D] font-semibold">
                    {formatNum(dist.median)}
                  </td>

                  <td className="py-2.5 px-4 text-right text-[#A6A8AB]">
                    {formatNum(dist.max)}
                  </td>

                  <td className="py-2.5 px-4 hidden lg:table-cell">
                    {dist.min !== null && dist.max !== null && dist.max > dist.min ? (
                      <div className="relative w-full h-1.5 bg-[#16181C] rounded-full my-auto border border-[#35383C]/40">
                        {/* Range track */}
                        <div className="absolute inset-0 bg-[#35383C]/80 rounded-full" />
                        {/* Median marker */}
                        <div
                          style={{ left: `${medianPos}%` }}
                          className="absolute -top-1 w-2 h-3.5 bg-[#D5A35D] rounded-xs -translate-x-1/2 shadow-xs"
                          title={`Median: ${formatNum(dist.median)}`}
                        />
                      </div>
                    ) : (
                      <span className="text-[#A6A8AB]/60 block text-center">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
