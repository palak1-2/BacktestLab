import React from 'react';
import {
  Sparkles,
  Bot,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  ShieldAlert,
  ExternalLink,
  Tag,
  Database,
  RefreshCw,
} from 'lucide-react';
import type { AIResult } from '../../api/types';
import { Button } from '../common/Button';

interface AIInterpretationPanelProps {
  aiResult?: AIResult | null;
  isLoading: boolean;
  onRequestAi: () => void;
  onSelectExperiment: (experimentId: number) => void;
}

export const AIInterpretationPanel: React.FC<AIInterpretationPanelProps> = ({
  aiResult,
  isLoading,
  onRequestAi,
  onSelectExperiment,
}) => {
  // 1. Not yet requested
  if (!aiResult && !isLoading) {
    return (
      <div className="surface-card rounded p-6 border border-[#35383C] bg-[#1D2024] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-[#E8E5DC] flex items-center gap-2">
              <Bot className="w-4 h-4 text-[#D5A35D]" />
              Optional Local AI Interpretation (Ollama / Gemma)
            </h3>
            <p className="text-xs text-[#A6A8AB] max-w-2xl leading-relaxed">
              Generate a qualitative post-mortem summary, evidence-grounded observations, and follow-up research questions using your local Ollama instance. BacktestLab keeps the deterministic report untrusted and strictly bounded.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={onRequestAi}
            icon={<Sparkles className="w-3.5 h-3.5 text-[#D5A35D]" />}
            className="border-[#D5A35D]/60 hover:bg-[#252219] text-[#D5A35D] shrink-0 font-medium"
          >
            Request Local AI
          </Button>
        </div>

        <div className="text-[11px] font-mono text-[#A6A8AB] pt-3 border-t border-[#35383C] flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 text-[#D5A35D]/80" />
          <span>Requires local Ollama running (default: http://localhost:11434 with model gemma3:4b).</span>
        </div>
      </div>
    );
  }

  // 2. Loading State
  if (isLoading) {
    return (
      <div className="surface-card rounded p-8 border border-[#D5A35D]/40 bg-[#1D2024] text-center space-y-3">
        <RefreshCw className="w-6 h-6 text-[#D5A35D] animate-spin mx-auto" />
        <h4 className="text-sm font-semibold text-[#E8E5DC]">Generating Qualitative Interpretation...</h4>
        <p className="text-xs text-[#A6A8AB] max-w-md mx-auto font-mono">
          Querying local Ollama with bounded deterministic autopsy findings. This may take a few moments depending on your local hardware.
        </p>
      </div>
    );
  }

  // 3. Unavailable State
  if (aiResult?.status === 'unavailable') {
    return (
      <div className="surface-card rounded p-5 border border-[#D5A35D]/40 bg-[#252219]/70 space-y-3">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[#D5A35D] shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-[#E8E5DC] flex items-center gap-2">
              Local AI Engine Unavailable
            </h4>
            <p className="text-xs text-[#D5A35D] font-mono mt-1 break-words">
              {aiResult.reason || 'Local Ollama service could not be contacted.'}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <Button
                variant="outline"
                size="xs"
                onClick={onRequestAi}
                icon={<RefreshCw className="w-3 h-3" />}
                className="border-[#D5A35D]/50 text-[#D5A35D] hover:bg-[#252219]"
              >
                Retry Local AI
              </Button>
              <span className="text-[11px] font-mono text-[#A6A8AB]">
                Deterministic findings above remain 100% complete and authoritative.
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 4. Error State
  if (aiResult?.status === 'error') {
    return (
      <div className="surface-card rounded p-5 border border-rose-900/60 bg-[#251517] space-y-3">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-semibold text-rose-200">Local AI Interpretation Error</h4>
            <p className="text-xs text-rose-300 font-mono mt-1 break-words">
              {aiResult.reason || 'Model output failed schema validation.'}
            </p>
            <div className="mt-3">
              <Button
                variant="outline"
                size="xs"
                onClick={onRequestAi}
                icon={<RefreshCw className="w-3 h-3" />}
                className="border-rose-800/80 text-rose-300 hover:bg-rose-950/40"
              >
                Retry
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 5. Success State
  const interpretation = aiResult?.interpretation;
  if (!interpretation) return null;

  return (
    <div className="surface-card rounded p-6 border border-[#35383C] bg-[#1D2024] space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#35383C]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded bg-[#252219] border border-[#D5A35D]/40 text-[#D5A35D] flex items-center justify-center">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#E8E5DC] flex items-center gap-2">
              Local AI Research Interpretation
              {aiResult.model && (
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#16181C] text-[#D5A35D] border border-[#35383C]">
                  {aiResult.model}
                </span>
              )}
            </h3>
            <p className="text-[11px] text-[#A6A8AB] font-mono mt-0.5">
              Evidence-linked qualitative analysis generated by local model
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="xs"
          onClick={onRequestAi}
          icon={<RefreshCw className="w-3 h-3" />}
          className="text-[#D5A35D] border-[#35383C] hover:border-[#D5A35D]/50 hover:bg-[#252219]"
        >
          Regenerate
        </Button>
      </div>

      {/* Context Truncation Notice */}
      {aiResult.context_truncated && (
        <div className="p-3 rounded bg-[#252219]/60 border border-[#D5A35D]/30 text-xs font-mono text-[#D5A35D] flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-[#D5A35D]" />
          <span>
            Notice: Input context was bounded to fit within model context limits. Only top findings and parameters were evaluated.
          </span>
        </div>
      )}

      {/* Qualitative Summary */}
      <div className="space-y-2">
        <h4 className="text-xs font-mono uppercase tracking-wider text-[#A6A8AB] font-semibold">
          Executive Summary
        </h4>
        <p className="text-xs text-[#E8E5DC] leading-relaxed font-sans bg-[#16181C] p-4 rounded border border-[#35383C]">
          {interpretation.summary}
        </p>
      </div>

      {/* Grounded Observations */}
      {interpretation.observations && interpretation.observations.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-mono uppercase tracking-wider text-[#A6A8AB] font-semibold">
            Grounded Observations ({interpretation.observations.length})
          </h4>
          <div className="grid grid-cols-1 gap-2.5">
            {interpretation.observations.map((obs, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded bg-[#16181C] border border-[#35383C] space-y-2"
              >
                <p className="text-xs text-[#E8E5DC] leading-relaxed font-sans">{obs.text}</p>

                <div className="flex items-center gap-3 pt-2 border-t border-[#35383C] flex-wrap text-[11px] font-mono">
                  {obs.finding_ids && obs.finding_ids.length > 0 && (
                    <div className="flex items-center gap-1">
                      <Tag className="w-3 h-3 text-[#A6A8AB]" />
                      {obs.finding_ids.map((fid) => (
                        <span
                          key={fid}
                          className="px-1.5 py-0.2 rounded bg-[#252219] text-[#D5A35D] border border-[#D5A35D]/30"
                        >
                          {fid}
                        </span>
                      ))}
                    </div>
                  )}

                  {obs.evidence_experiment_ids && obs.evidence_experiment_ids.length > 0 && (
                    <div className="flex items-center gap-1">
                      <Database className="w-3 h-3 text-[#A6A8AB]" />
                      {obs.evidence_experiment_ids.map((id) => (
                        <button
                          key={id}
                          onClick={() => onSelectExperiment(id)}
                          className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded bg-[#111317] hover:bg-[#252219] text-[#D5A35D] border border-[#35383C] hover:border-[#D5A35D]/50 transition-colors cursor-pointer"
                        >
                          <span>#{id}</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Follow-up Research Questions */}
      {interpretation.follow_up_questions && interpretation.follow_up_questions.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-mono uppercase tracking-wider text-[#A6A8AB] font-semibold flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-[#D5A35D]" />
            Recommended Follow-Up Research Questions
          </h4>
          <div className="space-y-2">
            {interpretation.follow_up_questions.map((q, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded bg-[#16181C] border border-[#35383C] space-y-2"
              >
                <p className="text-xs text-[#E8E5DC] font-medium leading-relaxed font-sans">
                  {q.question}
                </p>

                {(q.finding_ids?.length > 0 || q.evidence_experiment_ids?.length > 0) && (
                  <div className="flex items-center gap-2 pt-1.5 border-t border-[#35383C] flex-wrap text-[11px] font-mono">
                    {q.finding_ids?.map((fid) => (
                      <span
                        key={fid}
                        className="px-1.5 py-0.2 rounded bg-[#252219] text-[#D5A35D] border border-[#D5A35D]/30"
                      >
                        {fid}
                      </span>
                    ))}
                    {q.evidence_experiment_ids?.map((id) => (
                      <button
                        key={id}
                        onClick={() => onSelectExperiment(id)}
                        className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded bg-[#111317] text-[#D5A35D] border border-[#35383C] hover:border-[#D5A35D]/50 cursor-pointer"
                      >
                        <span>#{id}</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Qualitative Limitations */}
      {interpretation.limitations && interpretation.limitations.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-mono uppercase tracking-wider text-[#A6A8AB] font-semibold">
            Methodological Limitations
          </h4>
          <ul className="list-disc list-inside space-y-1 text-xs text-[#A6A8AB] font-sans">
            {interpretation.limitations.map((lim, idx) => (
              <li key={idx}>{lim}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Safety / Compliance Disclaimer */}
      <div className="p-3 rounded bg-[#16181C] border border-[#35383C] flex items-start gap-2 text-[11px] font-mono text-[#A6A8AB]">
        <ShieldAlert className="w-3.5 h-3.5 text-[#D5A35D]/80 shrink-0 mt-0.5" />
        <span>
          Local AI outputs are qualitative research narratives generated strictly from the supplied findings JSON. AI does not recalculate or override deterministic outcomes.
        </span>
      </div>
    </div>
  );
};
