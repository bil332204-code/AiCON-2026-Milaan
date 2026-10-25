const canvas=document.getElementById('orb-canvas'),ctx=canvas.getContext('2d'),art=document.getElementById('hero-art'),tilt=document.getElementById('scene-tilt'),button=document.getElementById('motion-toggle');
const media=matchMedia('(prefers-reduced-motion: reduce)');
const economical=matchMedia('(max-width: 760px)').matches || navigator.connection?.saveData===true;
let paused=media.matches,visible=true,frame=0,t=0,last=0,w=500,h=540,px=0,py=0;
try{if(sessionStorage.getItem('milaan-motion')==='off')paused=true;}catch{}
function motion(){document.body.classList.toggle('motion-paused',paused);button.setAttribute('aria-pressed',String(paused));button.setAttribute('aria-label',paused?'Resume animation':'Pause animation');button.querySelector('.motion-text').textContent=paused?'Motion off':'Motion on';if(paused)cancelAnimationFrame(frame);draw();if(!paused)start();}
button.addEventListener('click',()=>{paused=!paused;try{sessionStorage.setItem('milaan-motion',paused?'off':'on');}catch{}motion();});
media.addEventListener('change',()=>{paused=media.matches;motion();});
function resize(){if(!ctx)return;const r=art.getBoundingClientRect();if(r.width<1)return;w=r.width;h=r.height;const dpr=Math.min(devicePixelRatio||1,economical?1.5:2);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.width=w+'px';canvas.style.height=h+'px';ctx.setTransform(dpr,0,0,dpr,0,0);draw();}
function project(x,y,z,a,b){let xx=x*Math.cos(a)+z*Math.sin(a),zz=-x*Math.sin(a)+z*Math.cos(a),yy=y*Math.cos(b)-zz*Math.sin(b);zz=y*Math.sin(b)+zz*Math.cos(b);const f=550/(550+zz);return {x:w*.52+xx*f,y:h*.49+yy*f,z:zz,f};}
function draw(){
 if(!ctx||w<1)return;ctx.clearRect(0,0,w,h);const radius=Math.min(w*.39,h*.42),a=t*.09+px*.1,b=.83+Math.sin(t*.16)*.10+py*.05,points=[];
 const glow=ctx.createRadialGradient(w*.53,h*.45,0,w*.53,h*.45,radius*1.3);glow.addColorStop(0,'rgba(125,90,225,.08)');glow.addColorStop(.6,'rgba(78,140,102,.025)');glow.addColorStop(1,'rgba(20,60,39,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
 const resolution=economical?75:135;
 for(let band=0;band<9;band++)for(let i=0;i<resolution;i++){
  const u=i/resolution*Math.PI*2,rr=radius+(band-4)*2.7,z=Math.sin(u*2+t*.16+band*.055)*21;
  const p=project(Math.cos(u)*rr,Math.sin(u)*rr,z,a,b);points.push({...p,size:(band===4?1.15:.55)*p.f,alpha:(band===4?.55:.22)*(1-(p.z+radius)/(radius*3))});
 }
 const backgroundPoints=economical?56:94;
 for(let i=0;i<backgroundPoints;i++){const u=i/backgroundPoints*Math.PI*2,rr=radius*.91,p=project(Math.cos(u)*rr,Math.sin(u)*rr,0,-a*.65+.8,-.62);points.push({...p,size:.8*p.f,alpha:.2});}
 points.sort((a,b)=>b.z-a.z);for(const p of points){ctx.fillStyle=`rgba(155,174,255,${Math.max(.045,p.alpha)})`;ctx.beginPath();ctx.arc(p.x,p.y,Math.max(.3,p.size),0,Math.PI*2);ctx.fill();}
 for(let j=0;j<3;j++){const u=t*.19+j*2.1,p=project(Math.cos(u)*radius,Math.sin(u)*radius,0,a,b);const g=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,13);g.addColorStop(0,'rgba(132,245,221,.7)');g.addColorStop(.15,'rgba(130,193,255,.45)');g.addColorStop(1,'rgba(135,100,245,0)');ctx.fillStyle=g;ctx.fillRect(p.x-13,p.y-13,26,26);}
}
function tick(now){if(paused||!visible||document.hidden||document.getElementById('landing').hidden){frame=0;return;}if(now-last>(economical?32:25)){t+=Math.min((now-last)/1000,.06);last=now;draw();}frame=requestAnimationFrame(tick);}
function start(){if(frame)cancelAnimationFrame(frame);last=performance.now();if(!paused&&visible&&!document.hidden&&!document.getElementById('landing').hidden)frame=requestAnimationFrame(tick);}
art.addEventListener('pointermove',e=>{if(paused||e.pointerType==='touch')return;const r=art.getBoundingClientRect();px=(e.clientX-r.left)/r.width-.5;py=(e.clientY-r.top)/r.height-.5;tilt.style.setProperty('--ry',`${px*12-9}deg`);tilt.style.setProperty('--rx',`${-py*8+3}deg`);});
art.addEventListener('pointerleave',()=>{px=py=0;tilt.style.setProperty('--ry','-9deg');tilt.style.setProperty('--rx','3deg');});
new ResizeObserver(resize).observe(art);
new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible)start();else cancelAnimationFrame(frame);},{threshold:.05}).observe(art);
document.addEventListener('visibilitychange',start);document.addEventListener('milaan-visibility',()=>{resize();start();});
const observer=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('revealed');observer.unobserve(e.target);}});},{threshold:.12});document.querySelectorAll('.reveal').forEach(el=>observer.observe(el));document.body.classList.add('js-motion');resize();motion();
