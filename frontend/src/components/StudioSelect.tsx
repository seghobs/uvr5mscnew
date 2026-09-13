'use client';

import React, {Children, isValidElement, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {Check, ChevronDown, Search} from 'lucide-react';
import {cn} from '@/lib/utils';

type Option = {value:string; label:string; disabled:boolean; group?:string};
function textOf(node:ReactNode):string {
  return Children.toArray(node).map(child=>isValidElement<{children?:ReactNode}>(child)?textOf(child.props.children):String(child)).join('');
}
export function selectOptions(children:ReactNode, group?:string, disabled=false):Option[] {
  return Children.toArray(children).flatMap(child=>{
    if(!isValidElement<{value?:string|number;children?:ReactNode;label?:string;disabled?:boolean}>(child))return [];
    const props=child.props;
    if(child.type==='option')return [{value:String(props.value??textOf(props.children)),label:props.label??textOf(props.children),disabled:disabled||!!props.disabled,group}];
    return selectOptions(props.children,child.type==='optgroup'?props.label:group,disabled||!!props.disabled);
  });
}

export function StudioSelect({value,onValueChange,children,className,disabled=false,id,'aria-label':label='Seçenek seç', 'aria-labelledby':labelledBy}: {
  value:string|number;onValueChange:(value:string)=>void;children:ReactNode;className?:string;disabled?:boolean;id?:string;
  'aria-label'?:string;'aria-labelledby'?:string;
}) {
  const options=selectOptions(children);
  const selected=options.find(option=>option.value===String(value));
  const [open,setOpen]=useState(false),[query,setQuery]=useState(''),[active,setActive]=useState(-1);
  const trigger=useRef<HTMLButtonElement>(null),panel=useRef<HTMLDivElement>(null),search=useRef<HTMLInputElement>(null);
  const listId=useId();
  const [position,setPosition]=useState({left:8,top:8,width:240,maxHeight:320});
  const fold=(text:string)=>text.toLocaleLowerCase('tr-TR');
  const filtered=options.filter(option=>fold(`${option.label} ${option.group??''}`).includes(fold(query)));
  const close=(restore=false)=>{setOpen(false);if(restore)trigger.current?.focus();};
  const show=()=>{setQuery('');setActive(options.findIndex(option=>option.value===String(value)&&!option.disabled));setOpen(true);};
  const choose=(option:Option)=>{if(option.disabled)return;onValueChange(option.value);close(true);};
  useLayoutEffect(()=>{
    if(!open)return;
    const place=()=>{
      const rect=trigger.current?.getBoundingClientRect();if(!rect)return;
      const width=Math.min(Math.max(rect.width,240),window.innerWidth-16);
      const below=window.innerHeight-rect.bottom-16,above=rect.top-16;
      const upwards=below<240&&above>below;
      const maxHeight=Math.max(80,Math.min(340,upwards?above:below));
      const height=Math.min(panel.current?.scrollHeight||maxHeight,maxHeight);
      setPosition({width,maxHeight,left:Math.max(8,Math.min(rect.left,window.innerWidth-width-8)),top:upwards?Math.max(8,rect.top-height-8):rect.bottom+8});
    };
    place();search.current?.focus();
    const outside=(event:PointerEvent)=>{const target=event.target as Node;if(!panel.current?.contains(target)&&!trigger.current?.contains(target))setOpen(false);};
    const focusOutside=(event:FocusEvent)=>{const target=event.target as Node;if(!panel.current?.contains(target)&&!trigger.current?.contains(target))setOpen(false);};
    window.addEventListener('resize',place);window.addEventListener('scroll',place,true);
    document.addEventListener('pointerdown',outside);document.addEventListener('focusin',focusOutside);
    return ()=>{window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);document.removeEventListener('pointerdown',outside);document.removeEventListener('focusin',focusOutside);};
  },[open]);
  useEffect(()=>{if(disabled)setOpen(false);},[disabled]);
  useEffect(()=>{if(open)document.getElementById(`${listId}-${active}`)?.scrollIntoView({block:'nearest'});},[active,open,listId]);
  const navigate=(direction:number)=>{
    const origin=active<0?(direction>0?-1:0):active;
    for(let offset=1;offset<=filtered.length;offset++){
      const index=(origin+direction*offset+filtered.length)%filtered.length;
      if(!filtered[index].disabled){setActive(index);break;}
    }
  };
  return <>
    <button ref={trigger} id={id} type="button" role="combobox" aria-label={label} aria-labelledby={labelledBy} aria-expanded={open} aria-haspopup="listbox" aria-controls={open?listId:undefined} disabled={disabled}
      data-studio-select onClick={event=>{event.stopPropagation();if(open)close();else show();}}
      onKeyDown={event=>{if(['ArrowDown','ArrowUp','Enter',' '].includes(event.key)){event.preventDefault();event.stopPropagation();show();}}}
      className={cn(className,'inline-flex items-center justify-between gap-3 rounded-2xl border border-white/20 bg-[#17141f] px-3 py-2.5 text-left text-xs text-slate-200 shadow-inner transition-colors hover:border-violet-300/40 disabled:cursor-not-allowed disabled:opacity-40')}>
      <span className="min-w-0 flex-1 truncate">{selected?.label||'Seçenek seç'}</span><ChevronDown size={15} className={cn('shrink-0 text-slate-400 transition-transform',open&&'rotate-180')}/>
    </button>
    {open&&!disabled&&createPortal(<div ref={panel} data-studio-select data-karaoke-tool-popover style={position}
      className="fixed z-[100001] flex flex-col overflow-hidden rounded-2xl border border-white/25 bg-[#292333]/95 p-2.5 text-left text-slate-200 shadow-[0_20px_50px_#0009] backdrop-blur-2xl"
      onClick={event=>event.stopPropagation()}
      onKeyDown={event=>{
        event.stopPropagation();
        if(event.key==='Escape'){event.preventDefault();close(true);}
        if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();navigate(event.key==='ArrowDown'?1:-1);}
        if(event.key==='Enter'){event.preventDefault();const option=filtered[active]??filtered.find(item=>!item.disabled);if(option)choose(option);}
        if(event.key==='Tab'){close(true);}
      }}>
      <div className="mb-2 flex shrink-0 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2">
        <Search size={14} className="text-slate-400"/><input ref={search} aria-label={`${label}: ara`} role="combobox" aria-expanded="true" aria-controls={listId} aria-autocomplete="list" aria-activedescendant={active>=0&&filtered[active]?`${listId}-${active}`:undefined}
          placeholder="Ara…" value={query} onChange={event=>{setQuery(event.target.value);setActive(-1);}} className="min-w-0 w-full bg-transparent text-xs text-white placeholder:text-slate-400 outline-none"/>
      </div>
      <div id={listId} role="listbox" aria-label={label} className="min-h-0 overflow-y-auto overscroll-contain custom-scrollbar">
        {filtered.map((option,index)=><React.Fragment key={`${option.group??''}:${option.value}:${index}`}>
          {option.group&&option.group!==filtered[index-1]?.group&&<div className="px-3 pb-1 pt-3 text-[10px] font-semibold tracking-wider text-violet-300">{option.group}</div>}
          <div id={`${listId}-${index}`} role="option" aria-selected={option.value===String(value)} aria-disabled={option.disabled} onMouseMove={()=>{if(!option.disabled)setActive(index);}} onMouseDown={event=>event.preventDefault()} onClick={()=>choose(option)}
            className={cn('my-1 flex cursor-pointer items-center justify-between gap-2 rounded-xl border border-transparent px-3 py-3 text-xs transition-colors',option.value===String(value)&&'border-violet-400/30 bg-violet-400/15 font-semibold text-violet-100',active===index&&'bg-white/10',option.disabled&&'cursor-not-allowed opacity-40')}>
            <span className="min-w-0 break-words">{option.label}</span>{option.value===String(value)&&<Check size={15} className="shrink-0 text-violet-300"/>}
          </div>
        </React.Fragment>)}
        {!filtered.length&&<p className="p-3 text-xs text-slate-400">Sonuç bulunamadı.</p>}
      </div>
    </div>,document.body)}
  </>;
}
