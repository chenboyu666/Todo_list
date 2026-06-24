from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
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


MAX_CLUSTERS_PER_TAG = 6
MAX_REPRESENTATIVE_TASKS_PER_CLUSTER = 3
MAX_OVERVIEW_TASKS_PER_TAG = 8


def build_history_graph_payload(tasks: list[Task], *, max_keywords: int = 18) -> dict[str, Any]:
    completed = [task for task in tasks if task.status == "done"]
    task_nodes: list[dict[str, Any]] = []
    task_keywords: dict[str, set[str]] = {}
    tag_counts: Counter[str] = Counter()
    title_counts: Counter[str] = Counter()
    task_tags: dict[str, str] = {}
    task_title_keywords: dict[str, set[str]] = {}

    for task in completed:
        tag = normalize_task_tag(task.tag)
        title_keywords = _extract_keywords(task.title)
        task_tags[task.id] = tag
        task_title_keywords[task.id] = title_keywords
        if tag:
            tag_counts.update([tag])
        title_counts.update(title_keywords)

    selected_tags = [tag for tag, _count in tag_counts.most_common()]
    tag_set = set(selected_tags)
    selected_title_keywords = [
        word for word, count in title_counts.most_common() if count >= 2 and word not in tag_set
    ][:max_keywords]
    keyword_set = set(selected_tags) | set(selected_title_keywords)

    for task in completed:
        keywords = {task_tags[task.id]} | (task_title_keywords[task.id] & set(selected_title_keywords))
        keywords.discard("")
        task_keywords[task.id] = keywords
        task_nodes.append(
            {
                "id": task.id,
                "title": task.title,
                "tag": task_tags[task.id],
                "priority": task.priority,
                "priorityText": priority_text(task.priority),
                "late": _task_completed_late(task),
                "seconds": work_elapsed_seconds(task, task.completed_at or task.updated_at),
                "completedAt": (task.completed_at or task.updated_at).isoformat(),
                "words": sorted(keywords),
            }
        )

    keyword_nodes: list[dict[str, Any]] = [
        {
            "id": f"k-{_keyword_id(tag)}",
            "word": tag,
            "count": tag_counts[tag],
            "source": "tag",
        }
        for tag in selected_tags
    ]
    keyword_nodes.extend(
        {
            "id": f"k-{_keyword_id(word)}",
            "word": word,
            "count": title_counts[word],
            "source": "title",
        }
        for word in selected_title_keywords
    )

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

    clusters, cluster_links = _build_task_clusters(
        completed,
        task_nodes,
        task_tags=task_tags,
        task_title_keywords=task_title_keywords,
        selected_tags=selected_tags,
    )
    tag_summaries, overview_nodes, tag_task_links = _build_tag_overview_payload(
        completed,
        task_tags=task_tags,
        selected_tags=selected_tags,
    )

    return {
        "tasks": task_nodes,
        "keywords": keyword_nodes,
        "links": links,
        "clusters": clusters,
        "clusterLinks": cluster_links,
        "tagSummaries": tag_summaries,
        "overviewNodes": overview_nodes,
        "tagTaskLinks": tag_task_links,
        "metrics": {
            "tasks": len(task_nodes),
            "keywords": len(keyword_nodes),
            "links": len(links) + len(cluster_links) + len(tag_task_links),
            "clusters": len(clusters),
        },
    }


