import React from 'react';
import { ChevronRight } from 'lucide-react';
import type { ExperimentSummarySchema } from '../../api/types';
import { EvaluationBadge, ExperimentTypeBadge } from '../common/Badge';

interface ExperimentTableProps {
  experiments: ExperimentSummarySchema[];
  onSelectExperiment: (experimentId: number) => void;
  selectedExperimentId?: number | null;
  isLoading?: boolean;
}

export const ExperimentTable: React.FC<ExperimentTableProps> = ({
  experiments,
  onSelectExperiment,
  selectedExperimentId,
}) => {
  return (
    <div className="bg-[#1D2024] rounded-lg border border-[#35383C] overflow-hidden shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-[#16181C] border-b border-[#35383C] text-[#A6A8AB] font-mono text-[11px] uppercase tracking-wider select-none">
              <th className="py-2.5 px-3 font-semibold w-16">ID</th>
              <th className="py-2.5 px-3 font-semibold w-20">Pass #</th>
              <th className="py-2.5 px-3 font-semibold">Strategy & Version</th>
              <th className="py-2.5 px-3 font-semibold w-24">Symbol</th>
              <th className="py-2.5 px-3 font-semibold w-24">Timeframe</th>
              <th className="py-2.5 px-3 font-semibold w-28">Type</th>
              <th className="py-2.5 px-3 font-semibold w-36">Evaluation</th>
              <th className="py-2.5 px-3 font-semibold w-36">Created</th>
              <th className="py-2.5 px-3 font-semibold w-12 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#35383C]/60 font-mono">
            {experiments.map((exp) => {
              const isSelected = selectedExperimentId === exp.id;
              const formattedDate = new Date(exp.created_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              });

              return (
                <tr
                  key={exp.id}
                  onClick={() => onSelectExperiment(exp.id)}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-[#D5A35D]/10 border-l-2 border-l-[#D5A35D]'
                      : 'hover:bg-[#23272D]'
                  }`}
                >
                  <td className="py-2.5 px-3 text-[#A6A8AB] font-medium">
                    #{exp.id}
                  </td>

                  <td className="py-2.5 px-3 text-[#E8E5DC]">
                    {exp.optimization_pass !== null ? (
                      <span className="font-semibold text-[#D5A35D]">
                        {exp.optimization_pass}
                      </span>
                    ) : (
                      <span className="text-[#A6A8AB]/60">—</span>
                    )}
                  </td>

                  <td className="py-2.5 px-3 font-sans">
                    <div className="font-medium text-[#E8E5DC] truncate max-w-xs" title={exp.strategy_name || ''}>
                      {exp.strategy_name || <span className="text-[#A6A8AB] font-mono text-xs">Unnamed</span>}
                    </div>
                    {exp.strategy_version && (
                      <span className="text-[10px] font-mono text-[#A6A8AB]">
                        v{exp.strategy_version}
                      </span>
                    )}
                  </td>

                  <td className="py-2.5 px-3 text-[#E8E5DC] font-semibold">
                    {exp.symbol || <span className="text-[#A6A8AB]/60">—</span>}
                  </td>

                  <td className="py-2.5 px-3 text-[#E8E5DC]">
                    {exp.timeframe ? (
                      <span className="px-1.5 py-0.5 rounded bg-[#16181C] border border-[#35383C] text-[11px]">
                        {exp.timeframe}
                      </span>
                    ) : (
                      <span className="text-[#A6A8AB]/60">—</span>
                    )}
                  </td>

                  <td className="py-2.5 px-3">
                    <ExperimentTypeBadge type={exp.experiment_type} />
                  </td>

                  <td className="py-2.5 px-3">
                    <EvaluationBadge status={exp.evaluation_status} size="sm" />
                  </td>

                  <td className="py-2.5 px-3 text-[#A6A8AB] text-[11px] whitespace-nowrap">
                    {formattedDate}
                  </td>

                  <td className="py-2.5 px-3 text-right">
                    <button
                      className="p-1 text-[#A6A8AB] hover:text-[#D5A35D] transition-colors"
                      title="Inspect Experiment"
                      aria-label="Inspect Experiment"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
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
