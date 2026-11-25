'use strict';
const local = location.origin === 'http://127.0.0.1:8765';
const restLine = [0, 0.01];
const hardware = {token:null, origin:0, passes:[], slots:[null,null]};
function hardwarePhase(){return ((performance.now()-hardware.origin)/(seconds*1000))%1}
function rebuildPasses(){
  const passes=[];
  strokes.forEach((stroke, i)=>{
    let start=0, direction=0;
    function add(stop){
      const pts=stroke.points.slice(start,stop);
      if(pts[0][0]>pts.at(-1)[0])pts.reverse();
      passes.push({id:i+'/'+start,pts,ink:stroke.ink});
    }
    for(let j=1;j<stroke.points.length;j++){
      const sign=Math.sign(stroke.points[j][0]-stroke.points[j-1][0]);
      if(sign && direction && sign!==direction){add(j);start=j-1}
      if(sign)direction=sign;
    }
    add(stroke.points.length);
  });
  hardware.passes=passes;
}
function hardwareNotes(x){
  const voices=[];
  for(const pass of hardware.passes){
    const pts=pass.pts;
    if(x<pts[0][0] || x>=Math.max(pts.at(-1)[0],pts[0][0]+.04/seconds))continue;
    let lo=0,hi=pts.length;
    while(lo+1<hi){const mid=(lo+hi)>>1;if(pts[mid][0]<=x)lo=mid;else hi=mid}
    const [a,b]=pts[lo], [c,d]=pts[lo+1]||pts[lo];
    const y=c>a?b+(d-b)*clamp((x-a)/(c-a)):b;
    voices.push({id:pass.id,note:[pass.ink,Math.round(freq(y)*10)/10]});
    if(voices.length===2)break;
  }
  const ids=voices.map(v=>v.id);
  hardware.slots=hardware.slots.map(id=>ids.includes(id)?id:null);
  for(const id of ids)if(!hardware.slots.includes(id))hardware.slots[hardware.slots.indexOf(null)]=id;
  return hardware.slots.map(id=>voices.find(v=>v.id===id)?.note ?? restLine);
}
async function post(path,data){
  const r=await fetch('/'+path,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data),signal:AbortSignal.timeout(5000)});
  const result=await r.json();if(!r.ok)throw Error(result.error||'Bridge unavailable');return result;
}
function outputUI(){
  const usb=$('output').value==='utg';
  $('setup').hidden=!usb||local;$('play').disabled=usb&&!local;
}
if(local)$('output').value='utg';
$('output').onchange=outputUI;outputUI();
async function stopHardware(){
  const token=hardware.token;if(!token)return;
  hardware.token=null;$('play').disabled=true;
  try{await post('stop',{token})}catch(e){$('error').textContent=e.message}
  finally{$('play').textContent='▶ Play';$('output').disabled=false;outputUI();render()}
}
async function hardwarePlay(){
  if(hardware.token){await stopHardware();return}
  if(!local)return;
  $('play').disabled=$('output').disabled=true;
  try{
    const {token}=await post('start',{});hardware.token=token;
    hardware.origin=performance.now();hardware.slots=[null,null];rebuildPasses();
    $('play').disabled=false;$('play').textContent='■ Stop';animate();
    async function tick(){
      if(hardware.token!==token)return;
      try{
        await post('frame',{token,notes:hardwareNotes(hardwarePhase())});
        if(hardware.token===token)setTimeout(tick,25);
      }catch(e){if(hardware.token===token){await stopHardware();$('error').textContent=e.message}}
    }
    tick();
  }catch(e){$('error').textContent=e.message;$('output').disabled=false;outputUI()}
}
window.addEventListener('pagehide',()=>{
  if(hardware.token)navigator.sendBeacon('/stop',JSON.stringify({token:hardware.token}));
});
