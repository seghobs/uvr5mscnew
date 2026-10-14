// Distinct 100 Hz bands, matching the export's 0–8 kHz visual spectrum.
// Skip DC and work with unclipped float dB values instead of byte saturation.
export function velocityLevels(db:Float32Array,sampleRate:number,fftSize:number):number[] {
  const hzPerBin=sampleRate/fftSize;
  return Array.from({length:80},(_,i)=>{
    const first=Math.max(1,Math.ceil(Math.max(40,i*100)/hzPerBin));
    const last=Math.min(db.length,Math.ceil((i+1)*100/hzPerBin));
    let peak=0;
    for(let j=first;j<last;j++)if(Number.isFinite(db[j]))peak=Math.max(peak,Math.pow(10,db[j]/20));
    return Math.min(1,Math.cbrt(2*peak));
  });
}
