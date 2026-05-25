from __future__ import annotations

import json
import re
from collections import Counter
from itertools import combinations
from typing import Any

from floating_todo.domain import Task, normalize_task_tag, work_elapsed_seconds
from floating_todo.view_models import priority_text


STOP_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "todo",
    "list",
    "task",
    "notes",
    "note",
    "review",
    "done",
    "active",
}


def build_history_graph_payload(tasks: list[Task], *, max_keywords: int = 18) -> dict[str, Any]:
    completed = [task for task in tasks if task.status == "done"]
    task_nodes: list[dict[str, Any]] = []
    task_keywords: dict[str, set[str]] = {}
    keyword_counts: Counter[str] = Counter()

    for task in completed:
        keywords = _task_keywords(task)
        task_keywords[task.id] = keywords
        keyword_counts.update(keywords)
        task_nodes.append(
            {
                "id": task.id,
                "title": task.title,
                "tag": normalize_task_tag(task.tag),
                "priority": task.priority,
                "priorityText": priority_text(task.priority),
                "late": _task_completed_late(task),
                "seconds": work_elapsed_seconds(task, task.completed_at or task.updated_at),
                "words": sorted(keywords),
            }
        )

    selected_keywords = [
        word
        for word, count in keyword_counts.most_common()
        if count >= 2 or _is_cjk_word(word) or len(completed) <= 4
    ][:max_keywords]
    keyword_set = set(selected_keywords)
    keyword_nodes = [
        {"id": f"k-{_keyword_id(word)}", "word": word, "count": keyword_counts[word]}
        for word in selected_keywords
    ]

    links: list[dict[str, Any]] = []
    for task in task_nodes:
        for word in task["words"]:
            if word in keyword_set:
                links.append({"source": task["id"], "target": f"k-{_keyword_id(word)}", "kind": "keyword"})

    for left, right in combinations(task_nodes, 2):
        shared = sorted(task_keywords[left["id"]] & task_keywords[right["id"]])
        visible_shared = [word for word in shared if word in keyword_set]
        if len(visible_shared) >= 2:
            links.append(
                {
                    "source": left["id"],
                    "target": right["id"],
                    "kind": "task",
                    "shared": visible_shared[:5],
                }
            )

    return {
        "tasks": task_nodes,
        "keywords": keyword_nodes,
        "links": links,
        "metrics": {
            "tasks": len(task_nodes),
            "keywords": len(keyword_nodes),
            "links": len(links),
        },
    }


