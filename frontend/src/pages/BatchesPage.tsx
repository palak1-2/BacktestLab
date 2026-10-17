import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, RefreshCw, Filter, FileSpreadsheet } from 'lucide-react';
import { api } from '../api/client';
import type { PaginatedImportBatchesSchema } from '../api/types';
import { BatchCard } from '../components/batches/BatchCard';
import { Button } from '../components/common/Button';
import { Pagination } from '../components/common/Pagination';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';

export const BatchesPage: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedImportBatchesSchema | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [searchTerm, setSearchTerm] = useState('');

  const fetchBatches = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.getImportBatches(page, pageSize);
      setData(res);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, [page, pageSize]);

  const filteredItems = data?.items.filter((item) =>
    item.source_file.toLowerCase().includes(searchTerm.toLowerCase().trim())
  );

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* 1. EDITORIAL RESEARCH MASTHEAD */}
      <section className="bg-[#1D2024] border border-[#35383C] rounded-xl p-6 sm:p-8">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
          <div className="space-y-3 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-[#252219] border border-[#D5A35D]/30 text-xs font-mono text-[#D5A35D]">
              <span>QUANTITATIVE RESEARCH DOSSIERS</span>
              <span>•</span>
              <span>MT5 STRATEGY TESTER ARCHIVE</span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-serif font-medium text-[#E8E5DC] tracking-tight">
              Strategy Optimization Records
            </h1>
            <p className="text-sm text-[#A6A8AB] leading-relaxed font-sans">
              Historical MetaTrader 5 optimization reports evaluated through deterministic qualification criteria. Strategy passes are tested against quantitative survival thresholds: Profit Factor ≥ 1.5, Drawdown ≤ 25%, and Win Rate ≥ 60%.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row lg:flex-col items-start sm:items-center lg:items-end gap-3 shrink-0">
            <div className="flex items-center gap-2.5">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchBatches}
                isLoading={isLoading}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Refresh
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate('/import')}
                icon={<Upload className="w-3.5 h-3.5" />}
              >
                Import New Report
              </Button>
            </div>
            {data && (
              <span className="text-xs font-mono text-[#A6A8AB]">
                Archived Reports: <strong className="text-[#D5A35D]">{data.total}</strong>
              </span>
            )}
          </div>
        </div>

        {/* Quantitative Criteria Breakdown Strip */}
        <div className="mt-6 pt-5 border-t border-[#35383C]/70 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div className="bg-[#16181C] p-3.5 rounded border border-[#35383C]/60 space-y-1">
            <span className="text-[10px] text-[#A6A8AB] uppercase tracking-wider block">Hard Criteria // Profit Factor</span>
            <span className="text-[#E8E5DC] font-semibold text-sm">PF &ge; 1.50</span>
            <p className="text-[11px] text-[#A6A8AB]/80 font-sans">Gross profit to gross loss ratio must exceed minimum viability threshold.</p>
          </div>
          <div className="bg-[#16181C] p-3.5 rounded border border-[#35383C]/60 space-y-1">
            <span className="text-[10px] text-[#A6A8AB] uppercase tracking-wider block">Hard Criteria // Max Drawdown</span>
            <span className="text-[#E8E5DC] font-semibold text-sm">DD &le; 25.0%</span>
            <p className="text-[11px] text-[#A6A8AB]/80 font-sans">Peak-to-valley equity degradation bound to enforce risk limits.</p>
          </div>
          <div className="bg-[#16181C] p-3.5 rounded border border-[#35383C]/60 space-y-1">
            <span className="text-[10px] text-[#A6A8AB] uppercase tracking-wider block">Hard Criteria // Trade Win Rate</span>
            <span className="text-[#D5A35D] font-semibold text-sm">WR &ge; 60.0%</span>
            <p className="text-[11px] text-[#A6A8AB]/80 font-sans">Requires XLSX export or companion CSV pairing for XML reports.</p>
          </div>
        </div>
      </section>

      {/* Error display */}
      {error != null ? (
        <ErrorAlert
          error={error}
          onRetry={fetchBatches}
          title="Failed to load historical import batches"
        />
      ) : null}

      {/* 2. REGISTRY TOOLBAR */}
      {Boolean(data && data.total > 0) && (
        <div className="flex items-center justify-between gap-4 flex-wrap pb-2 border-b border-[#35383C]">
          <div className="relative flex-1 max-w-md">
            <Filter className="w-3.5 h-3.5 text-[#A6A8AB] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search batches by filename..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#1D2024] border border-[#35383C] rounded px-3 py-1.5 pl-8 text-xs text-[#E8E5DC] placeholder:text-[#A6A8AB]/70 focus:outline-none focus:border-[#D5A35D] font-mono"
            />
          </div>

          <div className="text-xs font-mono text-[#A6A8AB]">
            Showing <strong className="text-[#E8E5DC]">{filteredItems?.length ?? 0}</strong> of <strong className="text-[#D5A35D]">{data?.total}</strong> registered batches
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {Boolean(isLoading && !data) && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 bg-[#1D2024] rounded-lg animate-pulse border border-[#35383C]" />
          ))}
        </div>
      )}

      {/* Empty State */}
      {Boolean(!isLoading && data && data.total === 0) && (
        <EmptyState
          icon={FileSpreadsheet}
          title="No research batches recorded"
          description="The local repository contains zero imported MT5 reports. Ingest a Strategy Tester XML or XLSX optimization file to begin quantitative evaluation."
          actionLabel="Import MT5 Report"
          actionIcon={<Upload className="w-4 h-4" />}
          onAction={() => navigate('/import')}
        />
      )}

      {/* Batch Dossiers List */}
      {Boolean(filteredItems && filteredItems.length > 0) && (
        <div className="space-y-4">
          {filteredItems?.map((batch) => (
            <BatchCard key={batch.id} batch={batch} />
          ))}
        </div>
      )}

      {Boolean(filteredItems && filteredItems.length === 0 && data && data.total > 0) && (
        <div className="p-8 text-center text-xs text-[#A6A8AB] border border-[#35383C] bg-[#1D2024] rounded-lg font-mono">
          No batches match query "{searchTerm}". Clear filter to inspect all records.
        </div>
      )}

      {/* Pagination */}
      {Boolean(data && data.total > 0) && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={data ? data.total : 0}
          onPageChange={setPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize);
            setPage(1);
          }}
          isLoading={isLoading}
        />
      )}
    </div>
  );
};
