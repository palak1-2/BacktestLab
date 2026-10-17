import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Server,
  Calendar,
  Search,
  Sliders,
  BarChart3,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../../api/client';
import type { EvaluationResponseSchema, ExperimentDetailSchema } from '../../api/types';
import { Drawer } from '../common/Drawer';
import { EvaluationBadge, ExperimentTypeBadge, FormatBadge, RuleOutcomeBadge } from '../common/Badge';
import { ErrorAlert } from '../common/ErrorAlert';

interface ExperimentDetailDrawerProps {
  experimentId: number | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ExperimentDetailDrawer: React.FC<ExperimentDetailDrawerProps> = ({
  experimentId,
  isOpen,
  onClose,
}) => {
  const navigate = useNavigate();

  const [experiment, setExperiment] = useState<ExperimentDetailSchema | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponseSchema | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown | null>(null);

  const [activeTab, setActiveTab] = useState<'overview' | 'metrics' | 'parameters'>('overview');
  const [metricSearch, setMetricSearch] = useState('');
  const [paramSearch, setParamSearch] = useState('');

  useEffect(() => {
    if (!isOpen || !experimentId) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    Promise.all([
      api.getExperiment(experimentId),
      api.getEvaluation(experimentId),
    ])
      .then(([expData, evalData]) => {
        if (isMounted) {
          setExperiment(expData);
          setEvaluation(evalData);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [experimentId, isOpen]);

  const filteredMetrics = experiment?.metrics.filter((m) =>
    m.name.toLowerCase().includes(metricSearch.toLowerCase().trim())
  );

  const filteredParams = experiment?.parameters.filter((p) =>
    p.name.toLowerCase().includes(paramSearch.toLowerCase().trim())
  );

  const formatMetricValue = (val: number | null, unit: string | null) => {
    if (val === null || val === undefined || !Number.isFinite(val)) {
      return <span className="text-slate-500 font-mono italic">Missing / Non-finite</span>;
    }
    const formatted = val.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
    return (
      <span className="font-mono text-slate-100 font-medium">
        {formatted} {unit ? <span className="text-slate-400 text-xs">{unit}</span> : ''}
      </span>
    );
  };

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      width="max-w-3xl"
      title={
        experiment ? (
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="font-mono font-bold text-slate-200">
              Experiment #{experiment.id}
            </span>
            {experiment.optimization_pass !== null && (
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Pass {experiment.optimization_pass}
              </span>
            )}
            <EvaluationBadge status={experiment.evaluation_status} size="sm" />
          </div>
        ) : (
          <span>Loading experiment...</span>
        )
      }
      subtitle={
        experiment?.strategy_name
          ? `${experiment.strategy_name} ${experiment.symbol ? `• ${experiment.symbol}` : ''} ${experiment.timeframe ? `• ${experiment.timeframe}` : ''
          }`
          : undefined
      }
    >
      {error != null ? (
        <ErrorAlert
          error={error}
          onRetry={() => {
            if (experimentId) {
              setIsLoading(true);
              setError(null);
              Promise.all([
                api.getExperiment(experimentId),
                api.getEvaluation(experimentId),
              ])
                .then(([expData, evalData]) => {
                  setExperiment(expData);
                  setEvaluation(evalData);
                })
                .catch((err) => setError(err))
                .finally(() => setIsLoading(false));
            }
          }}
          title="Failed to fetch experiment details"
        />
      ) : null}

      {isLoading && (
        <div className="space-y-4">
          <div className="h-28 surface-card rounded animate-pulse" />
          <div className="h-44 surface-card rounded animate-pulse" />
          <div className="h-64 surface-card rounded animate-pulse" />
        </div>
      )}

      {!isLoading && experiment && (
        <div className="space-y-6">
          {/* Tabs navigation */}
          <div className="flex items-center gap-2 border-b border-[#35383C] pb-2">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer ${activeTab === 'overview'
                  ? 'bg-[#252219] text-[#D5A35D] border border-[#D5A35D]/40 font-semibold shadow-xs'
                  : 'text-[#A6A8AB] hover:text-[#E8E5DC] hover:bg-[#1D2024]'
                }`}
            >
              Overview & Qualification
            </button>
            <button
              onClick={() => setActiveTab('metrics')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${activeTab === 'metrics'
                  ? 'bg-[#252219] text-[#D5A35D] border border-[#D5A35D]/40 font-semibold shadow-xs'
                  : 'text-[#A6A8AB] hover:text-[#E8E5DC] hover:bg-[#1D2024]'
                }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Metrics ({experiment.metrics.length})
            </button>
            <button
              onClick={() => setActiveTab('parameters')}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${activeTab === 'parameters'
                  ? 'bg-[#252219] text-[#D5A35D] border border-[#D5A35D]/40 font-semibold shadow-xs'
                  : 'text-[#A6A8AB] hover:text-[#E8E5DC] hover:bg-[#1D2024]'
                }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              Parameters ({experiment.parameters.length})
            </button>
          </div>

          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Deterministic Evaluation Card */}
              {evaluation && (
                <div className="bg-[#1D2024] rounded-lg p-5 border border-[#35383C] space-y-4 shadow-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-[#35383C]">
                    <div>
                      <h3 className="text-xs font-mono font-semibold uppercase text-[#E8E5DC] flex items-center gap-1.5">
                        <Activity className="w-4 h-4 text-[#D5A35D]" />
                        Deterministic Rule Evaluation
                      </h3>
                      <p className="text-[11px] text-[#A6A8AB] font-mono mt-0.5">
                        Thresholds re-evaluated deterministically against experiment metrics
                      </p>
                    </div>
                    <EvaluationBadge status={evaluation.overall_status} size="md" />
                  </div>

                  {/* Rule results list */}
                  <div className="space-y-2.5">
                    {evaluation.rules.map((rule, idx) => {
                      const actualText =
                        rule.actual_value !== null && Number.isFinite(rule.actual_value)
                          ? Number(rule.actual_value).toFixed(2)
                          : 'None';

                      return (
                        <div
                          key={idx}
                          className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded bg-[#090D14] border border-slate-800/80"
                        >
                          <div className="space-y-0.5">
                            <span className="font-mono text-xs font-medium text-slate-200">
                              {rule.metric}
                            </span>
                            <div className="text-[11px] font-mono text-slate-400 flex items-center gap-2">
                              <span>
                                Threshold: <strong className="text-slate-300">{rule.operator} {rule.threshold}</strong>
                              </span>
                              <span>•</span>
                              <span>
                                Actual: <strong className="text-slate-300">{actualText}</strong>
                              </span>
                            </div>
                          </div>

                          <div className="shrink-0">
                            <RuleOutcomeBadge status={rule.status} />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="p-3 rounded bg-slate-900/40 border border-slate-800/60 flex items-start gap-2 text-[11px] text-slate-500">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
                    <span>
                      Qualification is a deterministic research heuristic based on defined criteria (e.g. Profit Factor &gt; 1.5, Drawdown &lt; 25%, Win Rate &gt; 60%). Not financial advice or a trade recommendation.
                    </span>
                  </div>
                </div>
              )}

              {/* Experiment Metadata */}
              <div className="surface-card rounded-lg p-5 border border-slate-800 space-y-4">
                <h3 className="text-xs font-mono font-semibold uppercase text-slate-300 flex items-center gap-1.5 pb-2 border-b border-slate-800/80">
                  <Server className="w-3.5 h-3.5 text-cyan-400" />
                  Run Metadata & Environment
                </h3>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs font-mono">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Symbol</span>
                    <span className="text-slate-200 font-semibold">{experiment.symbol || '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Timeframe</span>
                    <span className="text-slate-200 font-semibold">
                      {experiment.timeframe || '—'}{' '}
                      {experiment.raw_timeframe && experiment.raw_timeframe !== experiment.timeframe && (
                        <span className="text-slate-500 text-[10px]">({experiment.raw_timeframe})</span>
                      )}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Server</span>
                    <span className="text-slate-200">{experiment.server || '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Initial Deposit</span>
                    <span className="text-slate-200">
                      {experiment.deposit !== null ? `$${experiment.deposit.toLocaleString()}` : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Leverage</span>
                    <span className="text-slate-200">{experiment.leverage || '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">MT5 Build</span>
                    <span className="text-slate-200">{experiment.mt5_build || '—'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Source Format</span>
                    <div className="mt-0.5">
                      <FormatBadge format={experiment.source_format} />
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Import Batch</span>
                    <button
                      onClick={() => {
                        onClose();
                        navigate(`/autopsy/${experiment.import_batch_id}`);
                      }}
                      className="text-cyan-400 hover:underline flex items-center gap-1 mt-0.5"
                    >
                      Batch #{experiment.import_batch_id}
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Experiment Type</span>
                    <div className="mt-0.5">
                      <ExperimentTypeBadge type={experiment.experiment_type} />
                    </div>
                  </div>
                </div>

                {(experiment.test_start || experiment.test_end) && (
                  <div className="pt-3 border-t border-slate-800/60 flex items-center gap-2 text-xs font-mono text-slate-400">
                    <Calendar className="w-3.5 h-3.5 text-slate-500" />
                    <span>
                      Backtest Period:{' '}
                      <strong className="text-slate-200">
                        {experiment.test_start ? new Date(experiment.test_start).toLocaleDateString() : 'Start'}
                      </strong>{' '}
                      to{' '}
                      <strong className="text-slate-200">
                        {experiment.test_end ? new Date(experiment.test_end).toLocaleDateString() : 'End'}
                      </strong>
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: METRICS */}
          {activeTab === 'metrics' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="relative flex-1 max-w-sm">
                  <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search metrics..."
                    value={metricSearch}
                    onChange={(e) => setMetricSearch(e.target.value)}
                    className="w-full bg-[#090D14] border border-slate-800 rounded px-3 py-1.5 pl-8 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
                  />
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {filteredMetrics?.length} of {experiment.metrics.length} metrics
                </span>
              </div>

              <div className="surface-card rounded-lg border border-slate-800 overflow-hidden">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="table-header text-slate-400 font-mono text-[11px] uppercase tracking-wider">
                      <th className="py-2.5 px-4 font-semibold">Metric Name</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {filteredMetrics?.map((m) => (
                      <tr key={m.id} className="hover:bg-[#131B2E]/40">
                        <td className="py-2.5 px-4 text-slate-300 font-medium">{m.name}</td>
                        <td className="py-2.5 px-4 text-right">
                          {formatMetricValue(m.value, m.unit)}
                        </td>
                      </tr>
                    ))}
                    {filteredMetrics?.length === 0 && (
                      <tr>
                        <td colSpan={2} className="py-6 text-center text-slate-500 font-mono">
                          No metrics match "{metricSearch}"
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: PARAMETERS */}
          {activeTab === 'parameters' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="relative flex-1 max-w-sm">
                  <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search parameters..."
                    value={paramSearch}
                    onChange={(e) => setParamSearch(e.target.value)}
                    className="w-full bg-[#090D14] border border-slate-800 rounded px-3 py-1.5 pl-8 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
                  />
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {filteredParams?.length} of {experiment.parameters.length} parameters
                </span>
              </div>

              <div className="surface-card rounded-lg border border-slate-800 overflow-hidden">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="table-header text-slate-400 font-mono text-[11px] uppercase tracking-wider">
                      <th className="py-2.5 px-4 font-semibold">Parameter Name</th>
                      <th className="py-2.5 px-4 font-semibold w-24">Type</th>
                      <th className="py-2.5 px-4 font-semibold text-right">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {filteredParams?.map((p) => (
                      <tr key={p.id} className="hover:bg-[#131B2E]/40">
                        <td className="py-2.5 px-4 text-slate-200 font-medium">{p.name}</td>
                        <td className="py-2.5 px-4">
                          <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold bg-slate-900 border border-slate-800 text-slate-400">
                            {p.data_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-right text-cyan-300 font-semibold break-all">
                          {p.value}
                        </td>
                      </tr>
                    ))}
                    {filteredParams?.length === 0 && (
                      <tr>
                        <td colSpan={3} className="py-6 text-center text-slate-500 font-mono">
                          No parameters match "{paramSearch}"
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
};
