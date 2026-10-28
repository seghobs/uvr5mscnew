import {api} from './api';
import {flushAllProjects, flushProjects, projectStorage} from './project-storage';
import type {LibraryItem, LyricSegment} from './types';

type Lyrics = {language:string;segments:LyricSegment[]};
export type ProjectArchive = LibraryItem & {
  archive_version?:2;
  karaoke?:Record<string,Lyrics>;
  project_values?:Record<string,string|null>;
};

function belongsToProject(key:string, stems:string[]):boolean {
  return stems.some(stem =>
    ['uvr-stem-settings:','uvr-history:','uvr-lyrics-draft:','uvr-video-heading:','uvr-video-cover:','uvr-alignment-language:'].some(prefix=>key===prefix+stem) ||
    ['uvr-passages-v2:','uvr-passages-v3:'].some(prefix=>key.startsWith(prefix+stem+':')));
}

export async function exportProjectArchive(item:LibraryItem):Promise<ProjectArchive> {
  await flushAllProjects();
  const karaoke:Record<string,Lyrics>={};
  for(const stem of item.stems){
    try{
      const saved=await api.getSavedLyrics(stem);
      // Both instrumental/vocal endpoints can refer to the same saved lyrics.
      const owner=saved.file_name&&item.stems.includes(saved.file_name)?saved.file_name:stem;
      karaoke[owner]={language:saved.language||'auto',segments:saved.segments};
    }catch(error){if((error as {status?:number}).status!==404)throw error;}
  }
  const project_values:Record<string,string|null>={};
  for(const key of projectStorage.keys())if(belongsToProject(key,item.stems))project_values[key]=projectStorage.getItem(key);
  return {...item,archive_version:2,karaoke,project_values};
}

export async function importProjectArchive(value:unknown):Promise<LibraryItem> {
  const archive=value as ProjectArchive;
  if(!archive || !Number.isFinite(archive.id) || typeof archive.filename!=='string' || !archive.filename ||
    !Array.isArray(archive.stems) || !archive.stems.every(stem=>typeof stem==='string'&&!!stem))throw Error('Geçersiz proje formatı');
  if(archive.archive_version!==undefined&&archive.archive_version!==2)throw Error('Desteklenmeyen proje sürümü');
  const lyrics=archive.karaoke||{}, values=archive.project_values||{};
  if(typeof lyrics!=='object'||Array.isArray(lyrics)||typeof values!=='object'||Array.isArray(values))throw Error('Geçersiz proje verileri');
  for(const [file,saved] of Object.entries(lyrics)){
    if(!archive.stems.includes(file)||!saved||typeof saved.language!=='string'||!Array.isArray(saved.segments))throw Error('Geçersiz karaoke kaydı');
    for(const row of saved.segments)if(!row||typeof row.text!=='string'||![row.start,row.end].every(Number.isFinite)||
      (row.words!==undefined&&(!Array.isArray(row.words)||row.words.some(w=>!w||typeof w.word!=='string'||![w.start,w.end].every(Number.isFinite)))))throw Error('Geçersiz karaoke satırı');
  }
  for(const [key,entry] of Object.entries(values))if(!belongsToProject(key,archive.stems)||(entry!==null&&typeof entry!=='string'))throw Error('Proje dosyası başka bir projeye ait ayar içeriyor');
  await flushAllProjects();
  for(const [file,saved] of Object.entries(lyrics))await api.saveLyrics(file,saved.segments,saved.language);
  for(const [key,entry] of Object.entries(values)){
    if(entry===null)projectStorage.removeItem(key);else projectStorage.setItem(key,entry);
  }
  await flushProjects();
  const {archive_version:_,karaoke:__,project_values:___,...item}=archive;
  return item;
}