def _build_tag_overview_payload(
    completed: list[Task],
    *,
    task_tags: dict[str, str],
    selected_tags: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    tasks_by_tag: dict[str, list[Task]] = defaultdict(list)
    for task in completed:
        tag = task_tags.get(task.id, "")
        if tag:
            tasks_by_tag[tag].append(task)

    tag_summaries: list[dict[str, Any]] = []
    overview_nodes: list[dict[str, Any]] = []
    tag_task_links: list[dict[str, Any]] = []

    for tag in selected_tags:
        tag_tasks = sorted(
            tasks_by_tag.get(tag, []),
            key=lambda task: (task.completed_at or task.updated_at),
            reverse=True,
        )
        if not tag_tasks:
            continue
        recent_tasks = tag_tasks[:MAX_OVERVIEW_TASKS_PER_TAG]
        hidden_tasks = tag_tasks[MAX_OVERVIEW_TASKS_PER_TAG:]
        hidden_node_id = f"more-{_keyword_id(tag)}"
        tag_node_id = f"k-{_keyword_id(tag)}"
        recent_task_ids = [task.id for task in recent_tasks]
        hidden_task_ids = [task.id for task in hidden_tasks]

        tag_summaries.append(
            {
                "tag": tag,
                "count": len(tag_tasks),
                "recentTaskIds": recent_task_ids,
                "hiddenTaskIds": hidden_task_ids,
                "hiddenCount": len(hidden_tasks),
                "hiddenNodeId": hidden_node_id if hidden_tasks else "",
            }
        )
        tag_task_links.extend(
            {"source": tag_node_id, "target": task_id, "kind": "tag-task"}
            for task_id in recent_task_ids
        )
        if hidden_tasks:
            overview_nodes.append(
                {
                    "id": hidden_node_id,
                    "type": "more",
                    "tag": tag,
                    "title": f"更多任务 · {len(hidden_tasks)}",
                    "count": len(hidden_tasks),
                    "taskIds": hidden_task_ids,
                }
            )
            tag_task_links.append({"source": tag_node_id, "target": hidden_node_id, "kind": "tag-more"})

    return tag_summaries, overview_nodes, tag_task_links


def _build_task_clusters(
    completed: list[Task],
    task_nodes: list[dict[str, Any]],
    *,
    task_tags: dict[str, str],
    task_title_keywords: dict[str, set[str]],
    selected_tags: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks_by_tag: dict[str, list[Task]] = defaultdict(list)
    for task in completed:
        tag = task_tags.get(task.id, "")
        if tag:
            tasks_by_tag[tag].append(task)

    task_node_map = {node["id"]: node for node in task_nodes}
    clusters: list[dict[str, Any]] = []
    cluster_links: list[dict[str, Any]] = []

    for tag in selected_tags:
        tag_tasks = tasks_by_tag.get(tag, [])
        if not tag_tasks:
            continue
        cluster_words = _cluster_words_for_tag(tag_tasks, task_title_keywords, tag)
        assignments: dict[str, list[Task]] = {word: [] for word in cluster_words}
        other_tasks: list[Task] = []

        for task in tag_tasks:
            title_words = task_title_keywords.get(task.id, set())
            matched_word = next((word for word in cluster_words if word in title_words), None)
            if matched_word is None:
                other_tasks.append(task)
            else:
                assignments[matched_word].append(task)

        ordered_groups: list[tuple[str, list[Task]]] = [
            (word, grouped) for word, grouped in assignments.items() if grouped
        ]
        if other_tasks:
            ordered_groups.append(("其它任务", other_tasks))
        if not ordered_groups:
            ordered_groups = [("其它任务", tag_tasks)]

        for name, grouped_tasks in ordered_groups[:MAX_CLUSTERS_PER_TAG]:
            cluster_id = f"c-{_keyword_id(tag)}-{_keyword_id(name)}"
            representative_ids = [
                task.id for task in _representative_tasks(grouped_tasks)[:MAX_REPRESENTATIVE_TASKS_PER_CLUSTER]
            ]
            task_ids = [task.id for task in grouped_tasks]
            cluster_seconds = sum(int(task_node_map[task_id]["seconds"]) for task_id in task_ids if task_id in task_node_map)
            late_count = sum(1 for task_id in task_ids if task_node_map.get(task_id, {}).get("late"))
            clusters.append(
                {
                    "id": cluster_id,
                    "name": name,
                    "tag": tag,
                    "count": len(grouped_tasks),
                    "taskIds": task_ids,
                    "representativeIds": representative_ids,
                    "seconds": cluster_seconds,
                    "lateCount": late_count,
                }
            )
            cluster_links.append(
                {
                    "source": f"k-{_keyword_id(tag)}",
                    "target": cluster_id,
                    "kind": "tag-cluster",
                }
            )
            cluster_links.extend(
                {
                    "source": cluster_id,
                    "target": task_id,
                    "kind": "cluster-task",
                }
                for task_id in representative_ids
            )

    return clusters, cluster_links


def _cluster_words_for_tag(tasks: list[Task], task_title_keywords: dict[str, set[str]], tag: str) -> list[str]:
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    order = 0
    for task in tasks:
        for word in _extract_keywords_in_order(task.title):
            if word == tag or word not in task_title_keywords.get(task.id, set()):
                continue
            counts.update([word])
            first_seen.setdefault(word, order)
            order += 1
    return [
        word
        for word, count in sorted(counts.items(), key=lambda item: (-item[1], first_seen.get(item[0], 9999), item[0]))
        if count >= 2
    ][:MAX_CLUSTERS_PER_TAG]


def _representative_tasks(tasks: list[Task]) -> list[Task]:
    priority_rank = {"P1": 0, "P2": 1, "P3": 2}
    return sorted(
        tasks,
        key=lambda task: (
            not _task_completed_late(task),
            priority_rank.get(task.priority, 9),
            -(task.completed_at or task.updated_at).timestamp(),
        ),
    )


def render_history_graph_html(payload: dict[str, Any]) -> str:
    graph_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    is_empty = not payload.get("tasks") and not payload.get("keywords")
    body_class = "is-empty" if is_empty else ""
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
    html {{ background:#071421; }}
    body {{
      margin:0; width:100vw; height:100vh; overflow:hidden; color:var(--text);
      background-color:#071421;
      background:radial-gradient(circle at 18% 16%,rgba(50,220,255,.12),transparent 28%),
        radial-gradient(circle at 72% 18%,rgba(167,139,250,.09),transparent 30%),
        linear-gradient(145deg,#04101e,#071b2c 58%,#0A3741);
    }}
    canvas {{ position:fixed; inset:0; width:100vw; height:100vh; display:block; cursor:grab; background:#071421; }}
    canvas:active {{ cursor:grabbing; }}
    body.is-empty canvas {{ cursor:default; }}
    .empty-state {{
      position:fixed; inset:0; display:none; place-items:center; padding:28px;
      pointer-events:none;
    }}
    body.is-empty .empty-state {{ display:grid; }}
    .empty-card {{
      width:min(520px, calc(100vw - 56px)); min-height:190px; border-radius:24px;
      display:grid; place-items:center; text-align:center; padding:28px;
      background:linear-gradient(145deg,rgba(6,22,36,.86),rgba(8,48,62,.70));
      box-shadow:0 28px 80px rgba(0,0,0,.24), inset 0 0 0 1px rgba(78,207,255,.18);
    }}
    .empty-orbit {{
      width:68px; height:68px; border-radius:50%; margin:0 auto 16px;
      background:radial-gradient(circle,rgba(50,220,255,.62),rgba(50,220,255,.12) 46%,transparent 48%),
        conic-gradient(from 30deg,rgba(50,220,255,.0),rgba(50,220,255,.76),rgba(167,139,250,.55),rgba(50,220,255,.0));
      box-shadow:0 0 34px rgba(50,220,255,.28);
    }}
    .empty-card h2 {{ margin:0; font-size:22px; line-height:1.2; }}
    .empty-card p {{ margin:10px auto 0; max-width:360px; color:var(--soft); line-height:1.6; font-size:13px; font-weight:850; }}
    .hud {{ position:fixed; inset:12px; pointer-events:none; display:grid; grid-template-columns:250px minmax(360px,1fr) 300px; gap:12px; }}
    .glass {{
      pointer-events:auto; border:1px solid var(--line); border-radius:22px;
      background:linear-gradient(145deg,rgba(3,11,21,.82),rgba(7,26,40,.58));
      box-shadow:0 24px 78px rgba(0,0,0,.32), inset 0 0 0 1px rgba(255,255,255,.018);
    }}
    .left {{ align-self:start; padding:14px; }}
    .top {{ grid-column:2; justify-self:stretch; align-self:start; min-width:360px; padding:12px 14px; display:flex; justify-content:space-between; gap:12px; }}
    .right {{ align-self:stretch; padding:14px; min-height:0; overflow:hidden; display:grid; grid-template-rows:auto auto minmax(0,1fr) auto; gap:10px; }}
    h1,h2,p {{ margin:0; }} h1 {{ font-size:17px; line-height:1.2; }} h2 {{ font-size:15px; margin-bottom:8px; }}
    .sub {{ color:var(--muted); margin-top:6px; line-height:1.45; font-size:12px; font-weight:800; }}
    .chips {{ display:flex; gap:7px; flex-wrap:wrap; margin-top:10px; }}
    .chip {{ min-height:26px; display:inline-flex; align-items:center; border-radius:9px; padding:0 9px; color:var(--soft); background:rgba(5,15,28,.76); box-shadow:inset 0 0 0 1px rgba(78,207,255,.12); font-size:11px; font-weight:900; }}
    .legend {{ display:grid; gap:8px; margin-top:12px; }}
    .legend-item {{ display:grid; grid-template-columns:12px 1fr auto; gap:10px; align-items:center; color:var(--soft); font-size:12px; font-weight:850; }}
    .dot {{ width:10px; height:10px; border-radius:50%; box-shadow:0 0 14px currentColor; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
    .metric {{ padding:10px; border-radius:14px; background:rgba(4,13,24,.72); box-shadow:inset 0 0 0 1px rgba(78,207,255,.10); }}
    .metric b {{ display:block; font-size:19px; line-height:1; }} .metric span {{ display:block; margin-top:6px; color:var(--muted); font-size:11px; font-weight:850; }}
    .back-button {{ border:0; min-height:34px; border-radius:12px; padding:0 12px; color:var(--soft); background:rgba(5,15,28,.82); box-shadow:inset 0 0 0 1px rgba(78,207,255,.13); font-size:12px; font-weight:900; cursor:pointer; }}
    .back-button:hover {{ color:var(--text); box-shadow:inset 0 0 0 1px rgba(50,220,255,.38),0 10px 26px rgba(0,0,0,.22); }}
    .back-button[hidden] {{ display:none; }}
    .shortcut-hint {{
      position:fixed; left:50%; bottom:18px; transform:translateX(-50%); z-index:4;
      min-height:34px; display:flex; align-items:center; justify-content:center; padding:0 14px;
      border-radius:14px; color:rgba(214,241,252,.90); background:rgba(3,14,26,.66);
      box-shadow:inset 0 0 0 1px rgba(78,207,255,.14),0 14px 36px rgba(0,0,0,.24);
      font-size:12px; font-weight:900; pointer-events:none;
    }}
    .selected {{ border-radius:16px; padding:12px; background:rgba(4,13,24,.74); box-shadow:inset 0 0 0 1px rgba(78,207,255,.13); }}
    .selected-title {{ font-size:17px; font-weight:950; line-height:1.32; }} .selected-type {{ margin-top:8px; color:var(--muted); font-size:12px; font-weight:850; }}
    .context-header {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
    .context-header h2 {{ margin:0; }}
    .mini-toggle {{ border:0; min-height:30px; border-radius:10px; padding:0 10px; color:var(--soft); background:rgba(5,15,28,.82); box-shadow:inset 0 0 0 1px rgba(78,207,255,.13); font-size:11px; font-weight:900; cursor:pointer; }}
    .mini-toggle:hover {{ color:var(--text); box-shadow:inset 0 0 0 1px rgba(50,220,255,.38),0 10px 26px rgba(0,0,0,.22); }}
    .queue {{ min-height:0; overflow:auto; display:flex; flex-direction:column; gap:8px; padding-right:2px; }}
    .task-card {{ border:0; color:var(--text); text-align:left; cursor:pointer; border-radius:13px; padding:10px; background:rgba(4,13,24,.58); box-shadow:inset 0 0 0 1px rgba(78,207,255,.09); }}
    .task-card:hover,.task-card.active {{ box-shadow:inset 0 0 0 1px rgba(50,220,255,.34),0 14px 28px rgba(0,0,0,.18); }}
    .task-card strong {{ display:block; font-size:13px; line-height:1.45; }} .task-card span {{ display:inline-block; margin-top:8px; margin-right:6px; padding:5px 7px; border-radius:8px; color:var(--muted); background:rgba(7,22,34,.82); font-size:11px; font-weight:850; }}
    .ops {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }} .ops button {{ border:0; min-height:38px; border-radius:12px; color:var(--soft); background:rgba(5,15,28,.82); box-shadow:inset 0 0 0 1px rgba(78,207,255,.13); font-weight:900; cursor:pointer; }} .ops button:hover {{ color:var(--text); box-shadow:inset 0 0 0 1px rgba(50,220,255,.38),0 10px 26px rgba(0,0,0,.22); }} .ops button:disabled {{ cursor:not-allowed; opacity:.42; }}
  </style>
</head>
<body class=\"{body_class}\">
  <canvas id=\"graph\"></canvas>
  <div id=\"shortcutHint\" class=\"shortcut-hint\">单击标签查看全部 · 双击标签进入 · Esc 返回 · 滚轮缩放</div>
  <div class=\"empty-state\"><section class=\"empty-card\"><div class=\"empty-orbit\"></div><h2>暂无已完成任务</h2><p>完成任务后会自动生成关系图，用标签和高频主题词展示任务之间的连接。</p></section></div>
  <div class=\"hud\">
    <section class=\"glass left\"><h1>任务关系图图例</h1><p class=\"sub\">每个小点是一条已完成任务；标签是分类中心；高频主题词来自反复出现的任务名称。</p><div class=\"chips\"><span class=\"chip\">拖动旋转</span><span class=\"chip\">滚轮缩放</span><span class=\"chip\">点击查看</span></div><div class=\"legend\"><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--cyan);background:var(--cyan)\"></i><span>已完成任务</span><b id=\"legendTasks\">0</b></div><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--gold);background:var(--gold)\"></i><span>标签</span><b id=\"legendTagKeywords\">0</b></div><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--violet);background:var(--violet)\"></i><span>高频主题词</span><b id=\"legendTitleKeywords\">0</b></div><div class=\"legend-item\"><i class=\"dot\" style=\"color:var(--rose);background:var(--rose)\"></i><span>超时标记</span><b id=\"legendLate\">0</b></div></div></section>
    <section class=\"glass top\"><div><h1>Obsidian 风格历史洞察</h1><p class=\"sub\">用关系发现可合并的项目、孤立记录和需要补标签的任务。</p></div><button id=\"backButton\" class=\"back-button\" type=\"button\" hidden>返回总览</button><div class=\"metric-grid\"><div class=\"metric\"><b id=\"metricNodes\">0</b><span>节点</span></div><div class=\"metric\"><b id=\"metricLinks\">0</b><span>连接</span></div><div class=\"metric\"><b id=\"metricGroups\">0</b><span>主题簇</span></div></div></section>
    <aside class=\"glass right\"><div><h2>节点详情</h2><div class=\"selected\"><div id=\"selectedTitle\" class=\"selected-title\">点击一个点</div><div id=\"selectedType\" class=\"selected-type\">选择任务可补备注/改标签；选择标签或任务簇会列出对应任务。</div><div id=\"selectedChips\" class=\"chips\"></div></div></div><div class=\"context-header\"><h2 id=\"contextTitle\">关联任务</h2><button id=\"expandToggle\" class=\"mini-toggle\" type=\"button\">展开全部</button></div><div id=\"taskQueue\" class=\"queue\"></div><div class=\"ops\"><button id=\"noteButton\" type=\"button\">补备注</button><button id=\"tagButton\" type=\"button\">改标签</button><button id=\"exportButton\" type=\"button\">导出</button></div></aside>
  </div>
  <script src=\"qrc:///qtwebchannel/qwebchannel.js\"></script>
  <script>
    const GRAPH_PAYLOAD = {graph_json};
    const canvas = document.getElementById('graph');
    const ctx = canvas.getContext('2d');
    let historyBridge = null;
    if (window.qt && window.QWebChannel) {{
      new QWebChannel(qt.webChannelTransport, channel => {{ historyBridge = channel.objects.historyBridge; }});
    }}
    function callBridge(method, ...args) {{ if (historyBridge && historyBridge[method]) historyBridge[method](...args); }}
    const tasks = GRAPH_PAYLOAD.tasks || [];
    const keywords = GRAPH_PAYLOAD.keywords || [];
    const links = GRAPH_PAYLOAD.links || [];
    const clusters = GRAPH_PAYLOAD.clusters || [];
    const clusterLinks = GRAPH_PAYLOAD.clusterLinks || [];
    const tagSummaries = GRAPH_PAYLOAD.tagSummaries || [];
    const overviewNodes = GRAPH_PAYLOAD.overviewNodes || [];
    const tagTaskLinks = GRAPH_PAYLOAD.tagTaskLinks || [];
    const nodes = [];
    const nodeMap = new Map();
    const taskMap = new Map(tasks.map(task => [task.id, task]));
    const clusterMap = new Map(clusters.map(cluster => [cluster.id, cluster]));
    const tagSummaryMap = new Map(tagSummaries.map(summary => [summary.tag, summary]));
    const recentTaskIds = new Set(tagSummaries.flatMap(summary => summary.recentTaskIds || []));
    const representativeTaskIds = new Set(clusters.flatMap(cluster => cluster.representativeIds || []));
    const tagKeywords=keywords.filter(keyword=>keyword.source==='tag');
    const TAG_OVERVIEW_RADIUS=Math.min(250,170+tagKeywords.length*10);
    const TAG_OVERVIEW_Y_SPREAD=40;
    const OVERVIEW_TASK_DISTANCE_BASE=72;
    const OVERVIEW_TASK_DISTANCE_STEP=20;
    const OVERVIEW_MORE_DISTANCE=102;
    const OVERVIEW_TAG_ANCHOR_STRENGTH=.018;
    const OVERVIEW_CHILD_ANCHOR_STRENGTH=.045;
    let showExpandedTasks = false;
    let graphLayer = 'overview';
    let activeTag = null;
    let panX = 0, panY = 0, frameTick = 0, transitionUntil = 0;
    function addNode(node) {{ nodes.push(node); nodeMap.set(node.id, node); }}
    function keywordColor(source) {{ return source==='tag'?'#f4b45f':'#a78bfa'; }}
    function keywordRadius(keyword) {{ return keyword.source==='tag'?12.5+Math.min(8,keyword.count)*1.6:8.8+keyword.count*1.1; }}
    function clusterColor(cluster) {{ return cluster.lateCount ? '#38bdf8' : '#22d3ee'; }}
    function clusterRadius(cluster) {{ return 10.5 + Math.min(20, cluster.count * 1.45); }}
    function keywordLabelStyle(source,scale) {{
      if(source==='tag') return {{font:`900 ${{Math.max(12,14*scale)}}px Microsoft YaHei UI`,fill:'rgba(255,223,178,.96)'}};
      return {{font:`850 ${{Math.max(11,12.6*scale)}}px Microsoft YaHei UI`,fill:'rgba(226,218,255,.9)'}};
    }}
    function tagNodeId(tag) {{ return 'k-'+String(tag||'').replace(/[^a-zA-Z0-9_\\-\\u4e00-\\u9fff]+/g,'-').replace(/^-+|-+$/g,'').toLowerCase(); }}
    function taskCluster(taskId) {{ return clusters.find(cluster => (cluster.taskIds||[]).includes(taskId)); }}
    function auxiliaryMoreNode(summary) {{ return {{id:summary.hiddenNodeId,type:'more',tag:summary.tag,title:`更多任务 · ${{summary.hiddenCount}}`,count:summary.hiddenCount,taskIds:summary.hiddenTaskIds||[]}}; }}
    function stableHash(value) {{ let h=0; for(const ch of String(value||'')) h=(h*31+ch.charCodeAt(0))>>>0; return h; }}
    function addOverviewNodes() {{
      tagKeywords.forEach((keyword,index)=>{{ const target=overviewTagTarget({{tagIndex:index,tagCount:tagKeywords.length}}); addNode({{...keyword,title:keyword.word,type:'keyword',tagIndex:index,tagCount:tagKeywords.length,color:keywordColor(keyword.source),radius:keywordRadius(keyword),x:target.x,y:target.y,z:target.z,vx:0,vy:0,vz:0}}); }});
      overviewNodes.forEach(node=>addNode({{...node,color:'#9db6c8',radius:10+Math.min(18,node.count*1.2),x:0,y:0,z:0,vx:0,vy:0,vz:0}}));
      tasks.forEach((task, index) => {{ const cluster=taskCluster(task.id); addNode({{...task,type:'task',representative:recentTaskIds.has(task.id)||representativeTaskIds.has(task.id),clusterId:cluster?cluster.id:null,color:task.late?'#ff6f91':'#32dcff',radius:task.late?7.2:6.4,x:Math.cos(index*1.72)*42,y:Math.sin(index*.91)*22,z:Math.sin(index*1.37)*42,vx:0,vy:0,vz:0}}); }});
    }}
    addOverviewNodes();
    const INITIAL_ZOOM=1.08;
    let width=0,height=0,rotX=-.14,rotY=.58,zoom=INITIAL_ZOOM,drag=null,panDrag=null,selected=null,projected=[];
    function resize() {{ const dpr=Math.min(devicePixelRatio||1,2); width=innerWidth; height=innerHeight; canvas.width=Math.floor(width*dpr); canvas.height=Math.floor(height*dpr); ctx.setTransform(dpr,0,0,dpr,0,0); }}
    let simEnergy=Infinity;
    function summaryTasks(tag) {{ const summary=tagSummaryMap.get(tag); if(!summary) return []; return (summary.recentTaskIds||[]).concat(summary.hiddenTaskIds||[]).map(id=>taskMap.get(id)).filter(Boolean); }}
    function hiddenTasks(tag) {{ const summary=tagSummaryMap.get(tag); return summary ? (summary.hiddenTaskIds||[]).map(id=>taskMap.get(id)).filter(Boolean) : []; }}
    function activeLinks() {{ if(graphLayer==='tag'&&activeTag) return summaryTasks(activeTag).map(task=>({{source:tagNodeId(activeTag),target:task.id,kind:'tag-detail'}})); return tagTaskLinks; }}
    function expandedTaskLinks() {{ if(!showExpandedTasks||!selected) return []; const cluster = selected.type==='cluster' ? selected : selected.type==='task' ? clusterMap.get(selected.clusterId) : null; if(!cluster) return []; return (cluster.taskIds||[]).filter(id=>!representativeTaskIds.has(id)).map(id=>({{source:cluster.id,target:id,kind:'cluster-task-expanded'}})); }}
    function isVisibleNode(n) {{ if(graphLayer==='tag') return (n.type==='keyword'&&n.word===activeTag)||(n.type==='task'&&n.tag===activeTag); if(n.type==='keyword') return n.source==='tag'; if(n.type==='more') return true; if(n.type==='task') return recentTaskIds.has(n.id); return false; }}
    function selectedNeighborhood(n) {{ if(!selected) return false; if(n.id===selected.id) return true; if(selected.type==='keyword') return (n.type==='task'&&n.tag===selected.word)||(n.type==='more'&&n.tag===selected.word)||(n.type==='cluster'&&n.tag===selected.word)||(n.type==='task'&&clusterMap.get(n.clusterId)?.tag===selected.word); if(selected.type==='more') return n.tag===selected.tag; if(selected.type==='cluster') return n.id===selected.id||n.clusterId===selected.id||activeLinks().some(l=>(l.source===selected.id&&l.target===n.id)||(l.target===selected.id&&l.source===n.id)); if(selected.type==='task') return n.id===tagNodeId(selected.tag)||n.tag===selected.tag||n.id===selected.clusterId||n.clusterId===selected.clusterId; return false; }}
    function focusAlpha(n) {{ if(graphLayer==='overview'&&n.type==='keyword') return 1; if(!selected) return n.type==='more'?.72:.58; return selectedNeighborhood(n)?1:.25; }}
    function overviewTagTarget(n) {{
      const total=Math.max(1,n.tagCount||tagKeywords.length||1); const index=Math.max(0,n.tagIndex||0);
      const angle=index/total*Math.PI*2 + (total>2?-.18:.12);
      return {{x:Math.cos(angle)*TAG_OVERVIEW_RADIUS,y:Math.sin(index*1.4)*TAG_OVERVIEW_Y_SPREAD,z:Math.sin(angle)*TAG_OVERVIEW_RADIUS}};
    }}
    function overviewChildTarget(n) {{
      const summary=tagSummaryMap.get(n.tag); const tagNode=summary?nodeMap.get(tagNodeId(summary.tag)):null; if(!summary||!tagNode) return;
      const allIds=(summary.recentTaskIds||[]).concat(summary.hiddenNodeId?[summary.hiddenNodeId]:[]);
      const idx=Math.max(0,allIds.indexOf(n.id)); const a=(idx/Math.max(1,allIds.length))*Math.PI*2 + stableHash(summary.tag)*.0007;
      const distance=n.type==='more'?OVERVIEW_MORE_DISTANCE:OVERVIEW_TASK_DISTANCE_BASE+(idx%3)*OVERVIEW_TASK_DISTANCE_STEP;
      return {{x:tagNode.x+Math.cos(a)*distance,y:tagNode.y+Math.sin(idx*.8)*15,z:tagNode.z+Math.sin(a)*distance}};
    }}
    function layoutOverviewNode(n) {{
      const target=(n.type==='keyword'&&n.source==='tag')?overviewTagTarget(n):overviewChildTarget(n);
      if(!target) return;
      n.x=target.x; n.y=target.y; n.z=target.z;
    }}
    function layoutTagLayerNode(n) {{
      if(n.type==='keyword') {{ n.x=0; n.y=0; n.z=0; return; }}
      if(n.type!=='task'||n.tag!==activeTag) return;
      const ordered=summaryTasks(activeTag).sort((a,b)=>String(b.completedAt||'').localeCompare(String(a.completedAt||'')));
      const index=Math.max(0,ordered.findIndex(task=>task.id===n.id)); const radius=54+index*16; const a=stableHash(n.id)*.012 + index*.76;
      n.x=Math.cos(a)*radius; n.y=Math.sin(index*.61)*34; n.z=Math.sin(a)*radius;
    }}
    function setLayerPositions() {{ nodes.forEach(n=>{{ if(graphLayer==='tag') layoutTagLayerNode(n); else layoutOverviewNode(n); n.vx=0; n.vy=0; n.vz=0; }}); simEnergy=Infinity; }}
    function updateShortcutHint() {{ shortcutHint.textContent=graphLayer==='tag'?'Esc 返回 · 滚轮平移 · Ctrl+滚轮缩放 · 单击任务查看':'单击标签查看全部 · 双击标签进入 · 滚轮平移 · Ctrl+滚轮缩放'; }}
    function enterTagLayer(tag) {{ if(!tagSummaryMap.has(tag)) return; graphLayer='tag'; activeTag=tag; panX=0; panY=0; transitionUntil=frameTick+36; backButton.hidden=false; selected=nodeMap.get(tagNodeId(tag))||selected; setLayerPositions(); renderQueue(selected); updateShortcutHint(); scheduleFrame(); }}
    function returnToOverview() {{ graphLayer='overview'; activeTag=null; panX=0; panY=0; selected=null; transitionUntil=frameTick+28; backButton.hidden=true; setLayerPositions(); renderQueue(selected); updateShortcutHint(); scheduleFrame(); }}
    function applyOverviewAnchorForces() {{ if(graphLayer!=='overview') return; for(const n of nodes){{ if(!isVisibleNode(n)) continue; const isTag=n.type==='keyword'&&n.source==='tag'; const target=isTag?overviewTagTarget(n):(n.type==='task'||n.type==='more')?overviewChildTarget(n):null; if(!target) continue; const strength=isTag?OVERVIEW_TAG_ANCHOR_STRENGTH:OVERVIEW_CHILD_ANCHOR_STRENGTH; n.vx+=(target.x-n.x)*strength; n.vy+=(target.y-n.y)*strength; n.vz+=(target.z-n.z)*strength; }} }}
    function step() {{ for (const n of nodes) {{ if(!isVisibleNode(n)) continue; n.vx+=-n.x*.00016; n.vy+=-n.y*.00016; n.vz+=-n.z*.00016; }} for(let i=0;i<nodes.length;i++){{ for(let j=i+1;j<nodes.length;j++){{ const a=nodes[i],b=nodes[j]; if(!isVisibleNode(a)||!isVisibleNode(b)) continue; const dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z,d2=Math.max(480,dx*dx+dy*dy+dz*dz),f=5.8/d2; a.vx+=dx*f; a.vy+=dy*f; a.vz+=dz*f; b.vx-=dx*f; b.vy-=dy*f; b.vz-=dz*f; }} }} applyOverviewAnchorForces(); simEnergy=0; for(const n of nodes){{ if(!isVisibleNode(n)) continue; const damp=(selected&&n.id===selected.id) ? .22 : selectedNeighborhood(n) ? .50 : .76; n.vx*=damp; n.vy*=damp; n.vz*=damp; n.x+=n.vx; n.y+=n.vy; n.z+=n.vz; simEnergy+=n.vx*n.vx+n.vy*n.vy+n.vz*n.vz; }} }}
    function project(n) {{ const cy=Math.cos(rotY),sy=Math.sin(rotY),cx=Math.cos(rotX),sx=Math.sin(rotX); let x=n.x*cy-n.z*sy,z=n.x*sy+n.z*cy,y=n.y*cx-z*sx; z=n.y*sx+z*cx; const p=620/(620+z); return {{node:n,x:width*.52+x*p*zoom+panX,y:height*.55+y*p*zoom+panY,z,scale:p*zoom}}; }}
    function rgba(hex,a) {{ const v=hex.replace('#',''),r=parseInt(v.slice(0,2),16),g=parseInt(v.slice(2,4),16),b=parseInt(v.slice(4,6),16); return `rgba(${{r}},${{g}},${{b}},${{a}})`; }}
    function drawBackground() {{ const bg=ctx.createRadialGradient(width/2,height/2,0,width/2,height/2,Math.max(width,height)*.62); bg.addColorStop(0,'rgba(15,45,66,.34)'); bg.addColorStop(1,'rgba(1,5,11,0)'); ctx.fillStyle=bg; ctx.fillRect(0,0,width,height); ctx.strokeStyle='rgba(78,207,255,.035)'; ctx.lineWidth=1; for(let x=-44;x<width+44;x+=44){{ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,height); ctx.stroke(); }} for(let y=-44;y<height+44;y+=44){{ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(width,y); ctx.stroke(); }} }}
    function draw() {{ frameTick++; ctx.clearRect(0,0,width,height); drawBackground(); projected=nodes.filter(isVisibleNode).map(project).sort((a,b)=>a.z-b.z); const pm=new Map(projected.map(p=>[p.node.id,p])); for(const l of activeLinks()){{ const a=pm.get(l.source),b=pm.get(l.target); if(!a||!b) continue; const active=selected&&(selected.id===l.source||selected.id===l.target||selected.id===a.node.tag||selected.tag===b.node.tag); ctx.strokeStyle=active?'rgba(50,220,255,.68)':l.kind==='tag-more'?'rgba(157,182,200,.20)':l.kind==='tag-task'?'rgba(244,180,95,.18)':'rgba(78,207,255,.16)'; ctx.lineWidth=active?1.9:l.kind==='tag-more'?1.05:.9; ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); }} for(const p of projected){{ const n=p.node,r=Math.max(3.5,n.radius*p.scale),active=selected&&selected.id===n.id,keyword=n.type==='keyword',cluster=n.type==='cluster',more=n.type==='more',alpha=focusAlpha(n); const glowRadius=keyword?(active?3.1:2.35):cluster?(active?3.5:2.55):more?2.35:(active?4.8:n.late?3.9:3.0); const glow=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,r*glowRadius); glow.addColorStop(0,rgba(n.color,(active ? (keyword ? .36 : .46) : (keyword ? .2 : cluster ? .16 : .18))*alpha)); glow.addColorStop(.42,rgba(n.color,(active ? (keyword ? .12 : .16) : (keyword ? .07 : .07))*alpha)); glow.addColorStop(1,rgba(n.color,0)); ctx.fillStyle=glow; ctx.beginPath(); ctx.arc(p.x,p.y,r*glowRadius,0,Math.PI*2); ctx.fill(); }} for(const p of projected){{ const n=p.node,r=Math.max(3.5,n.radius*p.scale),keyword=n.type==='keyword',cluster=n.type==='cluster',more=n.type==='more',active=selected&&selected.id===n.id,alpha=focusAlpha(n); ctx.fillStyle=rgba(n.color,(keyword ? .9 : more ? .62 : cluster ? .72 : .82)*alpha); ctx.beginPath(); ctx.arc(p.x,p.y,r,0,Math.PI*2); ctx.fill(); if(keyword){{ ctx.strokeStyle=alpha<1?'rgba(255,232,190,.26)':'rgba(255,232,190,.74)'; ctx.lineWidth=1.2; ctx.beginPath(); ctx.arc(p.x,p.y,r*1.62,0,Math.PI*2); ctx.stroke(); }} else if(cluster){{ ctx.strokeStyle=alpha<1?'rgba(186,230,253,.18)':'rgba(186,230,253,.44)'; ctx.lineWidth=1.15; ctx.beginPath(); ctx.arc(p.x,p.y,r*1.36,0,Math.PI*2); ctx.stroke(); }} else {{ ctx.strokeStyle=alpha<1?'rgba(196,250,255,.18)':'rgba(196,250,255,.78)'; ctx.lineWidth=1.25; ctx.beginPath(); ctx.arc(p.x,p.y,r*1.18,0,Math.PI*2); ctx.stroke(); }} const showLabel=keyword||more||active||graphLayer==='tag'; if(showLabel){{ const style=keyword?keywordLabelStyle(n.source,p.scale):more?{{font:`900 ${{Math.max(10.5,11.8*p.scale)}}px Microsoft YaHei UI`,fill:'rgba(196,218,230,.88)'}}:{{font:`850 ${{Math.max(10.5,12*p.scale)}}px Microsoft YaHei UI`,fill:'rgba(210,250,255,.95)'}}; ctx.font=style.font; ctx.fillStyle=alpha<1?'rgba(139,173,190,.42)':style.fill; ctx.textAlign='center'; const label=more?n.title:keyword?n.word:n.title.slice(0,9); ctx.fillText(label,p.x,p.y+r+15); }} }} }}
    function clusterTasks(cluster) {{ return (cluster.taskIds||[]).map(id=>taskMap.get(id)).filter(Boolean); }}
    function related(n) {{ if(!n) return []; if(n.type==='cluster') return clusterTasks(n); if(n.type==='more') return summaryTasks(n.tag); if(n.type==='keyword') return n.source==='tag'?summaryTasks(n.word):tasks.filter(t=>(t.words||[]).includes(n.word)); if(n.type==='task') return summaryTasks(n.tag); return []; }}
    function updateActions() {{ const isTask=selected&&selected.type==='task'; noteButton.disabled=!isTask; tagButton.disabled=!isTask; }}
    function openSelectedNotes() {{ if(selected&&selected.type==='task'&&historyBridge&&historyBridge.openNotes) historyBridge.openNotes(selected.id); }}
    function editSelectedTag() {{ if(selected&&selected.type==='task'&&historyBridge&&historyBridge.editTag) historyBridge.editTag(selected.id); }}
    function exportSelectedHistory() {{ if(historyBridge&&historyBridge.exportHistory) historyBridge.exportHistory(); }}
    function keywordSourceText(source) {{ return source==='tag'?'标签：任务的分类中心':'高频主题词：来自反复出现的任务名称'; }}
    function contextText(n,count) {{ if(graphLayer==='tag'&&activeTag) return `${{activeTag}} · 时间视图 · ${{count}} 条`; if(!n) return `关联任务 · ${{count}} 条`; if(n.type==='cluster') return `${{n.name}} · ${{count}} 条`; if(n.type==='keyword') return `${{n.word}} · 全部任务 ${{count}} 条`; if(n.type==='more') return `${{n.tag}} · 全部任务 ${{count}} 条`; if(n.type==='task') return `同标签任务 · ${{count}} 条`; return `关联任务 · ${{count}} 条`; }}
    function select(n) {{ if(!n) return; if(selected&&selected.id!==n.id) showExpandedTasks=false; selected=n; selectedTitle.textContent=n.type==='more'?n.title:n.type==='cluster'?`${{n.name}} · ${{n.count}}`:n.type==='keyword'?n.word:n.title; selectedType.textContent=n.type==='more'?`容量提示 · ${{n.tag}} 还有 ${{n.count}} 条未画出任务`:n.type==='cluster'?`任务簇 · 标签：${{n.tag}} · 关联 ${{related(n).length}} 条任务`:n.type==='keyword'?`${{keywordSourceText(n.source)}} · 关联 ${{related(n).length}} 条任务`:`已完成任务 · 标签：${{n.tag}} · ${{n.priorityText||n.priority}} · ${{n.late?'超时完成':'准时完成'}}`; selectedChips.innerHTML=''; (n.type==='more'?[n.tag,'更多任务']:n.type==='cluster'?[n.tag,n.name]:n.type==='keyword'?[n.word]:(n.words||[])).slice(0,5).forEach(w=>{{ const c=document.createElement('span'); c.className='chip'; c.textContent=w; selectedChips.appendChild(c); }}); renderQueue(n); updateActions(); scheduleFrame(); }}
    function renderQueue(n=selected) {{ const items=related(n); contextTitle.textContent=contextText(n,items.length); expandToggle.textContent=showExpandedTasks?'收起':'展开全部'; expandToggle.disabled=true; taskQueue.innerHTML=''; items.forEach(t=>{{ const b=document.createElement('button'); b.className=`task-card ${{selected&&selected.id===t.id?'active':''}}`; b.innerHTML=`<strong>${{t.title}}</strong><span>#${{t.tag}}</span><span>${{t.priorityText||t.priority}}</span><span>${{t.late?'超时':'准时'}}</span>`; b.onclick=()=>select(nodeMap.get(t.id)); taskQueue.appendChild(b); }}); }}
    function hit(x,y) {{ return [...projected].filter(p=>p.node.type!=='more').sort((a,b)=>b.z-a.z).find(p=>{{ const r=Math.max(8,p.node.radius*p.scale*2.4),dx=p.x-x,dy=p.y-y; return dx*dx+dy*dy<=r*r; }})?.node; }}
    canvas.addEventListener('pointerdown',e=>{{ if(e.button===1){{ panDrag={{x:e.clientX,y:e.clientY}}; canvas.setPointerCapture(e.pointerId); e.preventDefault(); return; }} const n=hit(e.clientX,e.clientY); if(n) select(n); drag={{x:e.clientX,y:e.clientY}}; canvas.setPointerCapture(e.pointerId); }});
    canvas.addEventListener('pointermove',e=>{{ if(panDrag){{ panX+=e.clientX-panDrag.x; panY+=e.clientY-panDrag.y; panDrag={{x:e.clientX,y:e.clientY}}; scheduleFrame(); return; }} if(!drag) return; rotY+=(e.clientX-drag.x)*.006; rotX+=(e.clientY-drag.y)*.004; rotX=Math.max(-1.15,Math.min(1.15,rotX)); drag={{x:e.clientX,y:e.clientY}}; scheduleFrame(); }});
    canvas.addEventListener('pointerup',()=>{{ drag=null; panDrag=null; scheduleFrame(); }});
    function panCanvasByWheel(e) {{ panX-=e.deltaX; panY-=e.deltaY; }}
    canvas.addEventListener('wheel',e=>{{ e.preventDefault(); if(e.ctrlKey){{ zoom*=e.deltaY>0 ? .92 : 1.08; zoom=Math.max(.64,Math.min(2.2,zoom)); }} else {{ panCanvasByWheel(e); }} scheduleFrame(); }},{{passive:false}});
    canvas.addEventListener('dblclick',e=>{{ const n=hit(e.clientX,e.clientY); if(n&&n.type==='keyword'&&n.source==='tag') enterTagLayer(n.word); }});
    addEventListener('contextmenu',e=>{{ e.preventDefault(); }});
    addEventListener('keydown',e=>{{ if(e.key==='Escape'&&graphLayer==='tag') returnToOverview(); }});
    noteButton.onclick=openSelectedNotes;
    tagButton.onclick=editSelectedTag;
    exportButton.onclick=exportSelectedHistory;
    backButton.onclick=returnToOverview;
    expandToggle.onclick=()=>{{ showExpandedTasks=!showExpandedTasks; renderQueue(selected); }};
    let frameQueued=false;
    function scheduleFrame() {{ if(frameQueued) return; frameQueued=true; requestAnimationFrame(animate); }}
    function animate() {{ frameQueued=false; if(simEnergy>0.008||drag||panDrag||transitionUntil>frameTick) {{ step(); step(); scheduleFrame(); }} draw(); }}
    legendTasks.textContent=tasks.length; legendTagKeywords.textContent=keywords.filter(k=>k.source==='tag').length; legendTitleKeywords.textContent=keywords.filter(k=>k.source==='title').length; legendLate.textContent=tasks.filter(t=>t.late).length; metricNodes.textContent=tasks.length+keywords.filter(k=>k.source==='tag').length+overviewNodes.length; metricLinks.textContent=tagTaskLinks.length; metricGroups.textContent=Math.max(1, Math.min(9, tagSummaries.length)); addEventListener('resize',()=>{{ resize(); scheduleFrame(); }}); resize(); setLayerPositions(); renderQueue(selected); updateActions(); animate();
  </script>
</body>
</html>"""


def _extract_keywords(text: str) -> set[str]:
    words = set(_extract_keywords_in_order(text))
    return {word for word in words if word and word not in STOP_WORDS and len(word) >= 2}


def _extract_keywords_in_order(text: str) -> list[str]:
    words = [_normalize_keyword(match) for match in re.findall(r"[A-Za-z0-9_+\-.#]+|[\u4e00-\u9fff]{2,}", text)]
    return [word for word in words if word and word not in STOP_WORDS and len(word) >= 2]


def _normalize_keyword(value: str) -> str:
    value = value.strip().lower()
    return re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", value)


def _keyword_id(word: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "-", word).strip("-").lower()


def _task_completed_late(task: Task) -> bool:
    if task.deadline is None or task.completed_at is None:
        return False
    return task.completed_at > task.deadline
