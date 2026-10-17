import React, { useState } from 'react';
import { AlertTriangle, ExternalLink, Info } from 'lucide-react';
import type { ParameterAnalysisItem, ParameterGroup } from '../../api/types';

interface ParameterAnalysisProps {
  parameters: ParameterAnalysisItem[];
  groupingMethod: string;
  interpretationCaveat: string;
  minimumGroupSupport: number;
  onSelectExperiment: (experimentId: number) => void;
}

export const ParameterAnalysis: React.FC<ParameterAnalysisProps> = ({
  parameters,
  groupingMethod,
  interpretationCaveat,
  minimumGroupSupport,
  onSelectExperiment,
}) => {
  const [selectedParamName, setSelectedParamName] = useState<string>(
    parameters[0]?.name || ''
  );

  const selectedParam = parameters.find((p) => p.name === selectedParamName) || parameters[0];

  if (!selectedParam || parameters.length === 0) {
    return (
      <div className="surface-card rounded p-6 border border-[#35383C] text-center text-xs text-[#A6A8AB] font-mono">
        No parameter groupings generated for this batch.
      </div>
    );
  }

  const renderGroupLabel = (group: ParameterGroup) => {
    if (group.kind === 'numeric_range') {
      if (group.minimum === group.maximum) {
        return <span className="font-mono text-[#D5A35D] font-medium">{group.minimum}</span>;
      }
      return (
        <span className="font-mono text-[#D5A35D] font-medium">
          [{group.minimum} … {group.maximum}]
        </span>
      );
    }
    return (
      <span className="font-mono text-[#E8E5DC] font-medium">
        {String(group.value)}
      </span>
    );
  };

  const formatOutcomeMedian = (val: number | null | undefined) => {
    if (val === null || val === undefined || !Number.isFinite(val)) return '—';
    return Number(val).toFixed(2);
  };

  return (
    <div className="space-y-4">
      {/* Parameter Selection Toolbar */}
      <div className="flex flex-wrap items-center gap-2 pb-2">
        {parameters.map((p) => {
          const isSelected = p.name === selectedParam.name;
          return (
            <button
              key={p.name}
              onClick={() => setSelectedParamName(p.name)}
              className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors cursor-pointer border ${
                isSelected
                  ? 'bg-[#252219] text-[#D5A35D] border-[#D5A35D]/40 font-semibold shadow-xs'
                  : 'bg-[#16181C] text-[#A6A8AB] border-[#35383C] hover:text-[#E8E5DC] hover:border-[#D5A35D]/30'
              }`}
            >
              {p.name}
              <span className="ml-1.5 text-[10px] opacity-70">
                ({p.groups.length} grp{p.groups.length === 1 ? '' : 's'})
              </span>
            </button>
          );
        })}
      </div>

      {/* Selected Parameter Details & Table */}
      <div className="surface-card rounded border border-[#35383C] overflow-hidden shadow-sm">
        {/* Subheader */}
        <div className="p-4 border-b border-[#35383C] bg-[#16181C] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-[#E8E5DC] font-mono">
                {selectedParam.name}
              </h3>
              <div className="flex items-center gap-1">
                {selectedParam.parameter_types.map((t) => (
                  <span
                    key={t}
                    className="px-1.5 py-0.2 rounded text-[10px] font-mono uppercase bg-[#111317] text-[#A6A8AB] border border-[#35383C]"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
            <p className="text-[11px] font-mono text-[#A6A8AB] mt-1">
              {selectedParam.usable_value_count} usable runs partitioned into {selectedParam.groups.length} groups
              {selectedParam.missing_parameter_count > 0 && (
                <span className="text-[#D5A35D] ml-1.5">
                  ({selectedParam.missing_parameter_count} missing)
                </span>
              )}
            </p>
          </div>

          <div className="text-[11px] font-mono text-[#A6A8AB] bg-[#111317] px-2.5 py-1 rounded border border-[#35383C]">
            Min Support Threshold: <strong className="text-[#E8E5DC]">{minimumGroupSupport} runs</strong>
          </div>
        </div>

        {/* Groups Breakdown Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="table-header text-[#A6A8AB] text-[11px] uppercase tracking-wider select-none bg-[#16181C] border-b border-[#35383C]">
                <th className="py-2.5 px-4 font-semibold w-40">Group / Range</th>
                <th className="py-2.5 px-4 font-semibold w-24 text-right">Runs</th>
                <th className="py-2.5 px-4 font-semibold text-right">Median PF</th>
                <th className="py-2.5 px-4 font-semibold text-right">Median DD %</th>
                <th className="py-2.5 px-4 font-semibold text-right">Median Win Rate</th>
                <th className="py-2.5 px-4 font-semibold">Evidence Runs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#35383C]/60 bg-[#1D2024]">
              {selectedParam.groups.map((group, idx) => {
                const pf = group.outcomes?.profit_factor;
                const dd = group.outcomes?.equity_drawdown_pct;
                const wr = group.outcomes?.win_rate;

                return (
                  <tr key={idx} className="hover:bg-[#111317]/50 transition-colors">
                    <td className="py-2.5 px-4">
                      <div className="flex items-center gap-2">
                        {renderGroupLabel(group)}
                        {group.low_support && (
                          <span
                            className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] bg-[#252219] text-[#D5A35D] border border-[#D5A35D]/30"
                            title="Sample size is below the minimum support threshold (3 runs)"
                          >
                            <AlertTriangle className="w-2.5 h-2.5" />
                            Low Support
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-2.5 px-4 text-right text-[#E8E5DC] font-semibold">
                      {group.experiment_count}
                    </td>

                    <td className="py-2.5 px-4 text-right text-[#E8E5DC]">
                      {formatOutcomeMedian(pf?.median)}
                    </td>

                    <td className="py-2.5 px-4 text-right text-[#E8E5DC]">
                      {dd?.median !== null && dd?.median !== undefined ? `${formatOutcomeMedian(dd?.median)}%` : '—'}
                    </td>

                    <td className="py-2.5 px-4 text-right text-[#E8E5DC]">
                      {wr?.median !== null && wr?.median !== undefined ? `${formatOutcomeMedian(wr?.median)}%` : '—'}
                    </td>

                    <td className="py-2.5 px-4">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {group.evidence_experiment_ids?.slice(0, 5).map((id) => (
                          <button
                            key={id}
                            onClick={() => onSelectExperiment(id)}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-[#16181C] hover:bg-[#252219] text-[#D5A35D] border border-[#35383C] hover:border-[#D5A35D]/50 transition-colors cursor-pointer"
                            title={`Inspect experiment #${id}`}
                          >
                            <span>#{id}</span>
                            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                          </button>
                        ))}
                        {group.evidence_experiment_ids?.length > 5 && (
                          <span className="text-[10px] text-[#A6A8AB]">
                            +{group.evidence_experiment_ids.length - 5}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Unusable values notice if any */}
        {selectedParam.unusable_value_count > 0 && (
          <div className="p-3 bg-[#252219]/60 border-t border-[#D5A35D]/30 text-[11px] font-mono text-[#D5A35D] flex items-center justify-between">
            <span>
              {selectedParam.unusable_value_count} observations excluded due to missing, non-finite, or malformed parameter values.
            </span>
          </div>
        )}
      </div>

      {/* Methodological Caveat Box */}
      <div className="p-3.5 rounded bg-[#16181C] border border-[#35383C] flex items-start gap-2.5 text-xs text-[#A6A8AB] font-sans leading-relaxed">
        <Info className="w-4 h-4 text-[#D5A35D] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <strong className="text-[#E8E5DC] block font-mono text-[11px] uppercase tracking-wider">
            Association vs Causation Notice
          </strong>
          <p>{interpretationCaveat}</p>
          <p className="text-[11px] text-[#A6A8AB] font-mono">
            Partition method: {groupingMethod}
          </p>
        </div>
      </div>
    </div>
  );
};
