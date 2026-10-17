import React from 'react';
import { X, RotateCcw } from 'lucide-react';
import type { EvaluationStatus, ExperimentFilterParams, ExperimentType, ImportBatchSummarySchema } from '../../api/types';
import { Button } from '../common/Button';

interface ExperimentFiltersProps {
  filters: ExperimentFilterParams;
  onChange: (newFilters: ExperimentFilterParams) => void;
  batches?: ImportBatchSummarySchema[];
  isLoading?: boolean;
}

export const ExperimentFilters: React.FC<ExperimentFiltersProps> = ({
  filters,
  onChange,
  batches = [],
  isLoading = false,
}) => {
  const updateFilter = (key: keyof ExperimentFilterParams, value: any) => {
    onChange({
      ...filters,
      [key]: value === '' || value === undefined ? undefined : value,
      page: 1, // reset to page 1 on filter change
    });
  };

  const clearFilters = () => {
    onChange({
      page: 1,
      page_size: filters.page_size || 50,
    });
  };

  const hasActiveFilters = Boolean(
    filters.strategy_name ||
    filters.symbol ||
    filters.timeframe ||
    filters.experiment_type ||
    filters.evaluation_status ||
    filters.import_batch_id
  );

  return (
    <div className="bg-[#1D2024] rounded-lg p-4 border border-[#35383C] space-y-3 shadow-xs">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {/* Batch Selector */}
        <div>
          <label className="block text-[11px] font-mono text-[#A6A8AB] mb-1">Import Batch</label>
          <select
            value={filters.import_batch_id || ''}
            onChange={(e) => updateFilter('import_batch_id', e.target.value ? Number(e.target.value) : undefined)}
            disabled={isLoading}
            className="w-full bg-[#16181C] border border-[#35383C] rounded px-2.5 py-1.5 text-xs text-[#E8E5DC] focus:outline-none focus:border-[#D5A35D] font-mono cursor-pointer"
          >
            <option value="">All Batches</option>
            {batches.map((b) => (
              <option key={b.id} value={b.id}>
                #{b.id} - {b.source_file.slice(0, 24)} ({b.source_format.toUpperCase()})
              </option>
            ))}
          </select>
        </div>

        {/* Evaluation Status */}
        <div>
          <label className="block text-[11px] font-mono text-[#A6A8AB] mb-1">Status</label>
          <select
            value={filters.evaluation_status || ''}
            onChange={(e) => updateFilter('evaluation_status', e.target.value as EvaluationStatus)}
            disabled={isLoading}
            className="w-full bg-[#16181C] border border-[#35383C] rounded px-2.5 py-1.5 text-xs text-[#E8E5DC] focus:outline-none focus:border-[#D5A35D] font-mono cursor-pointer"
          >
            <option value="">All Statuses</option>
            <option value="QUALIFIED">QUALIFIED</option>
            <option value="REJECTED">REJECTED</option>
            <option value="INSUFFICIENT_DATA">INSUFFICIENT DATA</option>
            <option value="PENDING">PENDING</option>
          </select>
        </div>

        {/* Experiment Type */}
        <div>
          <label className="block text-[11px] font-mono text-[#A6A8AB] mb-1">Type</label>
          <select
            value={filters.experiment_type || ''}
            onChange={(e) => updateFilter('experiment_type', e.target.value as ExperimentType)}
            disabled={isLoading}
            className="w-full bg-[#16181C] border border-[#35383C] rounded px-2.5 py-1.5 text-xs text-[#E8E5DC] focus:outline-none focus:border-[#D5A35D] font-mono cursor-pointer"
          >
            <option value="">All Types</option>
            <option value="discovery">Discovery</option>
            <option value="validation">Validation</option>
          </select>
        </div>

        {/* Symbol */}
        <div>
          <label className="block text-[11px] font-mono text-[#A6A8AB] mb-1">Symbol</label>
          <div className="relative">
            <input
              type="text"
              placeholder="e.g. EURUSD"
              value={filters.symbol || ''}
              onChange={(e) => updateFilter('symbol', e.target.value)}
              className="w-full bg-[#16181C] border border-[#35383C] rounded px-2.5 py-1.5 text-xs text-[#E8E5DC] placeholder:text-[#A6A8AB]/60 focus:outline-none focus:border-[#D5A35D] font-mono uppercase"
            />
            {filters.symbol && (
              <button
                onClick={() => updateFilter('symbol', undefined)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#A6A8AB] hover:text-[#E8E5DC]"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Timeframe */}
        <div>
          <label className="block text-[11px] font-mono text-[#A6A8AB] mb-1">Timeframe</label>
          <div className="relative">
            <input
              type="text"
              placeholder="e.g. H1, M15"
              value={filters.timeframe || ''}
              onChange={(e) => updateFilter('timeframe', e.target.value)}
              className="w-full bg-[#16181C] border border-[#35383C] rounded px-2.5 py-1.5 text-xs text-[#E8E5DC] placeholder:text-[#A6A8AB]/60 focus:outline-none focus:border-[#D5A35D] font-mono uppercase"
            />
            {filters.timeframe && (
              <button
                onClick={() => updateFilter('timeframe', undefined)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#A6A8AB] hover:text-[#E8E5DC]"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Strategy Name */}
        <div>
          <label className="block text-[11px] font-mono text-[#A6A8AB] mb-1">Strategy Name</label>
          <div className="relative">
            <input
              type="text"
              placeholder="Filter strategy..."
              value={filters.strategy_name || ''}
              onChange={(e) => updateFilter('strategy_name', e.target.value)}
              className="w-full bg-[#16181C] border border-[#35383C] rounded px-2.5 py-1.5 text-xs text-[#E8E5DC] placeholder:text-[#A6A8AB]/60 focus:outline-none focus:border-[#D5A35D] font-mono"
            />
            {filters.strategy_name && (
              <button
                onClick={() => updateFilter('strategy_name', undefined)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#A6A8AB] hover:text-[#E8E5DC]"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filter summary & reset */}
      {hasActiveFilters && (
        <div className="flex items-center justify-between pt-2 border-t border-[#35383C]/60 text-xs">
          <span className="text-[11px] font-mono text-[#D5A35D]">
            Active filters applied
          </span>
          <Button
            variant="ghost"
            size="xs"
            onClick={clearFilters}
            icon={<RotateCcw className="w-3 h-3" />}
            className="text-[#A6A8AB] hover:text-[#E8E5DC]"
          >
            Clear all filters
          </Button>
        </div>
      )}
    </div>
  );
};
