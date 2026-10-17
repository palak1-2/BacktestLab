import React, { useRef, useState } from 'react';
import { Upload, FileSpreadsheet, FileText, CheckCircle2, AlertTriangle, AlertCircle, X, ArrowRight, Database, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../api/client';
import type { ImportResponseSchema } from '../../api/types';
import { Button } from '../common/Button';
import { FormatBadge } from '../common/Badge';

export const ImportDropzone: React.FC = () => {
  const navigate = useNavigate();

  const [primaryFile, setPrimaryFile] = useState<File | null>(null);
  const [companionCsv, setCompanionCsv] = useState<File | null>(null);

  const [isDraggingPrimary, setIsDraggingPrimary] = useState(false);
  const [isDraggingCompanion, setIsDraggingCompanion] = useState(false);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<ImportResponseSchema | null>(null);
  const [uploadError, setUploadError] = useState<{ message: string; status?: number; raw?: unknown } | null>(null);

  const primaryInputRef = useRef<HTMLInputElement>(null);
  const companionInputRef = useRef<HTMLInputElement>(null);

  const isPrimaryXml = primaryFile ? primaryFile.name.toLowerCase().endsWith('.xml') : false;
  const isPrimaryXlsx = primaryFile ? primaryFile.name.toLowerCase().endsWith('.xlsx') : false;

  const handlePrimaryFileSelect = (file: File) => {
    setUploadResult(null);
    setUploadError(null);
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'xml' && ext !== 'xlsx') {
      setUploadError({
        message: `Unsupported file extension '.${ext}'. Only MetaTrader 5 .xml and .xlsx reports are supported.`,
      });
      return;
    }
    setPrimaryFile(file);
    if (ext === 'xlsx') {
      // Clear companion csv if previously set since XLSX cannot be paired
      setCompanionCsv(null);
    }
  };

  const handleCompanionCsvSelect = (file: File) => {
    setUploadResult(null);
    setUploadError(null);
    if (!isPrimaryXml) {
      setUploadError({
        message: 'A Win Rate companion CSV can only be paired with an MT5 XML report.',
      });
      return;
    }
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'csv') {
      setUploadError({
        message: `Expected a .csv file for the win rate companion, but got .${ext}.`,
      });
      return;
    }
    setCompanionCsv(file);
  };

  const handleUpload = async () => {
    if (!primaryFile) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);

    try {
      const result = await api.importExperiments(primaryFile, companionCsv || undefined);
      setUploadResult(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setUploadError({
          message: err.detail,
          status: err.status,
          raw: err.raw,
        });
      } else if (err instanceof Error) {
        setUploadError({ message: err.message });
      } else {
        setUploadError({ message: 'Failed to import report due to an unexpected error.' });
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setPrimaryFile(null);
    setCompanionCsv(null);
    setUploadResult(null);
    setUploadError(null);
    if (primaryInputRef.current) primaryInputRef.current.value = '';
    if (companionInputRef.current) companionInputRef.current.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Upload Box Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Primary File Dropzone */}
        <div className="surface-card rounded p-5 border border-[#35383C] bg-[#1D2024] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-semibold uppercase text-[#E8E5DC] flex items-center gap-1.5">
                <FileSpreadsheet className="w-4 h-4 text-[#D5A35D]" />
                1. Primary Report (Required)
              </span>
              <span className="text-[11px] font-mono text-[#A6A8AB]">.XML or .XLSX (max 50 MB)</span>
            </div>

            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDraggingPrimary(true);
              }}
              onDragLeave={() => setIsDraggingPrimary(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDraggingPrimary(false);
                if (e.dataTransfer.files?.[0]) {
                  handlePrimaryFileSelect(e.dataTransfer.files[0]);
                }
              }}
              onClick={() => primaryInputRef.current?.click()}
              className={`border-2 border-dashed rounded p-6 text-center cursor-pointer transition-all ${
                isDraggingPrimary
                  ? 'border-[#D5A35D] bg-[#252219]/50'
                  : primaryFile
                  ? 'border-[#D5A35D]/50 bg-[#16181C]'
                  : 'border-[#35383C] hover:border-[#D5A35D]/40 bg-[#111317]'
              }`}
            >
              <input
                ref={primaryInputRef}
                type="file"
                accept=".xml,.xlsx"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) {
                    handlePrimaryFileSelect(e.target.files[0]);
                  }
                }}
              />

              {primaryFile ? (
                <div className="space-y-2">
                  <div className="w-10 h-10 rounded bg-[#252219] border border-[#D5A35D]/40 text-[#D5A35D] mx-auto flex items-center justify-center">
                    <FileSpreadsheet className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#E8E5DC] font-mono truncate max-w-xs mx-auto">
                      {primaryFile.name}
                    </p>
                    <p className="text-xs text-[#A6A8AB] font-mono mt-0.5">
                      {(primaryFile.size / (1024 * 1024)).toFixed(2)} MB • {primaryFile.name.split('.').pop()?.toUpperCase()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPrimaryFile(null);
                      setCompanionCsv(null);
                      if (primaryInputRef.current) primaryInputRef.current.value = '';
                    }}
                    icon={<X className="w-3 h-3" />}
                    className="text-[#A6A8AB] hover:text-[#E05252]"
                  >
                    Remove file
                  </Button>
                </div>
              ) : (
                <div className="space-y-2 py-3">
                  <div className="w-10 h-10 rounded bg-[#16181C] border border-[#35383C] text-[#A6A8AB] mx-auto flex items-center justify-center">
                    <Upload className="w-5 h-5 text-[#A6A8AB]" />
                  </div>
                  <p className="text-xs text-[#E8E5DC] font-medium">
                    Drag and drop your MT5 optimization file here, or{' '}
                    <span className="text-[#D5A35D] hover:underline">browse files</span>
                  </p>
                  <p className="text-[11px] text-[#A6A8AB]">
                    Supports Strategy Tester optimization reports exported as XML (MS-Excel XML) or XLSX
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Companion CSV Dropzone */}
        <div
          className={`surface-card rounded p-5 border transition-all flex flex-col justify-between ${
            !isPrimaryXml
              ? 'opacity-50 border-[#35383C]/60 bg-[#16181C]/50'
              : 'border-[#35383C] bg-[#1D2024]'
          }`}
        >
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-semibold uppercase text-[#E8E5DC] flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-[#D5A35D]" />
                2. Win Rate CSV Companion (XML Only)
              </span>
              <span className="text-[11px] font-mono text-[#A6A8AB]">Optional</span>
            </div>

            <div
              onDragOver={(e) => {
                e.preventDefault();
                if (isPrimaryXml) setIsDraggingCompanion(true);
              }}
              onDragLeave={() => setIsDraggingCompanion(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDraggingCompanion(false);
                if (isPrimaryXml && e.dataTransfer.files?.[0]) {
                  handleCompanionCsvSelect(e.dataTransfer.files[0]);
                }
              }}
              onClick={() => {
                if (isPrimaryXml) companionInputRef.current?.click();
              }}
              className={`border-2 border-dashed rounded p-6 text-center transition-all ${
                !isPrimaryXml
                  ? 'border-[#35383C]/60 cursor-not-allowed bg-[#111317]/40'
                  : isDraggingCompanion
                  ? 'border-[#D5A35D] bg-[#252219]/50 cursor-pointer'
                  : companionCsv
                  ? 'border-[#D5A35D]/50 bg-[#16181C] cursor-pointer'
                  : 'border-[#35383C] hover:border-[#D5A35D]/40 bg-[#111317] cursor-pointer'
              }`}
            >
              <input
                ref={companionInputRef}
                type="file"
                accept=".csv"
                disabled={!isPrimaryXml}
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0]) {
                    handleCompanionCsvSelect(e.target.files[0]);
                  }
                }}
              />

              {!isPrimaryXml ? (
                <div className="py-4 space-y-1.5 text-center">
                  <div className="w-8 h-8 rounded bg-[#16181C] border border-[#35383C] text-[#A6A8AB]/60 mx-auto flex items-center justify-center">
                    <FileText className="w-4 h-4 text-[#A6A8AB]/60" />
                  </div>
                  <p className="text-xs text-[#A6A8AB] font-mono">
                    {isPrimaryXlsx
                      ? 'Companion CSV pairing is not available for XLSX reports.'
                      : 'Select an XML report on the left first to enable companion pairing.'}
                  </p>
                  <p className="text-[10px] text-[#A6A8AB]/80">
                    MT5 XML reports lack Win Rate columns by default; pairing restores full qualification.
                  </p>
                </div>
              ) : companionCsv ? (
                <div className="space-y-2">
                  <div className="w-10 h-10 rounded bg-[#252219] border border-[#D5A35D]/40 text-[#D5A35D] mx-auto flex items-center justify-center">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#E8E5DC] font-mono truncate max-w-xs mx-auto">
                      {companionCsv.name}
                    </p>
                    <p className="text-xs text-[#A6A8AB] font-mono mt-0.5">
                      {(companionCsv.size / 1024).toFixed(1)} KB • CSV Companion
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setCompanionCsv(null);
                      if (companionInputRef.current) companionInputRef.current.value = '';
                    }}
                    icon={<X className="w-3 h-3" />}
                    className="text-[#A6A8AB] hover:text-[#E05252]"
                  >
                    Remove companion
                  </Button>
                </div>
              ) : (
                <div className="space-y-2 py-3">
                  <div className="w-10 h-10 rounded bg-[#16181C] border border-[#35383C] text-[#A6A8AB] mx-auto flex items-center justify-center">
                    <Upload className="w-5 h-5 text-[#A6A8AB]" />
                  </div>
                  <p className="text-xs text-[#E8E5DC] font-medium">
                    Drag and drop companion <span className="text-[#D5A35D]">winrate.csv</span>, or{' '}
                    <span className="text-[#D5A35D] hover:underline">browse</span>
                  </p>
                  <p className="text-[11px] text-[#A6A8AB]">
                    Pairs Pass ID / Trade stats to supply Win Rate for deterministic qualification rules
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex items-center justify-between border-t border-[#35383C] pt-4">
        <div className="text-xs text-[#A6A8AB] font-mono">
          {primaryFile ? (
            <span>
              Ready to import <strong className="text-[#E8E5DC]">{primaryFile.name}</strong>
              {companionCsv && <span> paired with <strong className="text-[#D5A35D]">{companionCsv.name}</strong></span>}
            </span>
          ) : (
            <span>Please select a primary MT5 report file (.xml or .xlsx)</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {primaryFile && (
            <Button variant="ghost" size="sm" onClick={handleReset} disabled={isUploading}>
              Clear selection
            </Button>
          )}

          <Button
            variant="primary"
            size="md"
            onClick={handleUpload}
            disabled={!primaryFile || isUploading}
            isLoading={isUploading}
            icon={<Upload className="w-4 h-4" />}
          >
            {isUploading ? 'Ingesting & Evaluating...' : 'Start Ingestion'}
          </Button>
        </div>
      </div>

      {/* Error state */}
      {uploadError ? (
        <div className="rounded border border-rose-900/80 bg-[#251517] p-5 text-[#E8E5DC] animate-in fade-in">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-semibold text-rose-200">Import Failed</h4>
                {uploadError.status ? (
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#111317] text-rose-300 border border-rose-800">
                    HTTP {uploadError.status}
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-rose-300 mt-1 font-mono break-words">{uploadError.message}</p>
              {uploadError.raw != null ? (
                <pre className="mt-2 p-2 rounded bg-black/40 border border-rose-950 text-[10px] text-rose-200 font-mono overflow-x-auto">
                  {JSON.stringify(uploadError.raw, null, 2)}
                </pre>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {/* Duplicate Import Notice */}
      {uploadResult && uploadResult.duplicate && (
        <div className="rounded border border-[#D5A35D]/40 bg-[#252219]/60 p-5 text-[#E8E5DC] animate-in fade-in space-y-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-[#D5A35D] shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-[#E8E5DC]">Duplicate Report Detected</h4>
              <p className="text-xs text-[#D5A35D] mt-1 font-mono">
                {uploadResult.detail || 'This report has already been ingested. BacktestLab preserves deterministic idempotency.'}
              </p>
              <div className="mt-2 text-xs font-mono text-[#A6A8AB] space-y-1">
                <div>Source File: <strong className="text-[#E8E5DC]">{uploadResult.source_file}</strong></div>
                <div>Source SHA-256: <code className="text-[11px] text-[#E8E5DC]">{uploadResult.source_hash}</code></div>
                {uploadResult.import_batch_id && (
                  <div>Existing Batch ID: <strong className="text-[#D5A35D]">#{uploadResult.import_batch_id}</strong> ({uploadResult.experiments_created} experiments)</div>
                )}
              </div>
            </div>
          </div>

          {uploadResult.import_batch_id && (
            <div className="flex items-center gap-3 pt-2 border-t border-[#35383C]">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate(`/experiments?batch_id=${uploadResult.import_batch_id}`)}
                icon={<Database className="w-3.5 h-3.5" />}
              >
                View Batch #{uploadResult.import_batch_id} Experiments
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate(`/autopsy/${uploadResult.import_batch_id}`)}
                icon={<Activity className="w-3.5 h-3.5" />}
              >
                Open Research Autopsy
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Successful Ingestion Result */}
      {uploadResult && uploadResult.imported && (
        <div className="surface-card rounded p-6 border border-[#35383C] bg-[#1D2024] space-y-5 animate-in fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#35383C]">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded bg-[#132A1E] border border-[#4E9F76]/40 text-[#4E9F76] flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#E8E5DC] flex items-center gap-2">
                  Import & Evaluation Complete
                  <FormatBadge format={uploadResult.source_format} />
                </h3>
                <p className="text-xs text-[#A6A8AB] font-mono mt-0.5">
                  Batch #{uploadResult.import_batch_id} • {uploadResult.source_file}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate(`/experiments?batch_id=${uploadResult.import_batch_id}`)}
                icon={<Database className="w-3.5 h-3.5" />}
              >
                View Experiments
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate(`/autopsy/${uploadResult.import_batch_id}`)}
                icon={<Activity className="w-3.5 h-3.5" />}
              >
                Open Autopsy
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>

          {/* Qualification Summary Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="p-3 rounded border border-[#35383C] bg-[#16181C]">
              <span className="text-[11px] font-mono text-[#A6A8AB] uppercase">Created</span>
              <p className="text-lg font-mono font-bold text-[#E8E5DC] mt-1">
                {uploadResult.experiments_created.toLocaleString()}
              </p>
            </div>
            <div className="p-3 rounded border border-[#4E9F76]/40 bg-[#132A1E]/30">
              <span className="text-[11px] font-mono text-[#4E9F76] uppercase">Qualified</span>
              <p className="text-lg font-mono font-bold text-[#4E9F76] mt-1">
                {uploadResult.qualified.toLocaleString()}
              </p>
            </div>
            <div className="p-3 rounded border border-[#E05252]/40 bg-[#251517]/40">
              <span className="text-[11px] font-mono text-[#E05252] uppercase">Rejected</span>
              <p className="text-lg font-mono font-bold text-[#E05252] mt-1">
                {uploadResult.rejected.toLocaleString()}
              </p>
            </div>
            <div className="p-3 rounded border border-[#D5A35D]/40 bg-[#252219]/40">
              <span className="text-[11px] font-mono text-[#D5A35D] uppercase">Insufficient Data</span>
              <p className="text-lg font-mono font-bold text-[#D5A35D] mt-1">
                {uploadResult.insufficient_data.toLocaleString()}
              </p>
            </div>
            <div className="p-3 rounded border border-[#35383C] bg-[#16181C]">
              <span className="text-[11px] font-mono text-[#A6A8AB] uppercase">Pending</span>
              <p className="text-lg font-mono font-bold text-[#A6A8AB] mt-1">
                {uploadResult.pending.toLocaleString()}
              </p>
            </div>
          </div>

          {/* Ingestion Warnings if any */}
          {uploadResult.warnings && uploadResult.warnings.length > 0 && (
            <div className="p-4 rounded border border-[#D5A35D]/30 bg-[#252219]/40 space-y-2">
              <h4 className="text-xs font-mono font-semibold text-[#D5A35D] flex items-center gap-1.5 uppercase">
                <AlertTriangle className="w-3.5 h-3.5" />
                Ingestion Notes & Warnings ({uploadResult.warnings.length})
              </h4>
              <ul className="space-y-1 text-xs text-[#E8E5DC] font-mono">
                {uploadResult.warnings.map((w, idx) => (
                  <li key={idx} className="bg-[#111317] p-2 rounded border border-[#35383C]">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="text-[11px] text-[#A6A8AB] font-mono">
            SHA-256 Provenance Fingerprint: <code className="text-[#E8E5DC]">{uploadResult.source_hash}</code>
          </div>
        </div>
      )}
    </div>
  );
};
