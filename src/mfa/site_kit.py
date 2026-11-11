"""Shared pieces for the decision page: page skeleton, styles and a small dependency-free chart library.

The page is one self-contained HTML file: the result tables are embedded as JSON and the charts are drawn with plain SVG,
so it works offline, needs no build step to view, and can be published as-is (for example with GitHub Pages).
"""
import json

CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--panel:#ffffff;--text:#0b0b0b;--text2:#52514e;--muted:#8a8883;--grid:#e6e5e1;--line:#d9d8d3;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#6250d6;--s8:#e34948;
--seq0:#cde2fb;--seq1:#104281;--bad:#c2372f;--good:#0a7a4f;--soft:#f3f2ef}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#141413;--panel:#1a1a19;--text:#f0efec;
--text2:#c3c2b7;--muted:#8d8c85;--grid:#2c2c2a;--line:#3a3a37;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;
--s7:#9085e9;--s8:#e66767;--seq0:#184f95;--seq1:#9ec5f4;--bad:#ee7a73;--good:#3dbb88;--soft:#222221}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#141413;--panel:#1a1a19;--text:#f0efec;--text2:#c3c2b7;--muted:#8d8c85;--grid:#2c2c2a;
--line:#3a3a37;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;--seq0:#184f95;
--seq1:#9ec5f4;--bad:#ee7a73;--good:#3dbb88;--soft:#222221}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
header.hero{padding:44px 0 28px;border-bottom:1px solid var(--line)}
.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--text2);margin:0 0 10px}
h1{font-size:clamp(26px,4.4vw,40px);line-height:1.15;margin:0 0 14px;letter-spacing:-.01em}
h2{font-size:clamp(20px,3vw,26px);margin:0 0 6px;letter-spacing:-.005em}
h3{font-size:17px;margin:0 0 4px}
.lede{font-size:18px;color:var(--text2);max-width:760px;margin:0}
section{padding:40px 0;border-bottom:1px solid var(--line)}
section:last-of-type{border-bottom:0}
.kicker{color:var(--text2);margin:0 0 22px;max-width:760px}
.decision{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--s1);border-radius:10px;padding:22px 24px;margin-top:26px}
.decision h2{margin-bottom:8px}
.decision ol{margin:10px 0 0;padding-left:20px}.decision li{margin:7px 0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-top:20px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat b{display:block;font-size:28px;line-height:1.1;letter-spacing:-.01em}
.stat span{display:block;color:var(--text2);font-size:13px;margin-top:4px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 18px 12px;margin:0 0 18px}
.card .note{color:var(--text2);font-size:14px;margin:6px 0 0}
.chart{width:100%;position:relative}.chart svg{display:block;width:100%;height:auto;overflow:visible}
svg text{font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;fill:var(--text2)}
svg text.val{fill:var(--text)}svg text.strong{fill:var(--text);font-weight:600}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:0 0 8px;font-size:13px;color:var(--text2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.pipe{display:flex;flex-wrap:wrap;align-items:stretch;gap:0;margin:6px 0 4px}
.pipe .step{flex:1 1 150px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:150px;margin:0 0 8px}
.pipe .step b{display:block;font-size:13px;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.pipe .step strong{display:block;font-size:22px;margin:3px 0}
.pipe .step span{font-size:13px;color:var(--text2)}
.pipe .arrow{flex:0 0 22px;align-self:center;text-align:center;color:var(--muted);font-size:18px;margin:0 0 8px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--text2);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tablewrap{overflow-x:auto}
.mess td:first-child{font-weight:600;min-width:170px}.mess td:nth-child(2){font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;font-size:12px;border-radius:999px;padding:2px 9px;background:var(--soft);color:var(--text2)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:760px){.chart{overflow-x:auto;-webkit-overflow-scrolling:touch}.chart svg{min-width:620px}.two{grid-template-columns:1fr}.pipe .arrow{display:none}.pipe .step{flex-basis:100%}}
.limits li{margin:6px 0;color:var(--text2)}.limits li b{color:var(--text)}
footer{padding:28px 0 60px;color:var(--text2);font-size:14px}
a{color:var(--s1)}
#tip{position:fixed;display:none;pointer-events:none;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px;
padding:8px 10px;font-size:13px;box-shadow:0 4px 18px rgba(0,0,0,.15);z-index:20;max-width:300px}
#tip b{display:block;margin-bottom:2px}#tip .r{display:flex;justify-content:space-between;gap:14px}
#tip .r i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}
"""

JS = r"""
const NS='http://www.w3.org/2000/svg';
const $=(s,r=document)=>r.querySelector(s);
function svg(tag,attrs,parent){const e=document.createElementNS(NS,tag);const st=[];
 for(const k in (attrs||{})){const v=attrs[k];if(k==='fill'||k==='stroke'||k==='style')st.push(k==='style'?v:k+':'+v);else e.setAttribute(k,v);}
 if(st.length)e.setAttribute('style',st.join(';'));if(parent)parent.appendChild(e);return e;}
function text(parent,x,y,s,attrs){const t=svg('text',Object.assign({x,y},attrs||{}),parent);t.textContent=s;return t;}
const tipEl=document.getElementById('tip');
function showTip(ev,html){tipEl.innerHTML=html;tipEl.style.display='block';const r=tipEl.getBoundingClientRect();
 let x=ev.clientX+14,y=ev.clientY+14;if(x+r.width>innerWidth-8)x=ev.clientX-r.width-14;if(y+r.height>innerHeight-8)y=ev.clientY-r.height-14;
 tipEl.style.left=Math.max(4,x)+'px';tipEl.style.top=Math.max(4,y)+'px';}
function hideTip(){tipEl.style.display='none';}
function lin(d0,d1,r0,r1){return v=>r0+(v-d0)*(r1-r0)/((d1-d0)||1);}
function niceMax(v){const e=Math.pow(10,Math.floor(Math.log10(v||1)));for(const m of [1,1.5,2,2.5,3,4,5,6,8,10]){if(m*e>=v)return m*e;}return 10*e;}
function ticks(lo,hi,n){const span=hi-lo;const raw=span/n;const e=Math.pow(10,Math.floor(Math.log10(raw)));
 let st=e;for(const m of [1,2,2.5,5,10]){if(m*e>=raw){st=m*e;break;}}const out=[];for(let v=Math.ceil(lo/st)*st;v<=hi+1e-9;v+=st)out.push(+v.toFixed(6));return out;}
const fmt={int:v=>Math.round(v).toLocaleString('en-US'),pct:v=>(Math.round(v*10)/10)+'%',pct0:v=>Math.round(v)+'%',pp:v=>(v>0?'+':'')+(Math.round(v*100)/100)+' pp',
 lakh:v=>'₹'+(v/100000).toFixed(1)+' lakh',k:v=>(v/1000).toFixed(0)+'k'};
function mk(container,w,h){const el=typeof container==='string'?$(container):container;el.innerHTML='';
 const s=svg('svg',{viewBox:'0 0 '+w+' '+h,role:'img'},el);return s;}
function legend(container,items){const el=typeof container==='string'?$(container):container;const d=document.createElement('div');d.className='legend';
 d.innerHTML=items.map(i=>'<span><i style="background:'+i.color+'"></i>'+i.name+'</span>').join('');el.parentNode.insertBefore(d,el);}
function axisY(s,sc,tk,x0,x1,f){tk.forEach(t=>{const y=sc(t);svg('line',{x1:x0,x2:x1,y1:y,y2:y,stroke:'var(--grid)'},s);text(s,x0-8,y+4,f(t),{'text-anchor':'end'});});}

/* line chart: o={series:[{name,color,pts:[[x,y],...]}], x:[min,max], y:[min,max], xt:[ticks], yt:[ticks], yf, xf, xlab, ylab, step, h} */
function lineChart(sel,o){const W=760,H=o.h||340,m={l:56,r:136,t:30,b:44};const s=mk(sel,W,H);
 const sx=lin(o.x[0],o.x[1],m.l,W-m.r),sy=lin(o.y[0],o.y[1],H-m.b,m.t);
 axisY(s,sy,o.yt||ticks(o.y[0],o.y[1],5),m.l,W-m.r,o.yf||String);
 (o.xt||ticks(o.x[0],o.x[1],6)).forEach(t=>{text(s,sx(t),H-m.b+18,(o.xf||String)(t),{'text-anchor':'middle'});});
 svg('line',{x1:m.l,x2:W-m.r,y1:H-m.b,y2:H-m.b,stroke:'var(--muted)'},s);
 if(o.xlab)text(s,(m.l+W-m.r)/2,H-6,o.xlab,{'text-anchor':'middle'});
 if(o.ylab)text(s,m.l,12,o.ylab,{});
 o.series.forEach(se=>{let d='';se.pts.forEach((p,i)=>{const X=sx(p[0]),Y=sy(p[1]);
  d+=i===0?'M'+X+','+Y:(o.step?'H'+X+'V'+Y:'L'+X+','+Y);});
  svg('path',{d,fill:'none',stroke:se.color,'stroke-width':2,'stroke-linejoin':'round'},s);});
 const lab=o.series.map(se=>({se,y:sy(se.pts[se.pts.length-1][1])})).sort((a,b)=>a.y-b.y);
 for(let i=1;i<lab.length;i++){if(lab[i].y-lab[i-1].y<14)lab[i].y=lab[i-1].y+14;}
 const floor=H-m.b-2;if(lab.length&&lab[lab.length-1].y>floor){lab[lab.length-1].y=floor;for(let i=lab.length-2;i>=0;i--){if(lab[i].y>lab[i+1].y-14)lab[i].y=lab[i+1].y-14;}}
 lab.forEach(l=>{text(s,W-m.r+8,l.y+4,l.se.name,{class:'strong'});});
 const g=svg('g',{},s);const cur=svg('line',{y1:m.t,y2:H-m.b,stroke:'var(--muted)','stroke-dasharray':'3 3',style:'display:none'},g);
 const dots=o.series.map(se=>svg('circle',{r:4,fill:se.color,stroke:'var(--panel)','stroke-width':2,style:'display:none'},g));
 const ov=svg('rect',{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:'transparent'},s);
 ov.addEventListener('mousemove',ev=>{const r=s.getBoundingClientRect();const px=(ev.clientX-r.left)*W/r.width;
  let xv=o.x[0]+(px-m.l)*(o.x[1]-o.x[0])/(W-m.l-m.r);let best=null;
  o.series[0].pts.forEach(p=>{if(best===null||Math.abs(p[0]-xv)<Math.abs(best-xv))best=p[0];});
  cur.setAttribute('x1',sx(best));cur.setAttribute('x2',sx(best));cur.style.display='';
  let html='<b>'+(o.xf||String)(best)+(o.xunit||'')+'</b>';
  o.series.forEach((se,i)=>{const p=se.pts.find(q=>q[0]===best);if(!p){dots[i].style.display='none';return;}
   dots[i].setAttribute('cx',sx(p[0]));dots[i].setAttribute('cy',sy(p[1]));dots[i].style.display='';
   html+='<div class="r"><span><i style="background:'+se.color+'"></i>'+se.name+'</span><span>'+(o.yf||String)(p[1])+'</span></div>';});
  showTip(ev,html);});
 ov.addEventListener('mouseleave',()=>{hideTip();cur.style.display='none';dots.forEach(d=>d.style.display='none');});}

/* horizontal bars: o={rows:[{label,value,tip,color,sub}], max, vf, lw, color} */
function hbar(sel,o){const rows=o.rows,lw=o.lw||210,rh=o.rh||26,W=760,m={t:6,r:70,b:22},H=m.t+rows.length*rh+m.b;const s=mk(sel,W,H);
 const mx=o.max||niceMax(Math.max(...rows.map(r=>r.value))),sx=lin(0,mx,lw,W-m.r);
 ticks(0,mx,5).forEach(t=>{svg('line',{x1:sx(t),x2:sx(t),y1:m.t,y2:H-m.b,stroke:'var(--grid)'},s);text(s,sx(t),H-6,(o.tf||o.vf||String)(t),{'text-anchor':'middle'});});
 rows.forEach((r,i)=>{const y=m.t+i*rh;text(s,lw-8,y+rh/2+4,r.label,{'text-anchor':'end',class:r.bold?'strong':''});
  const b=svg('rect',{x:lw,y:y+4,width:Math.max(1,sx(r.value)-lw),height:rh-8,rx:3,fill:r.color||o.color||'var(--s1)'},s);
  text(s,sx(r.value)+6,y+rh/2+4,(o.vf||String)(r.value)+(r.sub?'  '+r.sub:''),{class:'val'});
  const hit=svg('rect',{x:0,y:y,width:W,height:rh,fill:'transparent'},s);
  hit.addEventListener('mousemove',ev=>showTip(ev,r.tip||('<b>'+r.label+'</b>'+(o.vf||String)(r.value))));hit.addEventListener('mouseleave',hideTip);});}

/* range rows (low-high with a median tick): o={rows:[{label,lo,mid,hi,tip}], x:[min,max], xf} */
function rangeChart(sel,o){const rows=o.rows,lw=o.lw||170,rh=28,W=760,m={t:6,r:30,b:40},H=m.t+rows.length*rh+m.b;const s=mk(sel,W,H);
 const sx=lin(o.x[0],o.x[1],lw,W-m.r);
 ticks(o.x[0],o.x[1],6).forEach(t=>{svg('line',{x1:sx(t),x2:sx(t),y1:m.t,y2:H-m.b,stroke:t===0?'var(--muted)':'var(--grid)'},s);text(s,sx(t),H-m.b+16,o.xf(t),{'text-anchor':'middle'});});
 if(o.xlab)text(s,(lw+W-m.r)/2,H-4,o.xlab,{'text-anchor':'middle'});
 rows.forEach((r,i)=>{const y=m.t+i*rh;text(s,lw-8,y+rh/2+4,r.label,{'text-anchor':'end'});
  svg('rect',{x:sx(r.lo),y:y+7,width:Math.max(2,sx(r.hi)-sx(r.lo)),height:rh-14,rx:4,fill:o.color||'var(--s1)',style:'opacity:.5'},s);
  svg('rect',{x:sx(r.mid)-2,y:y+4,width:4,height:rh-8,rx:2,fill:o.color||'var(--s1)'},s);
  text(s,sx(r.hi)+8,y+rh/2+4,o.xf(r.lo)+' to '+o.xf(r.hi)+'  (median '+o.xf(r.mid)+')',{class:'val'});
  const hit=svg('rect',{x:0,y:y,width:W,height:rh,fill:'transparent'},s);
  hit.addEventListener('mousemove',ev=>showTip(ev,r.tip));hit.addEventListener('mouseleave',hideTip);});}

/* scatter with direct labels: o={pts:[{label,x,y,tip,dx,dy}], x:[..], y:[..], xf, yf, xlab, ylab} */
function scatter(sel,o){const W=760,H=o.h||380,m={l:60,r:30,t:30,b:46};const s=mk(sel,W,H);
 const sx=lin(o.x[0],o.x[1],m.l,W-m.r),sy=lin(o.y[0],o.y[1],H-m.b,m.t);
 axisY(s,sy,ticks(o.y[0],o.y[1],5),m.l,W-m.r,o.yf);
 ticks(o.x[0],o.x[1],6).forEach(t=>{svg('line',{x1:sx(t),x2:sx(t),y1:m.t,y2:H-m.b,stroke:'var(--grid)'},s);text(s,sx(t),H-m.b+18,o.xf(t),{'text-anchor':'middle'});});
 text(s,(m.l+W-m.r)/2,H-6,o.xlab,{'text-anchor':'middle'});text(s,m.l,12,o.ylab,{});
 const lp=o.pts.map(p=>({p,x:sx(p.x)+(p.dx===undefined?10:p.dx),y:sy(p.y)+(p.dy===undefined?4:p.dy)})).sort((a,b)=>a.y-b.y);
 for(let i=1;i<lp.length;i++){for(let j=0;j<i;j++){if(Math.abs(lp[i].y-lp[j].y)<13&&Math.abs(lp[i].x-lp[j].x)<120)lp[i].y=lp[j].y+13;}}
 const ly=new Map(lp.map(l=>[l.p,l.y]));
 o.pts.forEach(p=>{const c=svg('circle',{cx:sx(p.x),cy:sy(p.y),r:6.5,fill:p.color||'var(--s1)',stroke:'var(--panel)','stroke-width':2},s);
  text(s,sx(p.x)+(p.dx===undefined?10:p.dx),ly.get(p),p.label,{class:'val','text-anchor':p.anchor||'start'});
  c.addEventListener('mousemove',ev=>showTip(ev,p.tip));c.addEventListener('mouseleave',hideTip);});}

/* heatmap: o={rows:[labels], cols:[labels], vals:[[..]], vf, rowlab, collab, tip(r,c)} */
function heat(sel,o){const cw=118,ch=46,W=Math.max(560,170+o.cols.length*cw),H=44+o.rows.length*ch+30;const s=mk(sel,W,H);
 const mx=Math.max(...o.vals.flat());
 const mix=t=>{const a=getComputedStyle(document.documentElement);return 'color-mix(in srgb, var(--seq1) '+Math.round(t*100)+'%, var(--seq0))';};
 o.cols.forEach((c,j)=>text(s,170+j*cw+cw/2,22,c,{'text-anchor':'middle'}));
 text(s,170+o.cols.length*cw/2,H-4,o.collab,{'text-anchor':'middle'});
 o.rows.forEach((r,i)=>{text(s,160,44+i*ch+ch/2+4,r,{'text-anchor':'end'});
  o.vals[i].forEach((v,j)=>{const t=v/mx;const c=svg('rect',{x:170+j*cw+2,y:44+i*ch+2,width:cw-4,height:ch-4,rx:5,fill:mix(t)},s);
   text(s,170+j*cw+cw/2,44+i*ch+ch/2+4,o.vf(v),{'text-anchor':'middle',class:'strong',style:'fill:'+(t>.55?'#fff':'var(--text)')});
   c.addEventListener('mousemove',ev=>showTip(ev,o.tip(i,j)));c.addEventListener('mouseleave',hideTip);});});
 text(s,10,24,o.rowlab,{});}

/* grouped vertical bars with a zero line: o={cats:[..], series:[{name,color,vals:[..]}], y:[lo,hi], yf, ylab, tipf} */
function groupedBar(sel,o){const W=760,H=o.h||330,m={l:56,r:20,t:30,b:36};const s=mk(sel,W,H);
 const sy=lin(o.y[0],o.y[1],H-m.b,m.t);axisY(s,sy,ticks(o.y[0],o.y[1],6),m.l,W-m.r,o.yf);
 svg('line',{x1:m.l,x2:W-m.r,y1:sy(0),y2:sy(0),stroke:'var(--muted)'},s);
 const gw=(W-m.l-m.r)/o.cats.length,n=o.series.length,bw=Math.min(26,(gw-18)/n);
 o.cats.forEach((c,i)=>{const x0=m.l+i*gw+(gw-bw*n-2*(n-1))/2;text(s,m.l+i*gw+gw/2,H-m.b+18,c,{'text-anchor':'middle'});
  o.series.forEach((se,k)=>{const v=se.vals[i];if(v===null||v===undefined)return;const y=sy(Math.max(v,0)),h=Math.abs(sy(v)-sy(0));
   const b=svg('rect',{x:x0+k*(bw+2),y:y,width:bw,height:Math.max(1,h),rx:3,fill:se.color},s);
   if(o.vlab)text(s,x0+k*(bw+2)+bw/2,v>=0?y-5:y+h+13,o.vlab(v),{'text-anchor':'middle',class:'val'});
   b.addEventListener('mousemove',ev=>showTip(ev,o.tipf(c,se,v)));b.addEventListener('mouseleave',hideTip);});});
 if(o.ylab)text(s,m.l,12,o.ylab,{});}

/* dot with margin (point estimate and 95% band) per row: o={rows:[{label,v,m,tip}], x:[..], xf} */
function marginChart(sel,o){const rows=o.rows,lw=150,rh=34,W=760,m={t:8,r:30,b:42},H=m.t+rows.length*rh+m.b;const s=mk(sel,W,H);
 const sx=lin(o.x[0],o.x[1],lw,W-m.r);
 ticks(o.x[0],o.x[1],6).forEach(t=>{svg('line',{x1:sx(t),x2:sx(t),y1:m.t,y2:H-m.b,stroke:t===0?'var(--text2)':'var(--grid)'},s);text(s,sx(t),H-m.b+16,o.xf(t),{'text-anchor':'middle'});});
 text(s,(lw+W-m.r)/2,H-4,o.xlab,{'text-anchor':'middle'});
 rows.forEach((r,i)=>{const y=m.t+i*rh+rh/2;text(s,lw-8,y+4,r.label,{'text-anchor':'end'});
  svg('line',{x1:sx(r.v-r.m),x2:sx(r.v+r.m),y1:y,y2:y,stroke:r.color||'var(--s1)','stroke-width':2.5},s);
  const c=svg('circle',{cx:sx(r.v),cy:y,r:6,fill:r.color||'var(--s1)',stroke:'var(--panel)','stroke-width':2},s);
  const hit=svg('rect',{x:0,y:y-rh/2,width:W,height:rh,fill:'transparent'},s);
  hit.addEventListener('mousemove',ev=>showTip(ev,r.tip));hit.addEventListener('mouseleave',hideTip);});}
"""


def page(title, description, body, data, script):
    """Assemble the full HTML document."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>{CSS}</style>
</head>
<body>
<div id="tip" role="tooltip"></div>
{body}
<script>
const DATA = {json.dumps(data, separators=(",", ":"))};
{JS}
{script}
</script>
</body>
</html>
"""
