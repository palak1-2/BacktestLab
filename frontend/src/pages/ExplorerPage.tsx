import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { RefreshCw, FileSearch } from 'lucide-react';
import { api } from '../api/client';
import type {
  EvaluationStatus,
  ExperimentFilterParams,
  ExperimentType,
  ImportBatchSummarySchema,
  PaginatedExperimentsSchema,
} from '../api/types';
import { ExperimentFilters } from '../components/explorer/ExperimentFilters';
import { ExperimentTable } from '../components/explorer/ExperimentTable';
import { ExperimentDetailDrawer } from '../components/explorer/ExperimentDetailDrawer';
import { Pagination } from '../components/common/Pagination';
import { Button } from '../components/common/Button';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';

export const ExplorerPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse filters from URL
  const batchIdParam = searchParams.get('batch_id');
  const statusParam = searchParams.get('status') as EvaluationStatus | null;
  const typeParam = searchParams.get('type') as ExperimentType | null;
  const pageParam = searchParams.get('page');
  const pageSizeParam = searchParams.get('page_size');
  const expIdParam = searchParams.get('exp_id');

  const [filters, setFilters] = useState<ExperimentFilterParams>({
    import_batch_id: batchIdParam ? Number(batchIdParam) : undefined,
    evaluation_status: statusParam || undefined,
    experiment_type: typeParam || undefined,
    strategy_name: searchParams.get('strategy') || undefined,
    symbol: searchParams.get('symbol') || undefined,
    timeframe: searchParams.get('timeframe') || undefined,
    page: pageParam ? Number(pageParam) : 1,
    page_size: pageSizeParam ? Number(pageSizeParam) : 50,
  });

  const [batches, setBatches] = useState<ImportBatchSummarySchema[]>([]);
  const [data, setData] = useState<PaginatedExperimentsSchema | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown | null>(null);

  const [selectedExperimentId, setSelectedExperimentId] = useState<number | null>(
    expIdParam ? Number(expIdParam) : null
  );

  // Sync state changes back to URL search params
  const syncUrlParams = (newFilters: ExperimentFilterParams, expId?: number | null) => {
    const params = new URLSearchParams();
    if (newFilters.import_batch_id) params.set('batch_id', newFilters.import_batch_id.toString());
    if (newFilters.evaluation_status) params.set('status', newFilters.evaluation_status);
    if (newFilters.experiment_type) params.set('type', newFilters.experiment_type);
    if (newFilters.strategy_name) params.set('strategy', newFilters.strategy_name);
    if (newFilters.symbol) params.set('symbol', newFilters.symbol);
    if (newFilters.timeframe) params.set('timeframe', newFilters.timeframe);
    if (newFilters.page && newFilters.page > 1) params.set('page', newFilters.page.toString());
    if (newFilters.page_size && newFilters.page_size !== 50) params.set('page_size', newFilters.page_size.toString());
    if (expId) params.set('exp_id', expId.toString());

    setSearchParams(params, { replace: true });
  };

  // Load available batches for dropdown
  useEffect(() => {
    api.getImportBatches(1, 100)
      .then((res) => setBatches(res.items))
      .catch(() => { });
  }, []);

  const fetchExperiments = async (currentFilters: ExperimentFilterParams) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.getExperiments(currentFilters);
      setData(res);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchExperiments(filters);
    syncUrlParams(filters, selectedExperimentId);
  }, [
    filters.page,
    filters.page_size,
    filters.import_batch_id,
    filters.evaluation_status,
    filters.experiment_type,
    filters.strategy_name,
    filters.symbol,
    filters.timeframe,
  ]);

  const handleFilterChange = (newFilters: ExperimentFilterParams) => {
    setFilters(newFilters);
  };

  const handleSelectExperiment = (id: number) => {
    setSelectedExperimentId(id);
    syncUrlParams(filters, id);
  };

  const handleCloseDrawer = () => {
    setSelectedExperimentId(null);
    syncUrlParams(filters, null);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-[#35383C]">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 px-2 py-0.5 rounded bg-[#252219] border border-[#D5A35D]/30 text-[11px] font-mono text-[#D5A35D]">
            <span>ANALYTICAL WORKSPACE</span>
            <span>•</span>
            <span>EXPERIMENT MATRIX</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-serif font-medium text-[#E8E5DC] tracking-tight flex items-center gap-2.5">
            Experiment Explorer
          </h1>
          <p className="text-xs sm:text-sm text-[#A6A8AB] max-w-2xl font-sans">
            Filter, search, and drill down into individual MT5 strategy optimization passes with deterministic rule qualification decisions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {data && (
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-[#1D2024] border border-[#35383C] text-xs font-mono text-[#A6A8AB] rounded">
              <span>Matching Passes:</span>
              <strong className="text-[#D5A35D] font-semibold">{data.total.toLocaleString()}</strong>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchExperiments(filters)}
            isLoading={isLoading}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter toolbar */}
      <ExperimentFilters
        filters={filters}
        onChange={handleFilterChange}
        batches={batches}
        isLoading={isLoading}
      />

      {/* Error state */}
      {error != null ? (
        <ErrorAlert
          error={error}
          onRetry={() => fetchExperiments(filters)}
          title="Failed to query experiments"
        />
      ) : null}

      {/* Experiments Table or Empty State */}
      {Boolean(isLoading && !data) && (
        <div className="surface-card rounded-lg p-8 border border-slate-800 space-y-3">
          <div className="h-6 bg-slate-900 rounded animate-pulse" />
          <div className="h-44 bg-slate-900/60 rounded animate-pulse" />
        </div>
      )}

      {Boolean(!isLoading && data && data.items.length === 0) && (
        <EmptyState
          icon={FileSearch}
          title="No experiments match your search criteria"
          description="Try broadening or clearing your filters, or select a different import batch."
          actionLabel="Clear all filters"
          onAction={() => handleFilterChange({ page: 1, page_size: filters.page_size || 50 })}
        />
      )}

      {Boolean(data && data.items.length > 0) && (
        <div className="space-y-4">
          <ExperimentTable
            experiments={data ? data.items : []}
            onSelectExperiment={handleSelectExperiment}
            selectedExperimentId={selectedExperimentId}
            isLoading={isLoading}
          />

          <Pagination
            page={data ? data.page : 1}
            pageSize={data ? data.page_size : 50}
            total={data ? data.total : 0}
            onPageChange={(p) => setFilters((prev) => ({ ...prev, page: p }))}
            onPageSizeChange={(ps) => setFilters((prev) => ({ ...prev, page_size: ps, page: 1 }))}
            isLoading={isLoading}
          />
        </div>
      )}

      {/* Experiment Detail Drawer */}
      <ExperimentDetailDrawer
        experimentId={selectedExperimentId}
        isOpen={Boolean(selectedExperimentId)}
        onClose={handleCloseDrawer}
      />
    </div>
  );
};