def render_history_graph_html(payload: dict[str, Any]) -> str:
    graph_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Todo list · 任务关系图</title>
  <style>
    :root {{
      --bg:#01050b; --panel:rgba(4,13,24,.78); --line:rgba(78,207,255,.18);
      --text:#effaff; --soft:#a9cadc; --muted:#6b91a8; --cyan:#32dcff;
      --violet:#a78bfa; --gold:#f4b45f; --rose:#ff6f91;
      font-family:\"Alibaba PuHuiTi\",\"Microsoft YaHei UI\",\"Segoe UI\",sans-serif;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; width:100vw; height:100vh; overflow:hidden; color:var(--text);
      background:radial-gradient(circle at 18% 16%,rgba(50,220,255,.12),transparent 28%),
        radial-gradient(circle at 72% 18%,rgba(167,139,250,.09),transparent 30%),
        linear-gradient(145deg,#01050b,#04101e 58%,#061927);
    }}
    canvas {{ position:fixed; inset:0; width:100vw; height:100vh; display:block; cursor:grab; }}
    canvas:active {{ cursor:grabbing; }}
    .hud {{ position:fixed; inset:18px; pointer-events:none; display:grid; grid-template-columns:300px 1fr 330px; gap:18px; }}
    .glass {{
      pointer-events:auto; border:1px solid var(--line); border-radius:22px;
      background:linear-gradient(145deg,rgba(3,11,21,.82),rgba(7,26,40,.58));
      box-shadow:0 24px 78px rgba(0,0,0,.32), inset 0 0 0 1px rgba(255,255,255,.018);
      backdrop-filter:blur(16px);
    }}
    .left {{ align-self:start; padding:18px; }}
    .top {{ grid-column:2; justify-self:center; align-self:start; min-width:480px; padding:14px 18px; display:flex; justify-content:space-between; gap:18px; }}
    .right {{ align-self:stretch; padding:18px; min-height:0; display:grid; grid-template-rows:auto auto 1fr auto; gap:14px; }}
    h1,h2,p {{ margin:0; }} h1 {{ font-size:18px; line-height:1.2; }} h2 {{ font-size:16px; margin-bottom:10px; }}
    .sub {{ color:var(--muted); margin-top:6px; line-height:1.45; font-size:12px; font-weight:800; }}
    .chips {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }}
    .chip {{ min-height:30px; display:inline-flex; align-items:center; border-radius:10px; padding:0 10px; color:var(--soft); background:rgba(5,15,28,.76); box-shadow:inset 0 0 0 1px rgba(78,207,255,.12); font-size:12px; font-weight:900; }}
    .legend {{ display:grid; gap:10px; margin-top:16px; }}
    .legend-item {{ display:grid; grid-template-columns:12px 1fr auto; gap:10px; align-items:center; color:var(--soft); font-size:12px; font-weight:850; }}
    .dot {{ width:10px; height:10px; border-radius:50%; box-shadow:0 0 14px currentColor; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
    .metric {{ padding:12px; border-radius:15px; background:rgba(4,13,24,.72); box-shadow:inset 0 0 0 1px rgba(78,207,255,.10); }}
    .metric b {{ display:block; font-size:20px; line-height:1; }} .metric span {{ display:block; margin-top:7px; color:var(--muted); font-size:11px; font-weight:850; }}
    .selected {{ border-radius:18px; padding:15px; background:rgba(4,13,24,.74); box-shadow:inset 0 0 0 1px rgba(78,207,255,.13); }}
    .selected-title {{ font-size:18px; font-weight:950; line-height:1.35; }} .selected-type {{ margin-top:10px; color:var(--muted); font-size:12px; font-weight:850; }}
    .queue {{ min-height:0; overflow:auto; display:flex; flex-direction:column; gap:10px; padding-right:2px; }}
    .task-card {{ border:0; color:var(--text); text-align:left; cursor:pointer; border-radius:15px; padding:12px; background:rgba(4,13,24,.58); box-shadow:inset 0 0 0 1px rgba(78,207,255,.09); }}
    .task-card:hover,.task-card.active {{ box-shadow:inset 0 0 0 1px rgba(50,220,255,.34),0 14px 28px rgba(0,0,0,.18); }}
    .task-card strong {{ display:block; font-size:13px; line-height:1.45; }} .task-card span {{ display:inline-block; margin-top:8px; margin-right:6px; padding:5px 7px; border-radius:8px; color:var(--muted); background:rgba(7,22,34,.82); font-size:11px; font-weight:850; }}
    .ops {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }} .ops button {{ border:0; min-height:38px; border-radius:12px; color:var(--soft); background:rgba(5,15,28,.82); box-shadow:inset 0 0 0 1px rgba(78,207,255,.13); font-weight:900; }}
    .hint {{ position:fixed; left:50%; bottom:20px; transform:translateX(-50%); padding:9px 13px; border-radius:999px; color:var(--muted); background:rgba(3,10,19,.68); border:1px solid rgba(78,207,255,.12); font-size:12px; font-weight:850; pointer-events:none; }}
  </style>
</head>
<body>
  <canvas id=\"graph\"></canvas>
  <div class=\"hud\">
    <section class=\"glass left\"><h1>任务-关键词关系图</h1><p class=\"sub\">已完成任务形成节点；标题、标签、备注、体会中的关键词生成连接，用于发现主题簇、孤立任务和需要补标签的记录。</p><div class=\"chips\"><span class=\"chip\">拖动旋转</span><span class=\"chip\">滚轮缩放</span><span class=\"chip\">点击节点</span></div><div class=\"legend\"><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--cyan);background:var(--cyan)\"></i><span>任务节点</span><b id=\"legendTasks\">0</b></div><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--violet);background:var(--violet)\"></i><span>关键词节点</span><b id=\"legendKeywords\">0</b></div><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--gold);background:var(--gold)\"></i><span>高优先级</span><b id=\"legendHigh\">0</b></div><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--rose);background:var(--rose)\"></i><span>超时风险</span><b id=\"legendLate\">0</b></div></div></section>
    <section class=\"glass top\"><div><h1>Obsidian 风格历史洞察</h1><p class=\"sub\">用关系发现可合并的项目、孤立记录和需要补标签的任务。</p></div><div class=\"metric-grid\"><div class=\"metric\"><b id=\"metricNodes\">0</b><span>节点</span></div><div class=\"metric\"><b id=\"metricLinks\">0</b><span>连接</span></div><div class=\"metric\"><b id=\"metricGroups\">0</b><span>主题簇</span></div></div></section>
    <aside class=\"glass right\"><div><h2>节点详情</h2><div class=\"selected\"><div id=\"selectedTitle\" class=\"selected-title\">点击一个任务或关键词</div><div id=\"selectedType\" class=\"selected-type\">右侧会显示相关任务，用于补标签、复盘或导出。</div><div id=\"selectedChips\" class=\"chips\"></div></div></div><div><h2>关联任务</h2></div><div id=\"taskQueue\" class=\"queue\"></div><div class=\"ops\"><button>补备注</button><button>改标签</button><button>导出</button></div></aside>
  </div><div class=\"hint\">Canvas 3D 投影 · 可嵌入桌面程序 · 无外部依赖</div>
  <script>
    const GRAPH_PAYLOAD = {graph_json};
    const canvas = document.getElementById('graph');
    const ctx = canvas.getContext('2d');
    const tasks = GRAPH_PAYLOAD.tasks || [];
    const keywords = GRAPH_PAYLOAD.keywords || [];
    const links = GRAPH_PAYLOAD.links || [];
    const nodes = [];
    const nodeMap = new Map();
    function addNode(node) {{ nodes.push(node); nodeMap.set(node.id, node); }}
    tasks.forEach((task, index) => {{ const a = index * 1.72; addNode({{...task,type:'task',color:task.late?'#ff6f91':task.priority==='P1'?'#f4b45f':'#32dcff',radius:task.priority==='P1'?9:task.priority==='P2'?7.5:6.5,x:Math.cos(a)*(140+(index%3)*34),y:Math.sin(index*.91)*80,z:Math.sin(index*1.37)*(120+(index%4)*28),vx:0,vy:0,vz:0}}); }});
    keywords.forEach((keyword,index)=>{{ const a=index/Math.max(1,keywords.length)*Math.PI*2; addNode({{...keyword,title:keyword.word,type:'keyword',color:'#a78bfa',radius:10+keyword.count*1.4,x:Math.cos(a)*210,y:Math.sin(index*1.4)*72,z:Math.sin(a)*210,vx:0,vy:0,vz:0}}); }});
    let width=0,height=0,rotX=-.18,rotY=.65,zoom=1.28,drag=null,selected=nodes.find(n=>n.type==='keyword')||nodes[0],projected=[];
    function resize() {{ const dpr=Math.min(devicePixelRatio||1,2); width=innerWidth; height=innerHeight; canvas.width=Math.floor(width*dpr); canvas.height=Math.floor(height*dpr); ctx.setTransform(dpr,0,0,dpr,0,0); }}
    function step() {{ for (const n of nodes) {{ n.vx+=-n.x*.00008; n.vy+=-n.y*.00008; n.vz+=-n.z*.00008; }} for(let i=0;i<nodes.length;i++){{ for(let j=i+1;j<nodes.length;j++){{ const a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z,d2=Math.max(600,dx*dx+dy*dy+dz*dz),f=52/d2; a.vx+=dx*f; a.vy+=dy*f; a.vz+=dz*f; b.vx-=dx*f; b.vy-=dy*f; b.vz-=dz*f; }} }} for(const l of links){{ const a=nodeMap.get(l.source),b=nodeMap.get(l.target); if(!a||!b) continue; const dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z,d=Math.max(1,Math.sqrt(dx*dx+dy*dy+dz*dz)),target=(a.type==='keyword'||b.type==='keyword')?95:76,f=(d-target)*(l.kind==='task'?.006:.012),nx=dx/d,ny=dy/d,nz=dz/d; a.vx+=nx*f; a.vy+=ny*f; a.vz+=nz*f; b.vx-=nx*f; b.vy-=ny*f; b.vz-=nz*f; }} for(const n of nodes){{ n.vx*=.88; n.vy*=.88; n.vz*=.88; n.x+=n.vx; n.y+=n.vy; n.z+=n.vz; }} }}
    function project(n) {{ const cy=Math.cos(rotY),sy=Math.sin(rotY),cx=Math.cos(rotX),sx=Math.sin(rotX); let x=n.x*cy-n.z*sy,z=n.x*sy+n.z*cy,y=n.y*cx-z*sx; z=n.y*sx+z*cx; const p=620/(620+z); return {{node:n,x:width/2+x*p*zoom,y:height/2+y*p*zoom,z,scale:p*zoom}}; }}
    function rgba(hex,a) {{ const v=hex.replace('#',''),r=parseInt(v.slice(0,2),16),g=parseInt(v.slice(2,4),16),b=parseInt(v.slice(4,6),16); return `rgba(${{r}},${{g}},${{b}},${{a}})`; }}
    function draw() {{ ctx.clearRect(0,0,width,height); const bg=ctx.createRadialGradient(width/2,height/2,0,width/2,height/2,Math.max(width,height)*.62); bg.addColorStop(0,'rgba(15,45,66,.34)'); bg.addColorStop(1,'rgba(1,5,11,0)'); ctx.fillStyle=bg; ctx.fillRect(0,0,width,height); projected=nodes.map(project).sort((a,b)=>a.z-b.z); const pm=new Map(projected.map(p=>[p.node.id,p])); for(const l of links){{ const a=pm.get(l.source),b=pm.get(l.target); if(!a||!b) continue; const active=selected&&(selected.id===l.source||selected.id===l.target); ctx.strokeStyle=active?'rgba(50,220,255,.62)':l.kind==='task'?'rgba(167,139,250,.22)':'rgba(78,207,255,.15)'; ctx.lineWidth=active?1.8:l.kind==='task'?1.25:.9; ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); }} const t=performance.now()*.002; for(const p of projected){{ const n=p.node,r=Math.max(3.5,n.radius*p.scale),active=selected&&selected.id===n.id,pulse=1+Math.sin(t+n.x*.01)*.055; const glow=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,r*(active?5.2:n.late?4.2:3.2)); glow.addColorStop(0,rgba(n.color,active?.62:.36)); glow.addColorStop(.36,rgba(n.color,active?.22:.11)); glow.addColorStop(1,rgba(n.color,0)); ctx.fillStyle=glow; ctx.beginPath(); ctx.arc(p.x,p.y,r*(active?5.2:3.6),0,Math.PI*2); ctx.fill(); ctx.fillStyle=rgba(n.color,n.type==='keyword'?.92:.86); ctx.beginPath(); ctx.arc(p.x,p.y,r*pulse,0,Math.PI*2); ctx.fill(); if(n.priority==='P1'||n.type==='keyword'){{ ctx.strokeStyle=n.type==='keyword'?'rgba(216,204,255,.72)':'rgba(244,180,95,.72)'; ctx.lineWidth=1.2; ctx.beginPath(); ctx.arc(p.x,p.y,r*1.62,0,Math.PI*2); ctx.stroke(); }} ctx.font=`${{Math.max(10,12*p.scale)}}px Microsoft YaHei UI`; ctx.fillStyle=n.type==='keyword'?'rgba(232,223,255,.92)':'rgba(226,248,255,.88)'; ctx.textAlign='center'; ctx.fillText(n.type==='keyword'?n.word:n.title.slice(0,8),p.x,p.y+r+15); }} }}
    function related(n) {{ if(!n) return []; if(n.type==='keyword') return tasks.filter(t=>(t.words||[]).includes(n.word)); const set=new Set(n.words||[]); return tasks.map(t=>({{task:t,shared:(t.words||[]).filter(w=>set.has(w)).length}})).filter(i=>i.task.id===n.id||i.shared>0).sort((a,b)=>b.shared-a.shared).map(i=>i.task); }}
    function select(n) {{ if(!n) return; selected=n; selectedTitle.textContent=n.type==='keyword'?n.word:n.title; selectedType.textContent=n.type==='keyword'?`关键词节点 · 关联 ${{related(n).length}} 条任务`:`${{n.tag}} · ${{n.priorityText||n.priority}} · ${{n.late?'超时完成':'准时完成'}}`; selectedChips.innerHTML=''; (n.type==='keyword'?[n.word]:(n.words||[])).slice(0,5).forEach(w=>{{ const c=document.createElement('span'); c.className='chip'; c.textContent=w; selectedChips.appendChild(c); }}); renderQueue(n); }}
    function renderQueue(n=selected) {{ taskQueue.innerHTML=''; related(n).slice(0,7).forEach(t=>{{ const b=document.createElement('button'); b.className=`task-card ${{selected&&selected.id===t.id?'active':''}}`; b.innerHTML=`<strong>${{t.title}}</strong><span>#${{t.tag}}</span><span>${{t.priorityText||t.priority}}</span><span>${{t.late?'超时':'准时'}}</span>`; b.onclick=()=>select(nodeMap.get(t.id)); taskQueue.appendChild(b); }}); }}
    function hit(x,y) {{ return [...projected].sort((a,b)=>b.z-a.z).find(p=>{{ const r=Math.max(8,p.node.radius*p.scale*2.4),dx=p.x-x,dy=p.y-y; return dx*dx+dy*dy<=r*r; }})?.node; }}
    canvas.addEventListener('pointerdown',e=>{{ const n=hit(e.clientX,e.clientY); if(n) select(n); drag={{x:e.clientX,y:e.clientY}}; canvas.setPointerCapture(e.pointerId); }});
    canvas.addEventListener('pointermove',e=>{{ if(!drag) return; rotY+=(e.clientX-drag.x)*.006; rotX+=(e.clientY-drag.y)*.004; rotX=Math.max(-1.15,Math.min(1.15,rotX)); drag={{x:e.clientX,y:e.clientY}}; }});
    canvas.addEventListener('pointerup',()=>drag=null); canvas.addEventListener('wheel',e=>{{ e.preventDefault(); zoom*=e.deltaY>0?.92:1.08; zoom=Math.max(.7,Math.min(2.4,zoom)); }},{{passive:false}});
    function animate() {{ for(let i=0;i<2;i++) step(); if(!drag) rotY+=.0012; draw(); requestAnimationFrame(animate); }}
    legendTasks.textContent=tasks.length; legendKeywords.textContent=keywords.length; legendHigh.textContent=tasks.filter(t=>t.priority==='P1').length; legendLate.textContent=tasks.filter(t=>t.late).length; metricNodes.textContent=tasks.length+keywords.length; metricLinks.textContent=links.length; metricGroups.textContent=Math.max(1, Math.min(9, keywords.length)); addEventListener('resize', resize); resize(); select(selected); animate();
  </script>
</body>
</html>"""


def _task_keywords(task: Task) -> set[str]:
    text = " ".join([task.title, normalize_task_tag(task.tag), task.notes, task.reflection])
    words = {_normalize_keyword(match) for match in re.findall(r"[A-Za-z0-9_+\-.#]+|[\u4e00-\u9fff]{2,}", text)}
    return {word for word in words if word and word not in STOP_WORDS and len(word) >= 2}


def _normalize_keyword(value: str) -> str:
    value = value.strip().lower()
    return re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", value)


def _keyword_id(word: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "-", word).strip("-").lower()


def _is_cjk_word(word: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in word)


def _task_completed_late(task: Task) -> bool:
    if task.deadline is None or task.completed_at is None:
        return False
    return task.completed_at > task.deadline
