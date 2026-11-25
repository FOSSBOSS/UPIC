'use strict';
const $ = id => document.getElementById(id);
const canvas = $('score'), pen = canvas.getContext('2d');
const brushes = [
  {name:'Pure',color:'#f2f0e7'},
  {name:'Tremolo',color:'#68b6ff'},
  {name:'Vibrato',color:'#9ce7a5'},
  {name:'Bright FM',color:'#c29afa'}
];
let active=0, strokes=[], drawing=null, pointer=null, seconds=8, audio, source, origin=0;
let w,h, ratio;
const left=52, topY=13, right=15, bottom=30;
const freq=y=>1760*Math.pow(2,-4*y);
const clamp=n=>Math.max(0,Math.min(1,n));
function pick(i){
  active=i;
  [...$('brushes').children].forEach((b,j)=>b.setAttribute('aria-pressed',String(i===j)));
}
brushes.forEach((brush,i)=>{
  const b=document.createElement('button');
  b.className='brush'; b.style.setProperty('--ink',brush.color);
  b.innerHTML='<b></b>'+brush.name; b.onclick=()=>pick(i); $('brushes').append(b);
});
pick(0);
function phase(){if(hardware.token)return hardwarePhase();return source?((audio.currentTime-origin)%seconds+seconds)%seconds/seconds:0}
function render(){
  const dx=w-left-right,dy=h-topY-bottom;
  pen.clearRect(0,0,w,h); pen.font='12px monospace'; pen.fillStyle='#b4b7be';
  function line(x,y,ex,ey,color,width=1){pen.beginPath();pen.moveTo(x,y);pen.lineTo(ex,ey);pen.strokeStyle=color;pen.lineWidth=width;pen.stroke()}
  for(let i=0;i<=16;i++){
    const y=topY+dy*i/16,x=left+dx*i/16;
    line(left,y,w-right,y,i%4?'#2a2c32':'#393c43');
    line(x,topY,x,h-bottom,i%4?'#2a2c32':'#393c43');
    if(i%4===0){
      pen.textAlign='right';pen.fillText(Math.round(freq(i/16))+'',left-8,y+4);
      pen.textAlign=i===16?'right':'center';pen.fillText(seconds*i/16+'s',x,h-9);
    }
  }
  pen.lineJoin='round';pen.lineCap='round';
  for(const s of strokes){
    pen.strokeStyle=brushes[s.ink].color;pen.lineWidth=3;pen.beginPath();
    for(const [x,y] of s.points)pen.lineTo(left+dx*x,topY+dy*y);
    if(s.points.length===1){const [x,y]=s.points[0];pen.lineTo(left+dx*x+.1,topY+dy*y)}
    pen.stroke();
  }
  const p=phase();if(source||hardware.token)line(left+p*dx,topY,left+p*dx,h-bottom,'#dcff94',2);
  $('clock').textContent=(p*seconds).toFixed(1)+' / '+seconds+' s';
  $('hint').hidden=strokes.length>0;
  $('undo').disabled=$('clear').disabled=!strokes.length;
}
new ResizeObserver(()=>{
  w=canvas.clientWidth;h=canvas.clientHeight;ratio=devicePixelRatio||1;
  canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);pen.setTransform(ratio,0,0,ratio,0,0);render();
}).observe(canvas);
function point(e){const r=canvas.getBoundingClientRect();return [clamp((e.clientX-r.left-left)/(w-left-right)),clamp((e.clientY-r.top-topY)/(h-topY-bottom))]}
canvas.onpointerdown=e=>{
  if(pointer!==null||e.button!==0)return;
  pointer=e.pointerId;canvas.setPointerCapture(pointer);drawing={ink:active,points:[point(e)]};strokes.push(drawing);render();
};
canvas.onpointermove=e=>{if(e.pointerId===pointer){drawing.points.push(point(e));render()}};
function finish(e){if(pointer!==e.pointerId)return;drawing=null;pointer=null;updateSound();render()}
canvas.onpointerup=canvas.onpointercancel=canvas.onlostpointercapture=finish;
// Render each horizontal pass as one voice, including strokes drawn right to left.
function makeBuffer(){
  const rate=24000, buf=audio.createBuffer(1,rate*seconds,rate), out=buf.getChannelData(0),tau=2*Math.PI;
  function voice(points,ink){
    if(points.length>1 && points[0][0]>points.at(-1)[0])points=points.slice().reverse();
    const first=Math.min(out.length-1,Math.round(points[0][0]*out.length));
    const end=Math.min(out.length,Math.max(first+960,Math.round(points.at(-1)[0]*out.length)));
    let j=0,angle=0;
    for(let k=first;k<end;k++){
      const x=k/out.length;
      while(j+1<points.length && points[j+1][0]<=x)j++;
      const [x0,y0]=points[j], [x1,y1]=points[j+1]||points[j];
      const hz=freq(y0+(y1-y0)*(x1>x0?clamp((x-x0)/(x1-x0)):0));
      const t=(k-first)/rate, slow=Math.sin(tau*5*t);
      const fm=ink===2?4*slow:ink===3?180*Math.sin(tau*110*t):0;
      angle+=tau*(hz+fm)/rate;
      const envelope=Math.min(1,(k-first)/120,(end-k)/180);
      out[k]+=.20*envelope*Math.sin(angle)*(ink===1?.65+.35*slow:1);
    }
  }
  for(const s of strokes){
    let start=0,dir=0;
    for(let j=1;j<s.points.length;j++){
      const sign=Math.sign(s.points[j][0]-s.points[j-1][0]);
      if(sign && dir && sign!==dir){voice(s.points.slice(start,j),s.ink);start=j-1}
      if(sign)dir=sign;
    }
    voice(s.points.slice(start),s.ink);
  }
  let peak=1;for(const n of out)peak=Math.max(peak,Math.abs(n));
  if(peak>1)for(let i=0;i<out.length;i++)out[i]/=peak;
  return buf;
}
function start(p=0){
  const buf=makeBuffer();if(source)source.stop();
  source=audio.createBufferSource();source.buffer=buf;source.loop=true;source.connect(audio.destination);
  const now=audio.currentTime;origin=now-p*seconds;source.start(now,p*seconds);
}
function updateSound(){rebuildPasses();if(source)start(phase())}
function animate(){render();if(source||hardware.token)requestAnimationFrame(animate)}
$('play').onclick=async()=>{
  $('error').textContent='';
  if($('output').value==='utg'){await hardwarePlay();return}
  if(source){source.stop();source=null;$('output').disabled=false;$('play').textContent='▶ Play';render();return}
  try{
    audio??=new AudioContext();await audio.resume();if(source)return;
    start();$('output').disabled=true;$('play').textContent='■ Stop';animate();
  }catch(e){$('error').textContent='Audio could not start. '+e.message}
};
$('duration').oninput=e=>{
  const p=phase();seconds=Number(e.target.value);$('length').value=seconds+' s';
  if(source)start(p);if(hardware.token)hardware.origin=performance.now()-p*seconds*1000;render();
};
function edit(clear){pointer=null;drawing=null;if(clear)strokes=[];else strokes.pop();updateSound();render()}
$('undo').onclick=()=>edit(false);$('clear').onclick=()=>edit(true);
