import React, { useEffect } from 'react';
import { X } from 'lucide-react';

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  width?: string;
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  width = 'max-w-2xl',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer surface */}
      <div
        className={`relative z-10 w-full ${width} bg-[#16181C] border-l border-[#35383C] shadow-2xl flex flex-col h-full transform transition-transform duration-200 ease-out`}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#35383C] bg-[#1D2024] sticky top-0 z-20">
          <div className="min-w-0 pr-4">
            {typeof title === 'string' ? (
              <h2 className="text-base font-serif font-medium text-[#E8E5DC] tracking-tight truncate">{title}</h2>
            ) : (
              title
            )}
            {subtitle && (
              <p className="text-xs text-[#A6A8AB] mt-0.5 truncate font-mono">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#A6A8AB] hover:text-[#D5A35D] rounded hover:bg-[#23272D] transition-colors focus:outline-none focus:ring-1 focus:ring-[#D5A35D] cursor-pointer"
            aria-label="Close panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {children}
        </div>
      </div>
    </div>
  );
};
