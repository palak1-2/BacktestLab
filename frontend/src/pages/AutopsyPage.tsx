import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Database,
  RefreshCw,
  Layers,
  AlertTriangle,
  Info,
  Sliders,
  BarChart3,
} from 'lucide-react';
import { api } from '../api/client';
import type { ImportBatchSummarySchema, ResearchAutopsyResponse } from '../api/types';
import { AutopsySummary } from '../components/autopsy/AutopsySummary';
import { FindingsList } from '../components/autopsy/FindingsList';
import { MetricSummaryTable } from '../components/autopsy/MetricSummaryTable';
import { ParameterAnalysis } from '../components/autopsy/ParameterAnalysis';
import { AIInterpretationPanel } from '../components/autopsy/AIInterpretationPanel';
import { ExperimentDetailDrawer } from '../components/explorer/ExperimentDetailDrawer';
import { FormatBadge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';

export const AutopsyPage: React.FC = () => {
  const { batchId } = useParams<{ batchId?: string }>();
  const navigate = useNavigate();

  const [batches, setBatches] = useState<ImportBatchSummarySchema[]>([]);
  const [autopsy, setAutopsy] = useState<ResearchAutopsyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [error, setError] = useState<unknown | null>(null);

  const [selectedExperimentId, setSelectedExperimentId] = useState<number | null>(null);

  // Load available batches
  useEffect(() => {
    api.getImportBatches(1, 100)
      .then((res) => {
        setBatches(res.items);
        // If no batchId in URL and we have batches, navigate to first batch
        if (!batchId && res.items.length > 0) {
          navigate(`/autopsy/${res.items[0].id}`, { replace: true });
        }
      })
      .catch(() => { });
  }, [batchId, navigate]);

  const activeBatchId = batchId ? Number(batchId) : batches[0]?.id;

  const fetchAutopsy = async (id: number, includeAi = false) => {
    if (includeAi) {
      setIsAiLoading(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await api.getResearchAutopsy(id, includeAi);
      setAutopsy(data);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
      setIsAiLoading(false);
    }
  };

  useEffect(() => {
    if (activeBatchId) {
      fetchAutopsy(activeBatchId, false);
    }
  }, [activeBatchId]);

  const handleRequestAi = () => {
    if (activeBatchId) {
      fetchAutopsy(activeBatchId, true);
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header & Batch Selector */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-5 pb-5 border-b border-[#35383C]">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded bg-[#252219] border border-[#D5A35D]/30 text-xs font-mono text-[#D5A35D]">
            <span>POST-MORTEM RESEARCH AUTOPSY</span>
            {autopsy && (
              <>
                <span>•</span>
                <span>BATCH #{autopsy.import_batch_id}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-serif font-medium text-[#E8E5DC] tracking-tight">
              Research Autopsy
            </h1>
            {autopsy && <FormatBadge format={autopsy.source_format} />}
          </div>
          <p className="text-xs sm:text-sm text-[#A6A8AB] max-w-2xl font-sans">
            Deterministic post-mortem analysis of optimization outcomes, rule failure causalities, parameter outcome associations, and metric distribution.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Batch Selector Dropdown */}
          {batches.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-[#A6A8AB]">Batch:</span>
              <select
                value={activeBatchId || ''}
                onChange={(e) => navigate(`/autopsy/${e.target.value}`)}
                className="bg-[#1D2024] border border-[#35383C] rounded px-3 py-1.5 text-xs text-[#E8E5DC] focus:outline-none focus:border-[#D5A35D] font-mono cursor-pointer"
              >
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    #{b.id} - {b.source_file.slice(0, 24)} ({b.source_format.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>
          )}

          {autopsy && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate(`/experiments?batch_id=${autopsy.import_batch_id}`)}
              icon={<Database className="w-3.5 h-3.5" />}
            >
              Explore Batch Runs
            </Button>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => activeBatchId && fetchAutopsy(activeBatchId, false)}
            isLoading={isLoading}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error != null ? (
        <ErrorAlert
          error={error}
          onRetry={() => activeBatchId && fetchAutopsy(activeBatchId, false)}
          title="Failed to load Research Autopsy"
        />
      ) : null}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 surface-card rounded-lg animate-pulse" />
            ))}
          </div>
          <div className="h-48 surface-card rounded-lg animate-pulse" />
          <div className="h-64 surface-card rounded-lg animate-pulse" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && batches.length === 0 && (
        <EmptyState
          icon={Layers}
          title="No research batches found"
          description="Import an MT5 optimization report to generate a research autopsy."
          actionLabel="Import MT5 Report"
          onAction={() => navigate('/import')}
        />
      )}

      {/* Autopsy Report Content */}
      {!isLoading && autopsy && (
        <div className="space-y-8 animate-in fade-in">
          {/* SECTION 1: Status Overview */}
          <div className="space-y-3">
            <h2 className="text-sm font-mono font-semibold uppercase tracking-wider text-slate-400">
              Qualification Overview
            </h2>
            <AutopsySummary autopsy={autopsy} />
          </div>

          {/* SECTION 2: Deterministic Findings */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-mono font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                Deterministic Findings & Evidence ({autopsy.findings.length})
              </h2>
              <span className="text-xs font-mono text-slate-500">
                Click any evidence run to inspect full parameters & metrics
              </span>
            </div>
            <FindingsList
              findings={autopsy.findings}
              onSelectExperiment={setSelectedExperimentId}
            />
          </div>

          {/* SECTION 3: Metric Summaries & Distribution */}
          <div className="space-y-3">
            <h2 className="text-sm font-mono font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <BarChart3 className="w-4 h-4 text-cyan-400" />
              Metric Distribution & Coverage
            </h2>
            <MetricSummaryTable
              metrics={autopsy.metric_summary}
              totalExperiments={autopsy.total_experiments}
            />
          </div>

          {/* SECTION 4: Parameter Analysis */}
          <div className="space-y-3">
            <h2 className="text-sm font-mono font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-purple-400" />
              Parameter Partitioning & Outcome Associations
            </h2>
            <ParameterAnalysis
              parameters={autopsy.parameter_analysis.parameters}
              groupingMethod={autopsy.parameter_analysis.grouping_method}
              interpretationCaveat={autopsy.parameter_analysis.interpretation}
              minimumGroupSupport={autopsy.parameter_analysis.minimum_group_support}
              onSelectExperiment={setSelectedExperimentId}
            />
          </div>

          {/* SECTION 5: Missing-Data Limitations & Analysis Notes */}
          {autopsy.analysis_notes && autopsy.analysis_notes.length > 0 && (
            <div className="bg-[#1D2024] rounded-lg p-5 border border-[#35383C] space-y-2.5 shadow-xs">
              <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-[#E8E5DC] flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-[#D5A35D]" />
                Deterministic Autopsy Methodology Notes
              </h3>
              <ul className="space-y-1.5 text-xs text-[#A6A8AB] font-sans leading-relaxed list-disc list-inside">
                {autopsy.analysis_notes.map((note, idx) => (
                  <li key={idx} className="text-[#E8E5DC]/90">
                    {note}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* SECTION 6: Local AI Interpretation */}
          <div className="space-y-3 pt-2">
            <AIInterpretationPanel
              aiResult={autopsy.ai_interpretation}
              isLoading={isAiLoading}
              onRequestAi={handleRequestAi}
              onSelectExperiment={setSelectedExperimentId}
            />
          </div>
        </div>
      )}

      {/* Experiment Detail Drawer when evidence ID is clicked */}
      <ExperimentDetailDrawer
        experimentId={selectedExperimentId}
        isOpen={Boolean(selectedExperimentId)}
        onClose={() => setSelectedExperimentId(null)}
      />
    </div>
  );
};
