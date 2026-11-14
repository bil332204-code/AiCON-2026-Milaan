// Landing page motion: one orchestrated hero sequence (headline, two documents turning toward each
// other in 3D, the matching rows lighting up, a connecting line and the verdict), a gentle pointer
// tilt on desktop, and quiet section reveals. With reduced motion everything is shown in its final state.
const root=document.documentElement,body=document.body;
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),fine=matchMedia('(hover: hover) and (pointer: fine)');
const hero=document.querySelector('.hero'),stage=document.getElementById('hero-stage'),rig=document.getElementById('stage-rig'),path=document.getElementById('match-path');
const controller=new AbortController(),signal=controller.signal;

// Split the headline into words so they can rise in order. Screen readers get the sentence once.
const heading=hero?.querySelector('h1');
if(heading&&!heading.querySelector('.headline-word')){
  const text=heading.textContent.trim();heading.setAttribute('aria-label',text);heading.textContent='';
  text.split(/\s+/).forEach((word,index,all)=>{const span=document.createElement('span');span.className='headline-word';span.setAttribute('aria-hidden','true');span.style.setProperty('--word',index);span.textContent=word;heading.append(span);if(index<all.length-1)heading.append(' ');});
}

// Draw the connector from the receipt's Transaction ID to the matching statement row.
function drawLine(){
  if(!stage||!path)return;
  const from=stage.querySelector('.receipt-ref'),to=stage.querySelector('.doc-row-match span:nth-child(2)');if(!from||!to)return;
  const box=stage.getBoundingClientRect(),a=from.getBoundingClientRect(),b=to.getBoundingClientRect();
  const x1=a.right-box.left,y1=a.top+a.height/2-box.top,x2=b.left-box.left-8,y2=b.top+b.height/2-box.top;
  const bend=Math.max(40,Math.abs(x2-x1)*.6);
  path.setAttribute('d',`M${x1.toFixed(1)} ${y1.toFixed(1)} C${(x1+bend).toFixed(1)} ${y1.toFixed(1)} ${(x2-bend).toFixed(1)} ${y2.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`);
  const length=Math.ceil(path.getTotalLength?.()||600);path.style.setProperty('--path-length',length);
}

const timers=[];
function later(fn,ms){timers.push(setTimeout(fn,ms));}
function finalState(){hero?.classList.add('entered');stage?.classList.add('entered','matched');drawLine();}

function play(){
  if(!stage||!hero)return;
  if(reduced.matches){finalState();return;}
  root.classList.add('js-motion');
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    hero.classList.add('entered');stage.classList.add('entered');
    // Measure once the documents have settled so the line lands on the real rows.
    later(()=>{drawLine();stage.classList.add('matched');},1350);
  }));
}

// Pointer tilt: small, eased, and only on devices with a precise pointer.
let frame=0,target={x:0,y:0};
function applyTilt(){frame=0;if(!rig)return;rig.style.setProperty('--tilt-x',target.y.toFixed(2)+'deg');rig.style.setProperty('--tilt-y',target.x.toFixed(2)+'deg');}
if(stage&&rig){
  stage.addEventListener('pointermove',event=>{
    if(reduced.matches||!fine.matches||event.pointerType!=='mouse')return;
    const r=stage.getBoundingClientRect();target={x:((event.clientX-r.left)/r.width-.5)*8,y:-((event.clientY-r.top)/r.height-.5)*6};
    if(!frame)frame=requestAnimationFrame(applyTilt);
  },{passive:true,signal});
  stage.addEventListener('pointerleave',()=>{target={x:0,y:0};if(!frame)frame=requestAnimationFrame(applyTilt);},{signal});
  // The line follows the documents, so redraw after tilt transitions and on resize.
  rig.addEventListener('transitionend',event=>{if(event.target===rig&&stage.classList.contains('matched'))drawLine();},{signal});
}
let resizeTimer=0;
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(drawLine,120);},{passive:true,signal});
document.fonts?.ready.then(()=>{if(stage?.classList.contains('matched'))drawLine();});

// Header gets a hairline once the page scrolls.
function onScroll(){body.classList.toggle('scrolled',scrollY>8);}
window.addEventListener('scroll',onScroll,{passive:true,signal});onScroll();

// Section reveals: each block fades in once, the first time it comes into view.
const blocks=[...document.querySelectorAll('#landing .reveal')];
let observer=null;
if(reduced.matches||!('IntersectionObserver' in window)){blocks.forEach(block=>block.classList.add('is-visible'));}
else{
  observer=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;entry.target.classList.add('is-visible');observer.unobserve(entry.target);}},{rootMargin:'0px 0px -8% 0px',threshold:.12});
  blocks.forEach(block=>observer.observe(block));
}
reduced.addEventListener('change',()=>{if(reduced.matches){root.classList.remove('js-motion');blocks.forEach(block=>block.classList.add('is-visible'));finalState();if(rig){rig.style.removeProperty('--tilt-x');rig.style.removeProperty('--tilt-y');}}},{signal});

// Scenario tabs: roving tabindex and labelling. app.js renders the panel and handles arrow keys.
const tablist=document.querySelector('.scenario-tabs'),panel=document.getElementById('scenario-stage');
if(tablist&&panel){
  const tabs=[...tablist.querySelectorAll('[role="tab"]')];
  const syncTabs=()=>{tabs.forEach((tab,index)=>{tab.id='scenario-tab-'+index;tab.setAttribute('aria-controls',panel.id);tab.tabIndex=tab.getAttribute('aria-selected')==='true'?0:-1;});const active=tabs.find(tab=>tab.getAttribute('aria-selected')==='true');if(active)panel.setAttribute('aria-labelledby',active.id);};
  tablist.addEventListener('click',()=>queueMicrotask(syncTabs),{signal});
  tablist.addEventListener('keydown',event=>{
    if(event.key==='Home'||event.key==='End'){event.preventDefault();const tab=event.key==='Home'?tabs[0]:tabs[tabs.length-1];tab.click();tab.focus();}
    queueMicrotask(syncTabs);
  },{signal});
  syncTabs();
}

// Replay the hero when the landing page is shown again after the workspace.
const landing=document.getElementById('landing');
if(landing){new MutationObserver(()=>{if(!landing.hidden)requestAnimationFrame(drawLine);}).observe(landing,{attributes:true,attributeFilter:['hidden']});}

play();
window.addEventListener('pagehide',event=>{if(event.persisted)return;controller.abort();observer?.disconnect();timers.forEach(clearTimeout);cancelAnimationFrame(frame);},{once:true});
