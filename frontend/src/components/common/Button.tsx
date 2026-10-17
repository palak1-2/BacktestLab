import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'secondary',
  size = 'sm',
  isLoading = false,
  icon,
  className = '',
  disabled,
  ...props
}) => {
  const base = 'inline-flex items-center justify-center font-medium transition-colors select-none focus:outline-none focus-visible:ring-1 focus-visible:ring-cyan-500 disabled:opacity-50 disabled:pointer-events-none rounded cursor-pointer';

  const sizeClasses = {
    xs: 'px-2 py-1 text-xs gap-1.5',
    sm: 'px-3 py-1.5 text-xs gap-2',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-5 py-2.5 text-base gap-2.5',
  };

  const variantClasses = {
    primary: 'bg-[#D5A35D] hover:bg-[#E2B36E] text-[#111317] font-semibold shadow-xs active:translate-y-px',
    secondary: 'bg-[#1D2024] hover:bg-[#25292F] text-[#E8E5DC] border border-[#35383C] hover:border-[#4B5057] active:translate-y-px',
    outline: 'bg-transparent hover:bg-[#1D2024] text-[#E8E5DC] border border-[#35383C] hover:border-[#D5A35D]/60 active:translate-y-px',
    ghost: 'bg-transparent hover:bg-[#1D2024]/70 text-[#A6A8AB] hover:text-[#E8E5DC]',
    danger: 'bg-rose-950/30 hover:bg-rose-900/40 text-rose-300 border border-rose-800/60 active:translate-y-px',
  };

  return (
    <button
      className={`${base} ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        icon && <span className="shrink-0">{icon}</span>
      )}
      <span>{children}</span>
    </button>
  );
};
