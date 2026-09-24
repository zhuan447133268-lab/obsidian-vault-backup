# -*- coding: utf-8 -*-
"""把知识图谱 JSON + 离线 three.min.js 内联进单文件 HTML 知识星系。"""
import io, os, json

VAULT = r"D:/Users/dfjq/Documents/Obsidian Vault"
JSON_PATH = r"D:/培训temp/knowledge_graph.json"
THREE_PATH = r"D:/培训temp/知识点演示培训包/three.min.js"
OUT = r"D:/Users/dfjq/Documents/Obsidian Vault/Demo-知识图谱实操/知识星系.html"

with open(JSON_PATH, encoding="utf-8") as f:
    graph = json.load(f)
graph_js = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")

with open(THREE_PATH, encoding="utf-8") as f:
    three_src = f.read()

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Obsidian 知识星系 · 3D</title>
<style>
  :root{ --ink:#e8f1ff; --panel:rgba(10,16,28,.72); --line:rgba(120,170,255,.25); }
  *{ box-sizing:border-box; }
  html,body{ margin:0; height:100%; background:#03060f; color:var(--ink);
    font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif; overflow:hidden; }
  #app{ position:fixed; inset:0; }
  canvas{ display:block; }
  .hud{ position:fixed; z-index:5; pointer-events:none; }
  #title{ left:22px; top:18px; }
  #title h1{ margin:0; font-size:20px; letter-spacing:1px; font-weight:700;
    text-shadow:0 0 18px rgba(90,160,255,.6); }
  #title p{ margin:4px 0 0; font-size:12px; opacity:.7; }
  #stats{ left:22px; bottom:18px; font-size:12px; line-height:1.7; opacity:.85;
    background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 14px; }
  #stats b{ color:#7fd1ff; }
  #legend{ right:18px; top:18px; background:var(--panel); border:1px solid var(--line);
    border-radius:10px; padding:10px 12px; max-height:62vh; overflow:auto; min-width:178px; pointer-events:auto; }
  #legend h3{ margin:0 0 8px; font-size:13px; opacity:.85; }
  .lg{ display:flex; align-items:center; gap:8px; font-size:12px; padding:3px 4px;
    border-radius:6px; cursor:pointer; }
  .lg:hover{ background:rgba(120,170,255,.12); }
  .lg.muted{ opacity:.32; }
  .lg .sw{ width:12px; height:12px; border-radius:3px; flex:none; box-shadow:0 0 6px currentColor; }
  .lg .ct{ margin-left:auto; opacity:.6; }
  #search{ right:18px; bottom:18px; display:flex; gap:8px; pointer-events:auto; }
  #search input{ width:230px; padding:9px 12px; border-radius:10px; border:1px solid var(--line);
    background:var(--panel); color:var(--ink); font-size:13px; outline:none; }
  #search input::placeholder{ color:rgba(232,241,255,.4); }
  #hint{ left:50%; bottom:16px; transform:translateX(-50%); font-size:11px; opacity:.45; }
  #tip{ position:fixed; z-index:6; pointer-events:none; background:rgba(8,14,26,.92);
    border:1px solid var(--line); border-radius:8px; padding:6px 10px; font-size:12px;
    max-width:240px; display:none; box-shadow:0 6px 24px rgba(0,0,0,.5); }
  #panel{ position:fixed; z-index:7; right:-380px; top:0; height:100%; width:360px;
    background:rgba(8,13,24,.94); border-left:1px solid var(--line); padding:22px; overflow:auto;
    transition:right .35s cubic-bezier(.2,.8,.2,1); backdrop-filter:blur(8px); }
  #panel.open{ right:0; }
  #panel .close{ position:absolute; right:14px; top:12px; cursor:pointer; opacity:.6; font-size:18px; }
  #panel .close:hover{ opacity:1; }
  #panel .ptag{ display:inline-block; font-size:11px; padding:2px 8px; border-radius:20px;
    background:rgba(120,170,255,.16); margin:0 6px 6px 0; }
  #panel h2{ margin:6px 0 4px; font-size:18px; line-height:1.35; }
  #panel .meta{ font-size:12px; opacity:.7; margin-bottom:12px; }
  #panel .sum{ font-size:13px; line-height:1.7; opacity:.92; background:rgba(255,255,255,.04);
    border-radius:8px; padding:10px 12px; margin-bottom:14px; }
  #panel .nbr{ font-size:12px; opacity:.8; line-height:1.8; }
  #panel .nbr span{ color:#7fd1ff; cursor:pointer; }
  #panel .nbr span:hover{ text-decoration:underline; }
  .lbl{ position:fixed; z-index:4; transform:translate(-50%,-50%); font-size:11px;
    padding:1px 6px; border-radius:6px; background:rgba(6,11,22,.66); border:1px solid rgba(120,170,255,.3);
    white-space:nowrap; pointer-events:none; text-shadow:0 0 6px #000; }
</style>
</head>
<body>
<div id="app"></div>
<div id="title" class="hud">
  <h1>Obsidian 知识星系</h1>
  <p>你的 278 篇笔记 + 双链关系，在三维空间里漂浮</p>
</div>
<div id="stats" class="hud"></div>
<div id="legend" class="hud"><h3>分组（点击隔离）</h3><div id="legend-body"></div></div>
<div id="search" class="hud">
  <input id="q" placeholder="搜索笔记名，回车定位…" />
</div>
<div id="hint" class="hud">拖拽旋转 · 滚轮缩放 · 悬停看摘要 · 点击看详情</div>
<div id="tip"></div>
<div id="panel">
  <span class="close" id="panel-close">×</span>
  <div id="panel-body"></div>
</div>

<script>/*__THREE_SRC__*/</script>
<script>
const GRAPH = /*__GRAPH_JSON__*/;
</script>
<script>
"use strict";
(function(){
  const nodes = GRAPH.nodes.map((n,i)=>({
    i, id:n.id, title:n.title, group:n.group, in:n.in||0, out:n.out_count||0,
    ghost:!!n.ghost, summary:n.summary||"", tags:n.tags||[],
    pos:new THREE.Vector3(), size:0, color:new THREE.Color()
  }));
  const idIndex = {}; nodes.forEach(n=>idIndex[n.id]=n.i);
  const edges = [];
  GRAPH.edges.forEach(e=>{
    const a=idIndex[e.s], b=idIndex[e.t];
    if(a!==undefined && b!==undefined) edges.push([a,b]);
  });

  // 分组配色（按名称哈希到色相，稳定）
  function hashHue(s){ let h=0; for(let i=0;i<s.length;i++) h=(h*31+s.charCodeAt(i))>>>0; return h%360; }
  const groups = {};
  nodes.forEach(n=>{ if(!groups[n.group]) groups[n.group]={name:n.group,count:0}; groups[n.group].count++; });
  const groupList = Object.values(groups).sort((a,b)=>b.count-a.count);
  const groupColor = {};
  groupList.forEach(g=>{
    if(g.name==="（待写笔记）"){ groupColor[g.name]=new THREE.Color("#5b6b86"); return; }
    const c=new THREE.Color(); c.setHSL(hashHue(g.name)/360,0.62,0.6); groupColor[g.name]=c;
  });
  nodes.forEach(n=> n.color.copy(groupColor[n.group]||new THREE.Color("#8aa")));

  // 节点大小：被链接数（hub 更大）
  let maxIn=1; nodes.forEach(n=> maxIn=Math.max(maxIn,n.in));
  nodes.forEach(n=>{
    const base = n.ghost?2.2:3.0;
    n.size = base + 9.0*Math.sqrt(n.in/maxIn);
  });

  // ---------- 力导向布局（3D，预热若干步后冻结） ----------
  const N=nodes.length;
  nodes.forEach(n=>{ n.pos.set((Math.random()-.5),(Math.random()-.5),(Math.random()-.5)); });
  const K = 26, ITER=260;
  let temp = 60;
  for(let it=0; it<ITER; it++){
    const disp = nodes.map(()=>new THREE.Vector3());
    for(let a=0;a<N;a++){
      for(let b=a+1;b<N;b++){
        const d = new THREE.Vector3().subVectors(nodes[a].pos, nodes[b].pos);
        let len = d.length()||0.01; if(len>200) len=200;
        const f = (K*K)/len;
        d.multiplyScalar(f/len);
        disp[a].add(d); disp[b].sub(d);
      }
    }
    for(const e of edges){
      const A=nodes[e[0]].pos, B=nodes[e[1]].pos;
      const d = new THREE.Vector3().subVectors(A,B);
      let len=d.length()||0.01;
      const f = (len*len)/K;
      d.multiplyScalar(f/len);
      disp[e[0]].sub(d); disp[e[1]].add(d);
    }
    const cool = temp/Math.sqrt(N);
    for(let a=0;a<N;a++){
      const d=disp[a]; const l=d.length()||0.01;
      nodes[a].pos.add(d.multiplyScalar(Math.min(l,cool)/l));
    }
    temp *= 0.985;
  }
  // 居中
  const center=new THREE.Vector3();
  nodes.forEach(n=>center.add(n.pos)); center.multiplyScalar(1/N);
  nodes.forEach(n=>n.pos.sub(center));
  let maxR=1; nodes.forEach(n=> maxR=Math.max(maxR,n.pos.length()));

  // ---------- three 场景 ----------
  const app=document.getElementById("app");
  const scene=new THREE.Scene();
  scene.fog=new THREE.FogExp2(0x03060f, 0.0016);
  const camera=new THREE.PerspectiveCamera(55, innerWidth/innerHeight, 1, 6000);
  const renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.setSize(innerWidth,innerHeight);
  app.appendChild(renderer.domElement);

  // 星空
  (function(){
    const g=new THREE.BufferGeometry(); const M=1400; const p=new Float32Array(M*3);
    for(let i=0;i<M;i++){ const r=1200+Math.random()*2000;
      const t=Math.random()*Math.PI*2, ph=Math.acos(2*Math.random()-1);
      p[i*3]=r*Math.sin(ph)*Math.cos(t); p[i*3+1]=r*Math.sin(ph)*Math.sin(t); p[i*3+2]=r*Math.cos(ph);
    }
    g.setAttribute("position", new THREE.BufferAttribute(p,3));
    const m=new THREE.PointsMaterial({color:0x9fb6e0,size:2.2,sizeAttenuation:false,transparent:true,opacity:.7});
    scene.add(new THREE.Points(g,m));
  })();

  // 节点 Points
  const posArr=new Float32Array(N*3), colArr=new Float32Array(N*3), sizeArr=new Float32Array(N), stateArr=new Float32Array(N);
  nodes.forEach((n,i)=>{ posArr[i*3]=n.pos.x; posArr[i*3+1]=n.pos.y; posArr[i*3+2]=n.pos.z;
    colArr[i*3]=n.color.r; colArr[i*3+1]=n.color.g; colArr[i*3+2]=n.color.b; sizeArr[i]=n.size; });
  const ng=new THREE.BufferGeometry();
  ng.setAttribute("position", new THREE.BufferAttribute(posArr,3));
  ng.setAttribute("aColor", new THREE.BufferAttribute(colArr,3));
  ng.setAttribute("aSize", new THREE.BufferAttribute(sizeArr,1));
  ng.setAttribute("aState", new THREE.BufferAttribute(stateArr,1));
  const nMat=new THREE.ShaderMaterial({
    transparent:true, depthWrite:false, blending:THREE.AdditiveBlending,
    uniforms:{ uTime:{value:0}, uPixel:{value:renderer.getPixelRatio()} },
    vertexShader:`
      attribute vec3 aColor; attribute float aSize; attribute float aState;
      varying vec3 vC; varying float vS; uniform float uPixel;
      void main(){
        vC=aColor; float mul = aState>0.5 ? 1.9 : (aState<-0.5?0.45:1.0);
        vS=aState;
        vec4 mv=modelViewMatrix*vec4(position,1.0);
        gl_PointSize = aSize*mul*uPixel*(320.0/-mv.z);
        gl_Position=projectionMatrix*mv;
      }`,
    fragmentShader:`
      varying vec3 vC; varying float vS;
      void main(){
        vec2 d=gl_PointCoord-vec2(0.5); float r=length(d);
        if(r>0.5) discard;
        float core=smoothstep(0.5,0.0,r);
        float a = vS<-0.5 ? 0.12 : 1.0;
        vec3 c = vC;
        if(vS>0.5){ c=mix(c, vec3(1.0), 0.35); }
        float glow = smoothstep(0.5,0.18,r);
        gl_FragColor=vec4(c, a*(0.55+0.45*core)*glow);
      }`
  });
  const points=new THREE.Points(ng,nMat); scene.add(points);

  // 边（基础 + 高亮）
  function buildEdgeGeo(useSet){
    const verts=[];
    edges.forEach((e,k)=>{ if(useSet && !useSet.has(k)) return;
      const A=nodes[e[0]].pos, B=nodes[e[1]].pos;
      verts.push(A.x,A.y,A.z, B.x,B.y,B.z);
    });
    const g=new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(verts,3)); return g;
  }
  const baseEdges=new THREE.LineSegments(buildEdgeGeo(null),
    new THREE.LineBasicMaterial({color:0x5fa8ff, transparent:true, opacity:0.10}));
  scene.add(baseEdges);
  let hiEdges=null;

  // ---------- 轨道控制（自写） ----------
  const orbit={ r:maxR*2.1, theta:0.6, phi:1.15, tx:0,ty:0,tz:0 };
  let dragging=false, lx=0, ly=0, idle=0;
  const cv=renderer.domElement;
  cv.addEventListener("pointerdown",e=>{ dragging=true; lx=e.clientX; ly=e.clientY; idle=0; });
  addEventListener("pointerup",()=> dragging=false);
  addEventListener("pointermove",e=>{
    if(dragging){ orbit.theta -= (e.clientX-lx)*0.005; orbit.phi -= (e.clientY-ly)*0.005;
      orbit.phi=Math.max(0.12,Math.min(Math.PI-0.12,orbit.phi)); lx=e.clientX; ly=e.clientY; idle=0; }
    else { hover(e.clientX,e.clientY); }
  });
  cv.addEventListener("wheel",e=>{ e.preventDefault(); orbit.r*= (1+ (e.deltaY>0?0.1:-0.1));
    orbit.r=Math.max(maxR*0.4, Math.min(maxR*5, orbit.r)); idle=0; },{passive:false});

  function updateCamera(){
    const r=orbit.r, st=Math.sin(orbit.phi);
    camera.position.set(orbit.tx + r*st*Math.cos(orbit.theta),
      orbit.ty + r*Math.cos(orbit.phi),
      orbit.tz + r*st*Math.sin(orbit.theta));
    camera.lookAt(orbit.tx,orbit.ty,orbit.tz);
  }

  // ---------- 投影 / 悬停 / 标签 ----------
  const tip=document.getElementById("tip");
  const labels=[];
  const topHubs = nodes.slice().sort((a,b)=>b.in-a.in).filter(n=>n.in>=4).slice(0,28);
  topHubs.forEach(n=>{ const d=document.createElement("div"); d.className="lbl"; d.textContent=n.title;
    d.style.color="#"+n.color.getHexString(); document.body.appendChild(d); labels.push({n,el:d}); });
  const _v=new THREE.Vector3();
  let selected=-1, hoverIdx=-1, isolate=null;

  function project(p){ _v.copy(p).project(camera);
    return { x:(_v.x*0.5+0.5)*innerWidth, y:(-_v.y*0.5+0.5)*innerHeight, z:_v.z }; }

  function hover(mx,my){
    let best=-1, bestD=16;
    for(let i=0;i<N;i++){ const pr=project(nodes[i].pos);
      if(pr.z>1) continue; const dx=pr.x-mx, dy=pr.y-my; const dd=Math.sqrt(dx*dx+dy*dy);
      if(dd<bestD){ bestD=dd; best=i; } }
    hoverIdx=best;
    if(best>=0){ const n=nodes[best];
      tip.style.display="block"; tip.style.left=(mx+14)+"px"; tip.style.top=(my+14)+"px";
      tip.innerHTML="<b>"+n.title+"</b><br><span style='opacity:.7'>"+n.group+
        " · 被引 "+n.in+" · 出链 "+n.out+(n.ghost?" · 待写":"");
    } else tip.style.display="none";
    applyStates();
  }

  function applyStates(){
    const arr=ng.getAttribute("aState").array;
    const nei = selected>=0 ? neighborSet(selected) : null;
    for(let i=0;i<N;i++){
      let s=0;
      if(isolate!==null){ s = (nodes[i].group===isolate)?0:-1; }
      if(i===selected) s=1;
      else if(i===hoverIdx) s=1;
      else if(selected>=0){ s = nei.has(i)?0:-1; }
      arr[i]=s;
    }
    ng.getAttribute("aState").needsUpdate=true;
    // 高亮边
    if(hiEdges){ scene.remove(hiEdges); hiEdges.geometry.dispose(); hiEdges=null; }
    if(selected>=0 || hoverIdx>=0){
      const center = selected>=0?selected:hoverIdx;
      const set=new Set();
      for(let k=0;k<edges.length;k++){ if(edges[k][0]===center||edges[k][1]===center) set.add(k); }
      hiEdges=new THREE.LineSegments(buildEdgeGeo(set),
        new THREE.LineBasicMaterial({color:0xffe27a, transparent:true, opacity:0.85}));
      scene.add(hiEdges);
    }
    baseEdges.material.opacity = (selected>=0||hoverIdx>=0)?0.04:0.10;
  }
  function neighborSet(c){ const s=new Set(); edges.forEach(e=>{ if(e[0]===c)s.add(e[1]); if(e[1]===c)s.add(e[0]); }); return s; }
  function neighborList(c){ const s=new Set(); edges.forEach(e=>{ if(e[0]===c)s.add(e[1]); if(e[1]===c)s.add(e[0]); }); return [...s].map(i=>nodes[i]); }

  // 点击
  cv.addEventListener("click",e=>{
    const pr=project(hoverIdx>=0?nodes[hoverIdx].pos:nodes[0].pos);
    if(hoverIdx>=0){ openPanel(nodes[hoverIdx]); }
  });
  function openPanel(n){
    selected=n.i; applyStates();
    const body=document.getElementById("panel-body");
    const nb=neighborList(n.i);
    let html="";
    html+='<div class="ptag" style="color:#'+n.color.getHexString()+'">'+n.group+'</div>';
    if(n.ghost) html+='<div class="ptag">待写笔记</div>';
    n.tags.forEach(t=> html+='<div class="ptag">#'+t+'</div>');
    html+='<h2>'+n.title+'</h2>';
    html+='<div class="meta">被引 '+n.in+' 次 · 出链 '+n.out+' 条'+(n.ghost?' · 此笔记尚未创建':'');
    if(!n.ghost) html+='<br>文件：<code style="opacity:.6">'+n.id+'</code>';
    html+='</div>';
    html+='<div class="sum">'+(n.summary||"（无摘要）")+'</div>';
    if(nb.length){
      html+='<div class="nbr"><b>关联笔记（'+nb.length+'）：</b><br>';
      nb.slice(0,40).forEach(m=>{ html+='<span data-id="'+m.i+'">▸ '+m.title+'</span><br>'; });
      html+='</div>';
    }
    body.innerHTML=html;
    body.querySelectorAll("span[data-id]").forEach(el=> el.onclick=()=>{ const t=nodes[+el.dataset.id]; openPanel(t); });
    document.getElementById("panel").classList.add("open");
  }
  document.getElementById("panel-close").onclick=()=>{ document.getElementById("panel").classList.remove("open"); selected=-1; applyStates(); };

  // 搜索
  document.getElementById("q").addEventListener("keydown",e=>{
    if(e.key!=="Enter") return; const q=e.target.value.trim().toLowerCase(); if(!q) return;
    let hit=nodes.find(n=> n.title.toLowerCase().includes(q) || n.name.toLowerCase().includes(q));
    if(!hit) hit=nodes.find(n=> (n.tags||[]).some(t=>t.toLowerCase().includes(q)));
    if(hit){ openPanel(hit); }
  });

  // 图例
  const lb=document.getElementById("legend-body");
  groupList.forEach(g=>{
    const c=groupColor[g.name]||new THREE.Color("#8aa");
    const row=document.createElement("div"); row.className="lg";
    row.innerHTML='<span class="sw" style="background:#'+c.getHexString()+';color:#'+c.getHexString()+'"></span>'+
      '<span>'+g.name+'</span><span class="ct">'+g.count+'</span>';
    row.onclick=()=>{ isolate = isolate===g.name?null:g.name;
      document.querySelectorAll(".lg").forEach(x=>x.classList.remove("muted"));
      if(isolate){ document.querySelectorAll(".lg").forEach(x=>{ if(x.textContent.indexOf(isolate)<0) x.classList.add("muted"); }); }
      applyStates(); };
    lb.appendChild(row);
  });

  // stats
  document.getElementById("stats").innerHTML=
    "笔记 <b>"+nodes.filter(n=>!n.ghost).length+"</b> 篇<br>"+
    "连线 <b>"+edges.length+"</b> 条<br>"+
    "待写缺口 <b>"+nodes.filter(n=>n.ghost).length+"</b> 个<br>"+
    "分组 <b>"+groupList.length+"</b> 类";

  // ---------- 渲染循环 ----------
  let t0=performance.now();
  function frame(){
    const now=performance.now(); nMat.uniforms.uTime.value=(now-t0)/1000;
    idle += 0.016;
    if(!dragging && idle>3.5 && isolate===null && selected<0){ orbit.theta += 0.0009; }
    updateCamera();
    // 标签
    labels.forEach(L=>{ const pr=project(L.n.pos);
      if(pr.z>1 || (isolate!==null && L.n.group!==isolate)){ L.el.style.display="none"; return; }
      L.el.style.display="block"; L.el.style.left=pr.x+"px"; L.el.style.top=pr.y+"px";
      L.el.style.opacity = (selected>=0 && !neighborSet(selected).has(L.n.i) && L.n.i!==selected)? "0.18":"0.95";
    });
    renderer.render(scene,camera);
    requestAnimationFrame(frame);
  }
  updateCamera(); applyStates(); frame();
  addEventListener("resize",()=>{ camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth,innerHeight); nMat.uniforms.uPixel.value=renderer.getPixelRatio(); });
})();
</script>
</body>
</html>
"""

html = TPL.replace("/*__THREE_SRC__*/", three_src).replace("/*__GRAPH_JSON__*/", graph_js)
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("WROTE", OUT, len(html), "bytes")
