export function parseSongMetadata(source:string):{artist:string;title:string} {
  const clean=source.replace(/\.(wav|mp3|flac|ogg|m4a|webm)$/i,'').replace(/\s*#.*$/,'')
    .replace(/\s*\((?:official[^)]*|lyrics[^)]*|audio|video|hd|4k)\)/gi,'')
    .replace(/\s+Official\s+(?:Audio|Video).*$/i,'').trim();
  const reverse=clean.match(/^(.+?)\s*\(([^()]+)\)\s*$/);
  if(reverse)return {title:reverse[1].trim(),artist:reverse[2].trim()};
  const parts=clean.split(/\s+[-–—]\s+/);
  if(parts.length>=2)return {artist:parts[0].trim(),title:parts.slice(1).join(' - ').replace(/\s*\[.*?\]\s*/g,' ').trim()};
  return {artist:'',title:clean};
}
