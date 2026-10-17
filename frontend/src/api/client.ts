/**
 * API client interacting with the FastAPI backend through the Vite proxy (/api).
 */

import type {
  EvaluationResponseSchema,
  ExperimentDetailSchema,
  ExperimentFilterParams,
  HealthResponse,
  ImportResponseSchema,
  PaginatedExperimentsSchema,
  PaginatedImportBatchesSchema,
  ResearchAutopsyResponse,
} from './types';

export class ApiError extends Error {
  status: number;
  detail: string;
  raw: unknown;

  constructor(status: number, detail: string, raw?: unknown) {
    super(detail || `API Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.raw = raw;
  }
}

const BASE_URL = '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    let rawBody: unknown = null;
    try {
      const json = await res.json();
      rawBody = json;
      if (typeof json.detail === 'string') {
        errorDetail = json.detail;
      } else if (Array.isArray(json.detail)) {
        errorDetail = json.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ');
      } else if (json.detail) {
        errorDetail = JSON.stringify(json.detail);
      }
    } catch {
      try {
        const text = await res.text();
        if (text) errorDetail = text;
      } catch {
        // use default errorDetail
      }
    }
    throw new ApiError(res.status, errorDetail, rawBody);
  }
  return res.json() as Promise<T>;
}

export const api = {
  /** Check service liveness */
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${BASE_URL}/health`);
    return handleResponse<HealthResponse>(res);
  },

  /** List historical import batches */
  async getImportBatches(page = 1, pageSize = 50): Promise<PaginatedImportBatchesSchema> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    const res = await fetch(`${BASE_URL}/import-batches?${params.toString()}`);
    return handleResponse<PaginatedImportBatchesSchema>(res);
  },

  /** List experiments with optional filters and pagination */
  async getExperiments(filters: ExperimentFilterParams = {}): Promise<PaginatedExperimentsSchema> {
    const params = new URLSearchParams();
    if (filters.page) params.set('page', filters.page.toString());
    if (filters.page_size) params.set('page_size', filters.page_size.toString());
    if (filters.strategy_name) params.set('strategy_name', filters.strategy_name.trim());
    if (filters.symbol) params.set('symbol', filters.symbol.trim());
    if (filters.timeframe) params.set('timeframe', filters.timeframe.trim());
    if (filters.experiment_type) params.set('experiment_type', filters.experiment_type);
    if (filters.evaluation_status) params.set('evaluation_status', filters.evaluation_status);
    if (filters.import_batch_id) params.set('import_batch_id', filters.import_batch_id.toString());

    const res = await fetch(`${BASE_URL}/experiments?${params.toString()}`);
    return handleResponse<PaginatedExperimentsSchema>(res);
  },

  /** Get single experiment full detail with metrics and parameters */
  async getExperiment(id: number): Promise<ExperimentDetailSchema> {
    const res = await fetch(`${BASE_URL}/experiments/${id}`);
    return handleResponse<ExperimentDetailSchema>(res);
  },

  /** Get single experiment deterministic evaluation */
  async getEvaluation(id: number): Promise<EvaluationResponseSchema> {
    const res = await fetch(`${BASE_URL}/experiments/${id}/evaluation`);
    return handleResponse<EvaluationResponseSchema>(res);
  },

  /** Ingest an MT5 optimization report (XLSX or XML) with optional winrate CSV companion for XML */
  async importExperiments(file: File, winrateCsv?: File): Promise<ImportResponseSchema> {
    const formData = new FormData();
    formData.append('file', file);
    if (winrateCsv) {
      formData.append('winrate_csv', winrateCsv);
    }
    const res = await fetch(`${BASE_URL}/experiments/import`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<ImportResponseSchema>(res);
  },

  /** Fetch research autopsy for an import batch, with optional local AI interpretation */
  async getResearchAutopsy(importBatchId: number, includeAi = false): Promise<ResearchAutopsyResponse> {
    const params = new URLSearchParams({
      include_ai: includeAi ? 'true' : 'false',
    });
    const res = await fetch(`${BASE_URL}/research/autopsy/${importBatchId}?${params.toString()}`);
    return handleResponse<ResearchAutopsyResponse>(res);
  },
};
