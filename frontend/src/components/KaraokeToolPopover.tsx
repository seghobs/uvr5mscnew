'use client';

import { useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import { createPortal } from 'react-dom';

/** Keep tool menus outside the scrolling toolbar without changing its height. */
export function KaraokeToolPopover({ anchor, children, width, onClose }: {
  anchor: RefObject<HTMLDivElement | null>;
  children: ReactNode;
  width: number;
  onClose: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 8, top: 8, maxHeight: 360, width });
  useLayoutEffect(() => {
    const place = () => {
      const rect = anchor.current?.getBoundingClientRect();
      if (!rect) return;
      const menuWidth = Math.min(width, window.innerWidth - 16);
      const below = window.innerHeight - rect.bottom - 16;
      const above = rect.top - 16;
      const upwards = below < 240 && above > below;
      const maxHeight = Math.max(80, Math.min(380, upwards ? above : below));
      const height = Math.min(panel.current?.scrollHeight || maxHeight, maxHeight);
      setPosition({ left: Math.max(8, Math.min(rect.left, window.innerWidth - menuWidth - 8)), top: upwards ? Math.max(8, rect.top - height - 8) : rect.bottom + 8, maxHeight, width: menuWidth });
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [anchor, width]);

  return createPortal(<div ref={panel} data-karaoke-tool-popover style={position}
    onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); anchor.current?.querySelector('button')?.focus(); } }}
    className="fixed z-[100000] overflow-y-auto overscroll-contain rounded-2xl border border-white/15 bg-[#262230] p-2.5 text-left shadow-2xl custom-scrollbar">
    {children}
  </div>, document.body);
}
