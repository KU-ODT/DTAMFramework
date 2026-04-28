"""시퀀스 다이어그램 — JSON 데이터 + 시각화 페이지.

- ``GET /api/sequence-diagram`` — Phase별 메시지 흐름을 담은 정적 JSON
- ``GET /docs/sequence``        — 위 JSON 을 SVG 로 그려주는 HTML 페이지

데이터 파일은 ``app/web/data/sequence_diagram{_ko,_en}.json``.
페이지와 JSON 이 같은 origin (SimulationState, port 8096) 위에 있어야
브라우저 fetch 가 막히지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from ..config import WEB_DIR

router = APIRouter(tags=["📊 서버 상태"])

_DATA_DIR = WEB_DIR / "data"


@router.get(
    "/api/sequence-diagram",
    summary="시퀀스 다이어그램 JSON",
    description="라이브 모니터의 lane/arrow 렌더링용 정적 시퀀스 데이터.",
)
async def get_sequence_diagram(lang: str = "ko") -> Response:
    suffix = "_en" if lang.lower().startswith("e") else "_ko"
    path = _DATA_DIR / f"sequence_diagram{suffix}.json"
    if not path.is_file():
        path = _DATA_DIR / "sequence_diagram.json"
    if not path.is_file():
        return Response(
            content=json.dumps({"actors": [], "messages": []}),
            media_type="application/json",
        )
    return Response(content=path.read_text(encoding="utf-8"), media_type="application/json")


# ── 시각화 페이지 ───────────────────────────────────────────────────────
SEQ_HTML = r"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<title>DTAM Sequence Diagram</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#c9d1d9;overflow:hidden;height:100vh}
.top-bar{display:flex;align-items:center;gap:12px;padding:10px 20px;background:#161b22;border-bottom:1px solid #30363d}
.top-bar h1{font-size:18px;color:#58a6ff;flex:1}
.lang-btn{padding:4px 12px;border:1px solid #30363d;border-radius:6px;background:transparent;color:#8b949e;cursor:pointer;font-size:13px}
.lang-btn.active{background:#1f6feb;color:#fff;border-color:#1f6feb}
.back-link{color:#58a6ff;text-decoration:none;font-size:13px}
#seq-wrap{overflow:auto;height:calc(100vh - 50px);position:relative}
.seq-header-top{display:flex;position:sticky;top:0;z-index:10;background:#161b22;border-bottom:1px solid #30363d}
.seq-header{display:flex;border-top:1px solid #30363d;background:#161b22}
.seq-actor{display:flex;justify-content:center;padding:8px 0}
.seq-actor-box{padding:6px 10px;border-radius:8px;font-size:13px;font-weight:600;text-align:center;line-height:1.3;min-width:70px}
.actor-user{background:#6e40c9;color:#fff}.actor-monitoring{background:#1f6feb;color:#fff}
.actor-server{background:#238636;color:#fff}.actor-db{background:#8b949e;color:#fff}
.actor-mission{background:#d29922;color:#000}.actor-vehicle{background:#f85149;color:#fff}
.actor-visual{background:#a371f7;color:#fff}
.seq-body{position:relative;background:transparent}
.seq-label{position:absolute;font-size:11px;white-space:nowrap;pointer-events:none}
.seq-msg-id{color:#f0883e;font-weight:700;margin-right:3px}
.seq-msg-name{color:#c9d1d9}.seq-msg-proto{color:#8b949e;font-size:10px;margin-left:4px}
.seq-group{position:absolute;left:0;right:0;display:flex;align-items:center;border-top:1px dashed #30363d33}
.seq-group-band{position:absolute;left:0;right:0;background:linear-gradient(90deg,#1f6feb15 0%,#1f6feb08 50%,#1f6feb15 100%);pointer-events:none}
.seq-group-label{background:#1f6feb33;color:#58a6ff;padding:4px 14px;border-radius:6px;font-size:13px;font-weight:700;border:1px solid #1f6feb55;margin-left:14px}
.seq-sticky-group{position:sticky;top:46px;z-index:9;background:#21262dcc;backdrop-filter:blur(4px);padding:4px 14px;font-size:12px;color:#58a6ff;font-weight:600;border-bottom:1px solid #30363d;min-height:24px}
</style></head><body>
<div class="top-bar">
<h1>📊 DTAM Sequence Diagram</h1>
<button class="lang-btn active" data-lang="ko">한국어</button>
<button class="lang-btn" data-lang="en">English</button>
<a class="back-link" href="/docs">← Swagger Docs</a>
<a class="back-link" href="/docs/websocket">🔌 WS Docs</a>
</div>
<div id="seq-wrap"></div>
<script>
const SEQ_URLS={ko:"/api/sequence-diagram?lang=ko",en:"/api/sequence-diagram?lang=en"};
let LANG="ko";
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
document.querySelectorAll(".lang-btn").forEach(b=>b.addEventListener("click",()=>{
  LANG=b.dataset.lang;
  document.querySelectorAll(".lang-btn").forEach(x=>x.classList.toggle("active",x===b));
  render();
}));
async function render(){
  const el=document.getElementById("seq-wrap");
  let data;
  try{
    const r=await fetch(SEQ_URLS[LANG]||SEQ_URLS.ko,{cache:"no-store"});
    data=await r.json();
  }catch(e){el.innerHTML=`<p style="padding:20px;color:#f85149">로드 실패: ${e.message}</p>`;return}
  const ACTORS=data.actors||[],MSGS=data.messages||[];
  const ai={};ACTORS.forEach((a,i)=>ai[a.id]=i);
  const colW=180,rowH=48,groupH=42,totalW=colW*ACTORS.length;
  const cx=i=>i*colW+colW/2;
  const actorBar=(sticky)=>{
    let h=`<div class="${sticky?"seq-header-top":"seq-header"}" style="width:${totalW}px">`;
    ACTORS.forEach(a=>{
      const cls=a.color?`actor-${a.color}`:"";
      h+=`<div class="seq-actor" style="width:${colW}px"><div class="seq-actor-box ${cls}">${(a.name||"").replace(/\\n/g,"<br>")}</div></div>`;
    });
    return h+"</div>";
  };
  // Phase 별 (start, end) 위치 계산 — 그룹 라벨 위에 부드러운 band 를 깔기 위함
  const phases=[];
  {
    let yc=0,curStart=0,curLabel=null;
    for(const m of MSGS){
      if(m.group){
        if(curLabel!==null)phases.push({start:curStart,end:yc,label:curLabel});
        curLabel=m.group;curStart=yc;yc+=groupH;
      }else yc+=rowH;
    }
    if(curLabel!==null)phases.push({start:curStart,end:yc,label:curLabel});
  }
  let bodyH=0;MSGS.forEach(m=>bodyH+=m.group?groupH:rowH);
  const AH=9,AHW=5;
  let svg=`<svg style="position:absolute;top:0;left:0;width:${totalW}px;height:${bodyH}px;pointer-events:none">`;
  // Lifeline (각 actor 의 수직 점선) — 처음부터 끝까지 끊기지 않게 그림
  ACTORS.forEach((_,i)=>{svg+=`<line x1="${cx(i)}" y1="0" x2="${cx(i)}" y2="${bodyH}" stroke="#d0d6e0" stroke-width="1.5" stroke-dasharray="6,4"/>`});
  // Phase 경계 가로선 (각 phase 시작 위치에 옅은 선)
  phases.forEach((p,idx)=>{if(idx>0)svg+=`<line x1="0" y1="${p.start}" x2="${totalW}" y2="${p.start}" stroke="#30363d" stroke-width="1" stroke-dasharray="2,4"/>`});
  let labels="",groups="",bands="",y=0;
  for(const m of MSGS){
    if(m.group){groups+=`<div class="seq-group" style="top:${y}px;height:${groupH}px"><span class="seq-group-label">${esc(m.group)}</span></div>`;y+=groupH;continue}
    const fi=ai[m.from],ti=ai[m.to],x1=cx(fi),x2=cx(ti),my=y+rowH/2+6;
    const proto=String(m.proto||"").toLowerCase();
    // proto 색상: WebSocket(ws), DB/file, UI/internal — 옛 UDP/TCP 표기는 ws 로 fallback
    const sc=proto==="db"||proto==="file"?"#8892a6":proto==="ui"||proto==="build"?"#a371f7":proto==="internal"?"#f0883e":"#3b78d8";
    let txt=`<span class="seq-msg-id">${m.id?m.id+" ":""}</span><span class="seq-msg-name">${esc(m.name)}</span><span class="seq-msg-proto">${m.proto||""}</span>`;
    if(m.note)txt+=`<span class="seq-msg-proto"> · ${esc(m.note)}</span>`;
    if(fi===ti){
      const lw=36,lh=20,ly1=my-lh/2,ly2=my+lh/2;
      svg+=`<polyline points="${x1},${ly1} ${x1+lw},${ly1} ${x1+lw},${ly2} ${x1+AH},${ly2}" fill="none" stroke="${sc}" stroke-width="1.5" stroke-dasharray="4,3"/>`;
      svg+=`<polygon points="${x1},${ly2} ${x1+AH},${ly2-AHW} ${x1+AH},${ly2+AHW}" fill="${sc}"/>`;
      labels+=`<div class="seq-label" style="left:${x1+lw+5}px;top:${y+8}px">${txt}</div>`;
    }else{
      const dir=x2>x1?1:-1,baseX=x2-dir*AH;
      svg+=`<line x1="${x1}" y1="${my}" x2="${baseX}" y2="${my}" stroke="${sc}" stroke-width="2"/>`;
      svg+=`<polygon points="${x2},${my} ${baseX},${my-AHW} ${baseX},${my+AHW}" fill="${sc}"/>`;
      labels+=`<div class="seq-label" style="left:${(x1+x2)/2}px;top:${y+8}px;transform:translateX(-50%)">${txt}</div>`;
    }
    y+=rowH;
  }
  svg+="</svg>";
  // Phase band (그룹 영역 전체에 옅은 background 를 깔아 시각적 분리감 강화)
  phases.forEach(p=>{bands+=`<div class="seq-group-band" style="top:${p.start}px;height:${p.end-p.start}px;width:${totalW}px"></div>`});
  let html=actorBar(true);
  html+=`<div class="seq-sticky-group" id="ssg"></div>`;
  html+=`<div class="seq-body" style="width:${totalW}px;height:${bodyH}px;position:relative">${bands}${svg}${labels}${groups}</div>`;
  html+=actorBar(false);
  el.innerHTML=html;
  const ssg=document.getElementById("ssg");
  const sync=()=>{let c=phases[0]?.label||"";for(const p of phases)if(p.start<=el.scrollTop)c=p.label;ssg.textContent=c};
  el.onscroll=sync;sync();
}
render();
</script></body></html>"""


@router.get(
    "/docs/sequence",
    summary="시퀀스 다이어그램",
    description="Phase별 메시지 흐름 시퀀스 다이어그램 (SVG 기반 시각화)",
    response_class=HTMLResponse,
)
async def sequence_diagram_page() -> HTMLResponse:
    return HTMLResponse(content=SEQ_HTML)
