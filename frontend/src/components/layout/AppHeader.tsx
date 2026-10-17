import React, { useEffect, useState } from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import { Layers, Upload, Database, Activity } from 'lucide-react';
import { api } from '../../api/client';
import { Button } from '../common/Button';

export const AppHeader: React.FC = () => {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const navigate = useNavigate();

  const checkHealth = async () => {
    try {
      const res = await api.getHealth();
      setIsHealthy(res.status === 'ok');
    } catch {
      setIsHealthy(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { to: '/', label: 'Research Batches', icon: Layers, end: true },
    { to: '/import', label: 'Import Report', icon: Upload },
    { to: '/experiments', label: 'Experiment Explorer', icon: Database },
    { to: '/autopsy', label: 'Research Autopsy', icon: Activity },
  ];

  return (
    <header className="border-b border-[#35383C] bg-[#111317]/95 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 rounded bg-[#1D2024] border border-[#D5A35D]/50 flex items-center justify-center text-[#D5A35D] group-hover:border-[#D5A35D] transition-colors shadow-xs">
                <span className="font-serif font-bold text-sm tracking-tighter">B·L</span>
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="text-base font-serif font-medium text-[#E8E5DC] tracking-tight group-hover:text-white transition-colors">
                    BacktestLab
                  </span>
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-medium bg-[#1D2024] text-[#D5A35D] border border-[#35383C]">
                    STUDIO
                  </span>
                </div>
                <span className="text-[10px] text-[#A6A8AB] tracking-wider uppercase font-mono hidden sm:inline">
                  Quantitative Research
                </span>
              </div>
            </Link>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-1.5">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition-colors ${isActive
                        ? 'bg-[#1D2024] text-[#E8E5DC] border border-[#35383C] shadow-xs'
                        : 'text-[#A6A8AB] hover:text-[#E8E5DC] hover:bg-[#1D2024]/50 border border-transparent'
                      }`
                    }
                  >
                    <Icon className="w-3.5 h-3.5 text-[#D5A35D]/90" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-3">
            {/* Backend status indicator */}
            <div
              className="flex items-center gap-2 px-2.5 py-1 rounded text-[11px] font-mono border border-[#35383C] bg-[#1D2024]"
              title={
                isHealthy === true
                  ? 'FastAPI engine responsive on port 8001'
                  : isHealthy === false
                    ? 'Engine unreachable on port 8001'
                    : 'Checking backend status...'
              }
            >
              {isHealthy === true ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span className="text-[#A6A8AB]">Engine Online</span>
                </>
              ) : isHealthy === false ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                  <span className="text-rose-400">Offline</span>
                </>
              ) : (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-[#D5A35D] animate-pulse" />
                  <span className="text-[#A6A8AB]">Connecting...</span>
                </>
              )}
            </div>

            <Button
              variant="primary"
              size="xs"
              onClick={() => navigate('/import')}
              icon={<Upload className="w-3.5 h-3.5" />}
            >
              Import Report
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
};
