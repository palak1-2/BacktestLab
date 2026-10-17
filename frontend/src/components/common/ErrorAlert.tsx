import React, { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { ApiError } from '../../api/client';
import { Button } from './Button';

interface ErrorAlertProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  error,
  onRetry,
  title = 'An error occurred while loading data',
}) => {
  const [showDetails, setShowDetails] = useState(false);

  let message = 'Unknown error';
  let status: number | undefined;
  let raw: unknown = null;

  if (error instanceof ApiError) {
    message = error.detail;
    status = error.status;
    raw = error.raw;
  } else if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === 'string') {
    message = error;
  }

  return (
    <div className="rounded border border-rose-900/60 bg-rose-950/20 p-4 text-slate-200">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="text-sm font-semibold text-rose-200">{title}</h4>
            {status ? (
              <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-rose-950 text-rose-300 border border-rose-800">
                HTTP {status}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-rose-300/90 mt-1 font-mono break-words">{message}</p>

          {raw != null ? (
            <div className="mt-2.5">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="inline-flex items-center gap-1 text-[11px] font-mono text-rose-400 hover:text-rose-300 transition-colors"
              >
                {showDetails ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                {showDetails ? 'Hide technical payload' : 'Show technical payload'}
              </button>
              {showDetails ? (
                <pre className="mt-1.5 p-2 rounded bg-black/40 border border-rose-950 text-[10px] text-rose-200 overflow-x-auto font-mono">
                  {typeof raw === 'object' ? JSON.stringify(raw, null, 2) : String(raw)}
                </pre>
              ) : null}
            </div>
          ) : null}

          {onRetry ? (
            <div className="mt-3">
              <Button
                variant="outline"
                size="xs"
                onClick={onRetry}
                icon={<RefreshCw className="w-3 h-3" />}
                className="border-rose-800/80 hover:bg-rose-950/40 text-rose-300"
              >
                Retry request
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
