/**
 * Exact TypeScript definitions derived directly from backend Pydantic schemas
 * (app/schemas/experiment.py, app/services/experiments/autopsy.py, app/services/experiments/gemma.py).
 *
 * Do NOT invent properties, metrics, or endpoints.
 */

export type ExperimentType = 'discovery' | 'validation';
export type EvaluationStatus = 'QUALIFIED' | 'REJECTED' | 'INSUFFICIENT_DATA' | 'PENDING';
export type DataType = 'integer' | 'float' | 'boolean' | 'string';
export type SourceFormat = 'xlsx' | 'xml';
export type RuleOutcomeStatus = 'PASS' | 'FAIL' | 'INSUFFICIENT_DATA';

export interface HealthResponse {
  status: string;
}

export interface ParameterSchema {
  id: number;
  name: string;
  value: string;
  data_type: DataType;
}

export interface MetricSchema {
  id: number;
  name: string;
  value: number | null;
  unit: string | null;
}

export interface ExperimentSummarySchema {
  id: number;
  strategy_name: string | null;
  strategy_version: string | null;
  symbol: string | null;
  timeframe: string | null;
  optimization_pass: number | null;
  experiment_type: ExperimentType;
  evaluation_status: EvaluationStatus | null;
  created_at: string;
}

export interface ExperimentDetailSchema {
  id: number;
  import_batch_id: number;
  strategy_name: string | null;
  strategy_version: string | null;
  symbol: string | null;
  timeframe: string | null;
  raw_timeframe: string | null;
  test_start: string | null;
  test_end: string | null;
  server: string | null;
  deposit: number | null;
  leverage: string | null;
  mt5_build: string | null;
  source_file: string | null;
  source_format: SourceFormat | null;
  optimization_pass: number | null;
  experiment_type: ExperimentType;
  evaluation_status: EvaluationStatus | null;
  created_at: string;
  parameters: ParameterSchema[];
  metrics: MetricSchema[];
}

export interface RuleResultSchema {
  metric: string;
  operator: string;
  threshold: number;
  actual_value: number | null;
  status: RuleOutcomeStatus;
}

export interface EvaluationResponseSchema {
  experiment_id: number;
  overall_status: EvaluationStatus;
  rules: RuleResultSchema[];
}

export interface ImportBatchSummarySchema {
  id: number;
  source_file: string;
  source_format: SourceFormat;
  created_at: string;
  experiments_created: number;
  warnings: string[];
}

export interface PaginatedImportBatchesSchema {
  total: number;
  page: number;
  page_size: number;
  items: ImportBatchSummarySchema[];
}

export interface PaginatedExperimentsSchema {
  total: number;
  page: number;
  page_size: number;
  items: ExperimentSummarySchema[];
}

export interface ImportResponseSchema {
  imported: boolean;
  duplicate: boolean;
  source_format: SourceFormat;
  source_file: string;
  source_hash: string;
  import_batch_id?: number | null;
  experiments_created: number;
  qualified: number;
  rejected: number;
  insufficient_data: number;
  pending: number;
  warnings: string[];
  detail?: string | null;
}

export interface AutopsyFinding {
  finding_id: string;
  kind: 'failure_pattern' | 'data_gap';
  title: string;
  description: string;
  metric: string;
  operator?: string;
  threshold?: number;
  count: number;
  percentage_of_all: number;
  evidence_experiment_ids: number[];
  evidence_count: number;
}

export interface MetricDistribution {
  available_count: number;
  missing_count: number;
  min: number | null;
  median: number | null;
  max: number | null;
}

export interface ParameterOutcome {
  usable_count: number;
  missing_count: number;
  min: number | null;
  median: number | null;
  max: number | null;
  status: 'available' | 'unavailable';
}

export interface ParameterGroup {
  kind: 'numeric_range' | 'boolean' | 'categorical';
  value?: string | boolean | number;
  minimum?: number;
  maximum?: number;
  experiment_count: number;
  low_support: boolean;
  evidence_experiment_ids: number[];
  outcomes: Record<string, ParameterOutcome>;
}

export interface ParameterAnalysisItem {
  name: string;
  parameter_types: string[];
  experiment_count: number;
  usable_value_count: number;
  missing_parameter_count: number;
  unusable_value_count: number;
  unusable_values: Record<
    string,
    {
      count: number;
      evidence_experiment_ids: number[];
    }
  >;
  groups: ParameterGroup[];
}

export interface AIObservation {
  text: string;
  finding_ids: string[];
  evidence_experiment_ids: number[];
}

export interface AIFollowUpQuestion {
  question: string;
  finding_ids: string[];
  evidence_experiment_ids: number[];
}

export interface AIInterpretation {
  summary: string;
  observations: AIObservation[];
  follow_up_questions: AIFollowUpQuestion[];
  referenced_finding_ids: string[];
  limitations: string[];
}

export interface AIResult {
  status: 'success' | 'unavailable' | 'error';
  reason?: string;
  model?: string;
  interpretation?: AIInterpretation;
  context_truncated?: boolean;
}

export interface ResearchAutopsyResponse {
  import_batch_id: number;
  source_file: string;
  source_format: 'xlsx' | 'xml';
  total_experiments: number;
  status_counts: {
    qualified: number;
    rejected: number;
    incomplete: number;
    pending: number;
  };
  metric_summary: Record<string, MetricDistribution>;
  parameter_analysis: {
    grouping_method: string;
    minimum_group_support: number;
    interpretation: string;
    parameters: ParameterAnalysisItem[];
  };
  findings: AutopsyFinding[];
  analysis_notes: string[];
  ai_interpretation?: AIResult;
}

export interface ExperimentFilterParams {
  strategy_name?: string;
  symbol?: string;
  timeframe?: string;
  experiment_type?: ExperimentType;
  evaluation_status?: EvaluationStatus;
  import_batch_id?: number;
  page?: number;
  page_size?: number;
}
