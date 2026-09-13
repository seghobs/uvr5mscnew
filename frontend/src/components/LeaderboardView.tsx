'use client';

import React, { useState, useEffect } from 'react';
import { Trophy, Award, Zap, Sparkles, Filter, ChevronRight, ShieldCheck } from 'lucide-react';
import { Language, AccentColor, LeaderboardEntry } from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';

interface LeaderboardViewProps {
  lang: Language;
  accentColor: AccentColor;
}

const fallbackRankings: Record<string, LeaderboardEntry[]> = {
  vocals: [
    { model: 'BS-Roformer-Viperx-1297', score: '12.97', speed: '1.2x', type: 'Roformer (S-Tier)' },
    { model: 'BS-Roformer-Viperx-1296', score: '12.96', speed: '1.2x', type: 'Roformer (S-Tier)' },
    { model: 'BS-Roformer-Revive 2 (Bleedless) by pcunwa', score: '12.90', speed: '1.1x', type: 'Roformer (2026 Bleedless)' },
    { model: 'BS-Roformer-Revive 3e (Fullness) by pcunwa', score: '12.88', speed: '1.1x', type: 'Roformer (2026 Fullness)' },
    { model: 'Mel-Roformer-Viperx-1143', score: '11.43', speed: '1.1x', type: 'Roformer (S-Tier)' },
    { model: 'BS-Roformer-Viperx-1053', score: '10.53', speed: '1.3x', type: 'Roformer (Elite)' },
    { model: 'Mel-Roformer-Karaoke-Aufr33', score: '10.19', speed: '1.4x', type: 'Roformer (Special)' },
    { model: 'Kim_Vocal_2', score: '9.95', speed: '1.6x', type: 'MDX-Net (Elite)' },
    { model: 'UVR-MDX-NET-Voc_FT', score: '9.82', speed: '1.5x', type: 'MDX-Net (Elite)' },
    { model: 'Kim_Vocal_1', score: '9.65', speed: '1.7x', type: 'MDX-Net' },
    { model: 'UVR-MDX-NET_Main_438', score: '9.45', speed: '1.6x', type: 'MDX-Net' },
    { model: 'BS-Roformer-De-Reverb', score: '8.95', speed: '1.0x', type: 'Roformer (Utility)' },
    { model: 'UVR-VR-Voc-Main', score: '8.75', speed: '2.3x', type: 'VR Arch' },
    { model: 'Demucs-v4-htdemucs_ft', score: '8.20', speed: '0.8x', type: 'Demucs v4' },
  ],
  instrumental: [
    { model: 'UVR-MDX-NET-Inst_Main', score: '10.24', speed: '1.4x', type: 'MDX-Net (S-Tier)' },
    { model: 'UVR-MDX-NET-Inst_HQ_1', score: '10.12', speed: '1.3x', type: 'MDX-Net (S-Tier)' },
    { model: 'UVR-MDX-NET-Inst_HQ_2', score: '9.98', speed: '1.4x', type: 'MDX-Net (Elite)' },
    { model: 'MDX23C-8KFFT-InstVoc_HQ', score: '9.85', speed: '1.1x', type: 'MDX23C (Elite)' },
    { model: 'Kim_Inst', score: '9.65', speed: '1.8x', type: 'MDX-Net' },
    { model: 'UVR-MDX-NET-Inst_full_292', score: '9.40', speed: '1.5x', type: 'MDX-Net' },
    { model: 'UVR-VR-Inst-Main', score: '8.90', speed: '2.4x', type: 'VR Arch' },
    { model: 'Demucs-v4-htdemucs', score: '8.45', speed: '0.9x', type: 'Demucs v4' },
  ],
  drums: [
    { model: 'Demucs-v4-htdemucs_ft (Drums)', score: '10.80', speed: '0.8x', type: 'Demucs v4 (S-Tier)' },
    { model: 'MDX23C-Drums-HQ', score: '10.15', speed: '1.2x', type: 'MDX23C (Elite)' },
  ],
  bass: [
    { model: 'Demucs-v4-htdemucs_ft (Bass)', score: '11.20', speed: '0.8x', type: 'Demucs v4 (S-Tier)' },
    { model: 'MDX23C-Bass-HQ', score: '10.40', speed: '1.2x', type: 'MDX23C (Elite)' },
  ],
};

