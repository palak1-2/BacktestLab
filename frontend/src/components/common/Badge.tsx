import React from 'react';
import type { EvaluationStatus, ExperimentType, RuleOutcomeStatus, SourceFormat } from '../../api/types';

interface EvaluationBadgeProps {
  status: EvaluationStatus | null | undefined;
  size?: 'sm' | 'md';
}

export const EvaluationBadge: React.FC<EvaluationBadgeProps> = ({ status, size = 'sm' }) => {
  if (!status) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-slate-900/60 text-slate-400 border border-slate-800">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
        UNRATED
      </span>
    );
  }

  const configs: Record<EvaluationStatus, { label: string; bg: string; text: string; border: string; dot: string }> = {
    QUALIFIED: {
      label: 'QUALIFIED',
      bg: 'bg-emerald-950/30',
      text: 'text-emerald-400',
      border: 'border-emerald-800/60',
      dot: 'bg-emerald-400',
    },
    REJECTED: {
      label: 'REJECTED',
      bg: 'bg-rose-950/30',
      text: 'text-rose-400',
      border: 'border-rose-800/60',
      dot: 'bg-rose-400',
    },
    INSUFFICIENT_DATA: {
      label: 'INSUFFICIENT DATA',
      bg: 'bg-[#D5A35D]/15',
      text: 'text-[#D5A35D]',
      border: 'border-[#D5A35D]/40',
      dot: 'bg-[#D5A35D]',
    },
    PENDING: {
      label: 'PENDING',
      bg: 'bg-[#1D2024]',
      text: 'text-[#A6A8AB]',
      border: 'border-[#35383C]',
      dot: 'bg-[#A6A8AB]',
    },
  };

  const c = configs[status] || configs.PENDING;
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs tracking-wider';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded font-mono font-medium border ${c.bg} ${c.text} ${c.border} ${padding}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
};

export const RuleOutcomeBadge: React.FC<{ status: RuleOutcomeStatus }> = ({ status }) => {
  if (status === 'PASS') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-emerald-950/30 text-emerald-400 border border-emerald-800/60">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        PASS
      </span>
    );
  }
  if (status === 'FAIL') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-rose-950/30 text-rose-400 border border-rose-800/60">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
        FAIL
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium bg-[#D5A35D]/15 text-[#D5A35D] border border-[#D5A35D]/40">
      <span className="w-1.5 h-1.5 rounded-full bg-[#D5A35D]" />
      INSUFFICIENT DATA
    </span>
  );
};

export const FormatBadge: React.FC<{ format: SourceFormat | string | null | undefined }> = ({ format }) => {
  const isXml = format?.toLowerCase() === 'xml';
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono uppercase font-semibold border ${isXml
        ? 'bg-[#1D2024] text-[#E8E5DC] border-[#35383C]'
        : 'bg-[#252219] text-[#D5A35D] border-[#D5A35D]/40'
      }`}>
      {format || 'UNKNOWN'}
    </span>
  );
};

export const ExperimentTypeBadge: React.FC<{ type: ExperimentType | string }> = ({ type }) => {
  const isDiscovery = type === 'discovery';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono capitalize border ${isDiscovery
        ? 'bg-[#16181C] text-[#E8E5DC] border-[#35383C]'
        : 'bg-[#252219] text-[#D5A35D] border-[#D5A35D]/40'
      }`}>
      {type}
    </span>
  );
};
