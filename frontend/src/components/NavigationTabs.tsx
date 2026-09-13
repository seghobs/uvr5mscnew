'use client';

import React from 'react';
import { Layers, Disc, Music, Activity, Radio, FolderHeart, Trophy, FolderArchive } from 'lucide-react';
import { TabId, Language, AccentColor } from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';

interface NavigationTabsProps {
  currentTab: TabId;
  onSelectTab: (tab: TabId) => void;
  lang: Language;
  accentColor: AccentColor;
}

export const NavigationTabs: React.FC<NavigationTabsProps> = ({
  currentTab,
  onSelectTab,
  lang,
  accentColor,
}) => {
  const t = (key: string) => getTranslation(lang, key);

  const modelTabs = [
    { id: 'roformer' as TabId, name: 'Roformer', badge: 'PRO', icon: Layers },
    { id: 'mdx23c' as TabId, name: 'MDX23C', badge: 'HQ', icon: Disc },
    { id: 'mdxnet' as TabId, name: 'MDX-NET', badge: 'CLASSIC', icon: Music },
    { id: 'vrarch' as TabId, name: 'VR Arch', badge: 'VOCALS', icon: Activity },
    { id: 'demucs' as TabId, name: 'Demucs', badge: 'v4', icon: Radio },
  ];

  const toolTabs = [
    { id: 'batch' as TabId, name: 'Toplu İşlem', icon: FolderArchive },
    { id: 'library' as TabId, name: t('Library'), icon: FolderHeart },
    { id: 'leaderboard' as TabId, name: t('Leaderboard'), icon: Trophy },
  ];

  return (
    <nav
      className="relative w-full glass-panel p-1.5 rounded-2xl border border-white/[0.08] backdrop-blur-2xl flex flex-wrap items-center gap-2 shadow-2xl"
    >
      {/* Model Architectures Group */}
      <div className="flex flex-wrap items-center gap-1 z-10">
        {modelTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;

          return (
            <button
              key={tab.id}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onSelectTab(tab.id)}
              className={cn(
                'relative flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-bold font-outfit transition-colors duration-200 active:scale-95 group shrink-0 whitespace-nowrap cursor-pointer',
                isActive
                  ? cn('text-white shadow-md ring-1 ring-white/15', { 'bg-indigo-600': accentColor === 'indigo', 'bg-emerald-600': accentColor === 'emerald', 'bg-rose-600': accentColor === 'rose', 'bg-amber-600': accentColor === 'amber', 'bg-violet-600': accentColor === 'violet' })
                  : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
              )}
            >
              <Icon className={cn('w-4 h-4 shrink-0 transition-transform group-hover:scale-110', isActive ? 'text-white' : 'text-slate-400')} />
              <span>{tab.name}</span>
              {tab.badge && (
                <span
                  className={cn(
                    'text-[9px] px-1.5 py-0.5 rounded-md font-mono font-bold tracking-tight transition-colors',
                    isActive
                      ? 'bg-white/20 text-white'
                      : 'bg-white/[0.06] text-slate-400 group-hover:text-slate-200'
                  )}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Vertical Divider */}
      <div className="h-5 w-px bg-white/10 shrink-0 mx-0.5 hidden sm:block z-10" />

      {/* Tools Group */}
      <div className="flex flex-wrap items-center gap-1 z-10">
        {toolTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;

          return (
            <button
              key={tab.id}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onSelectTab(tab.id)}
              className={cn(
                'flex items-center gap-1.5 px-4 py-3 rounded-xl text-sm font-bold font-outfit transition-colors duration-200 active:scale-95 group shrink-0 whitespace-nowrap cursor-pointer',
                isActive
                  ? cn('text-white shadow-md ring-1 ring-white/15', { 'bg-indigo-600': accentColor === 'indigo', 'bg-emerald-600': accentColor === 'emerald', 'bg-rose-600': accentColor === 'rose', 'bg-amber-600': accentColor === 'amber', 'bg-violet-600': accentColor === 'violet' })
                  : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
              )}
            >
              <Icon className={cn('w-4 h-4 shrink-0 transition-transform group-hover:scale-110', isActive ? 'text-white' : 'text-slate-400')} />
              <span>{tab.name}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