export const LeaderboardView: React.FC<LeaderboardViewProps> = ({ lang, accentColor }) => {
  const t = (key: string) => getTranslation(lang, key);
  const [filter, setFilter] = useState<'vocals' | 'instrumental' | 'drums' | 'bass'>('vocals');
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [entries, setEntries] = useState<LeaderboardEntry[]>(fallbackRankings.vocals);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    const filterKey = filter === 'instrumental' ? 'instrumental' : filter;
    
    // Set fallback immediately
    setEntries(fallbackRankings[filterKey] || fallbackRankings.vocals);

    api
      .getLeaderboard(filterKey)
      .then((res) => {
        if (res && res.html) {
          setHtmlContent(res.html);
        }
      })
      .catch((e) => {
        // Fallback already active, do not crash
        console.warn('Backend leaderboard using fallback rankings:', e);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [filter]);

  return (
    <div className="glass-panel rounded-3xl p-6 sm:p-8 lg:p-8 shadow-2xl space-y-6 border border-white/10">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-2xl bg-amber-500/15 text-amber-400 border border-amber-500/30 shadow-[0_0_15px_rgba(245,158,11,0.2)]">
            <Trophy className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-xl font-black font-outfit text-white tracking-tight">
              {t('Model Performance Leaderboard')}
            </h3>
            <p className="text-xs text-slate-400">
              {t('Model performance and quality rankings.')}
            </p>
          </div>
        </div>

        {/* Stem Category Filter Chips */}
        <div className="flex items-center gap-1.5 p-1 rounded-2xl glass-panel border border-white/10 self-start sm:self-auto shadow-inner">
          {[
            { id: 'vocals', label: t('Vocals') },
            { id: 'instrumental', label: t('Instrumental') },
            { id: 'drums', label: 'Drums' },
            { id: 'bass', label: 'Bass' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setFilter(item.id as any)}
              className={cn(
                'px-4 py-2 rounded-xl text-xs font-bold font-outfit transition-all duration-200 active:scale-95',
                filter === item.id
                  ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-white shadow-lg shadow-amber-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Modern Leaderboard Rankings Table */}
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="text-slate-400 text-[11px] font-bold uppercase tracking-wider border-b border-white/5">
              <th className="pb-3 px-3">Rank</th>
              <th className="pb-3 px-3">Model Name</th>
              <th className="pb-3 px-3">SDR Score</th>
              <th className="pb-3 px-3 text-right">Inference Speed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04] text-xs">
            {entries.map((item, index) => {
              const isFirst = index === 0;
              const isSecond = index === 1;
              const isThird = index === 2;

              return (
                <tr
                  key={item.model}
                  className="hover:bg-white/[0.03] transition-colors duration-150 group"
                >
                  {/* Rank Badge */}
                  <td className="py-4 px-3">
                    <div className="flex items-center gap-2">
                      {isFirst && (
                        <span className="w-7 h-7 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-300 font-black flex items-center justify-center shadow-[0_0_10px_rgba(245,158,11,0.4)]">
                          #1
                        </span>
                      )}
                      {isSecond && (
                        <span className="w-7 h-7 rounded-xl bg-slate-300/20 border border-slate-300/40 text-slate-200 font-black flex items-center justify-center">
                          #2
                        </span>
                      )}
                      {isThird && (
                        <span className="w-7 h-7 rounded-xl bg-amber-700/20 border border-amber-700/40 text-amber-500 font-black flex items-center justify-center">
                          #3
                        </span>
                      )}
                      {!isFirst && !isSecond && !isThird && (
                        <span className="w-7 h-7 rounded-xl bg-slate-900 border border-slate-800 text-slate-500 font-bold flex items-center justify-center font-mono">
                          #{index + 1}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Model Name & Architecture */}
                  <td className="py-4 px-3">
                    <div className="space-y-0.5">
                      <div className="font-bold text-white text-xs sm:text-sm group-hover:text-amber-200 transition-colors">
                        {item.model}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider font-semibold">
                          {item.type}
                        </span>
                      </div>
                    </div>
                  </td>

                  {/* SDR Benchmark Score */}
                  <td className="py-4 px-3">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-emerald-400 font-bold text-sm">
                        {item.score}
                      </span>
                      {index < 3 ? (
                        <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-mono font-bold tracking-wider shadow-[0_0_8px_rgba(16,185,129,0.3)]">
                          S-TIER
                        </span>
                      ) : index < 7 ? (
                        <span className="text-[9px] px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 font-mono font-bold tracking-wider">
                          ELITE
                        </span>
                      ) : (
                        <span className="text-[9px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono font-medium">
                          PRO
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Speed */}
                  <td className="py-4 px-3 text-right">
                    <span className="font-mono text-xs px-2.5 py-1 rounded-xl bg-slate-950/80 border border-white/5 text-slate-300">
                      ⚡ {item.speed}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
