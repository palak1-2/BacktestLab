import React from 'react';
import { Database, ExternalLink } from 'lucide-react';
import type { AutopsyFinding } from '../../api/types';

interface FindingsListProps {
  findings: AutopsyFinding[];
  onSelectExperiment: (experimentId: number) => void;
}

export const FindingsList: React.FC<FindingsListProps> = ({
  findings,
  onSelectExperiment,
}) => {
  if (findings.length === 0) {
    return (
      <div className="surface-card rounded-lg p-6 border border-slate-800 text-center text-xs text-slate-400 font-mono">
        No deterministic failure patterns or data gaps identified for this batch.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {findings.map((f) => {
        const isDataGap = f.kind === 'data_gap';

        return (
          <div
            key={f.finding_id}
            className={`rounded-lg p-5 border transition-all shadow-xs ${
              isDataGap
                ? 'border-[#D5A35D]/30 bg-[#252219]/40'
                : 'border-rose-800/40 bg-rose-950/15'
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
              <div className="space-y-2 flex-1 min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="font-mono text-xs font-bold text-[#E8E5DC] px-2 py-0.5 rounded bg-[#16181C] border border-[#35383C]">
                    {f.finding_id}
                  </span>

                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${
                      isDataGap
                        ? 'bg-[#D5A35D]/15 text-[#D5A35D] border-[#D5A35D]/30'
                        : 'bg-rose-950/40 text-rose-300 border-rose-800/60'
                    }`}
                  >
                    {isDataGap ? 'Data Gap' : 'Failure Pattern'}
                  </span>

                  <h4 className="text-base font-medium text-[#E8E5DC]">{f.title}</h4>
                </div>

                <p className="text-xs text-[#E8E5DC]/80 leading-relaxed font-sans">{f.description}</p>

                {f.operator && f.threshold !== undefined && (
                  <div className="text-[11px] font-mono text-[#A6A8AB]">
                    Rule Criterion: <strong className="text-[#E8E5DC]">{f.metric} {f.operator} {f.threshold}</strong>
                  </div>
                )}
              </div>

              {/* Counts Badge */}
              <div className="shrink-0 text-right font-mono">
                <div
                  className={`text-base font-bold ${
                    isDataGap ? 'text-[#D5A35D]' : 'text-rose-400'
                  }`}
                >
                  {f.count.toLocaleString()} runs
                </div>
                <div className="text-[11px] text-[#A6A8AB]">
                  {f.percentage_of_all}% of batch
                </div>
              </div>
            </div>

            {/* Clickable Evidence Experiment IDs */}
            {f.evidence_experiment_ids && f.evidence_experiment_ids.length > 0 && (
              <div className="mt-4 pt-3 border-t border-[#35383C]/60 flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-mono text-[#A6A8AB] flex items-center gap-1 shrink-0">
                  <Database className="w-3 h-3 text-[#A6A8AB]" />
                  Evidence Runs:
                </span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {f.evidence_experiment_ids.map((id) => (
                    <button
                      key={id}
                      onClick={() => onSelectExperiment(id)}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-[#16181C] hover:bg-[#25292F] text-[#D5A35D] border border-[#35383C] hover:border-[#D5A35D]/50 transition-colors cursor-pointer group"
                      title={`Inspect experiment #${id}`}
                    >
                      <span>#{id}</span>
                      <ExternalLink className="w-2.5 h-2.5 opacity-60 group-hover:opacity-100" />
                    </button>
                  ))}
                  {f.evidence_count > f.evidence_experiment_ids.length && (
                    <span className="text-[11px] font-mono text-[#A6A8AB]">
                      +{f.evidence_count - f.evidence_experiment_ids.length} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
