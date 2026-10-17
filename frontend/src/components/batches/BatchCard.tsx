import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Database, Activity, AlertTriangle, ArrowRight, FileSpreadsheet, ChevronDown, ChevronUp } from 'lucide-react';
import type { ImportBatchSummarySchema } from '../../api/types';
import { FormatBadge } from '../common/Badge';
import { Button } from '../common/Button';

interface BatchCardProps {
  batch: ImportBatchSummarySchema;
}

export const BatchCard: React.FC<BatchCardProps> = ({ batch }) => {
  const navigate = useNavigate();
  const [showWarnings, setShowWarnings] = useState(false);

  const formattedDate = new Date(batch.created_at).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const hasWarnings = batch.warnings && batch.warnings.length > 0;

  return (
    <div className="bg-[#1D2024] rounded-lg p-5 sm:p-6 border border-[#35383C] hover:border-[#4B5057] transition-all shadow-xs group">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
        {/* Left: Info */}
        <div className="space-y-3 min-w-0 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="font-mono text-xs text-[#D5A35D] font-semibold bg-[#26221A] px-2 py-0.5 rounded border border-[#D5A35D]/30">
              BATCH #{batch.id}
            </span>
            <FormatBadge format={batch.source_format} />
            {hasWarnings && (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-[#D5A35D]/15 text-[#D5A35D] border border-[#D5A35D]/30">
                <AlertTriangle className="w-3 h-3 text-[#D5A35D]" />
                {batch.warnings.length} {batch.warnings.length === 1 ? 'provenance caveat' : 'provenance caveats'}
              </span>
            )}
          </div>

          <h3 className="text-base sm:text-lg font-medium text-[#E8E5DC] tracking-tight truncate flex items-center gap-2" title={batch.source_file}>
            <FileSpreadsheet className="w-4 h-4 text-[#A6A8AB] shrink-0" />
            <span className="truncate">{batch.source_file}</span>
          </h3>

          <div className="flex items-center gap-4 text-xs text-[#A6A8AB] font-mono flex-wrap">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-[#A6A8AB]/70" />
              <span>{formattedDate}</span>
            </div>
            <span className="text-[#35383C]">•</span>
            <div className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-[#A6A8AB]/70" />
              <span>
                <strong className="text-[#E8E5DC] font-semibold">{batch.experiments_created.toLocaleString()}</strong> experiment passes
              </span>
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2.5 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-[#35383C]/40">
          {hasWarnings && (
            <Button
              variant="ghost"
              size="xs"
              onClick={() => setShowWarnings(!showWarnings)}
              icon={showWarnings ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              className="text-[#D5A35D] hover:text-[#E2B36E]"
            >
              {showWarnings ? 'Hide caveats' : 'Provenance caveats'}
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/experiments?batch_id=${batch.id}`)}
            icon={<Database className="w-3.5 h-3.5" />}
          >
            Explore Runs
          </Button>

          <Button
          variant="primary"
          size="sm"
          className="whitespace-nowrap"
          onClick={() => navigate(`/autopsy/${batch.id}`)}
          icon={<Activity className="w-3.5 h-3.5" />}
        >
          Research Autopsy
          <ArrowRight className="inline-block w-3 h-3 ml-1 align-middle shrink-0" />
          </Button>
        </div>
      </div>

      {/* Expandable Warnings & Provenance */}
      {hasWarnings && showWarnings && (
        <div className="mt-4 pt-3 border-t border-[#35383C] bg-[#16181C] -mx-5 sm:-mx-6 -mb-5 sm:-mb-6 p-4 rounded-b-lg space-y-2">
          <h4 className="text-[11px] font-mono uppercase tracking-wider text-[#D5A35D] font-semibold flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Batch Ingestion Warnings & Data Provenance
          </h4>
          <ul className="space-y-1.5">
            {batch.warnings.map((w, i) => (
              <li key={i} className="text-xs text-[#E8E5DC]/90 font-mono bg-[#1D2024] p-2.5 rounded border border-[#35383C] leading-relaxed">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
