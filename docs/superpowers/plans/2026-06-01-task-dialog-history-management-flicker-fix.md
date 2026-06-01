# 新建任务快捷交互、历史记录管理与洞察频闪修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让新增任务窗口打开后可直接输入名称并点击优先级卡片选值，为历史记录补充改名和删除能力，同时保留 3D 图谱缓慢旋转并消除 HUD 面板频闪。

**Architecture:** 在现有 PySide6 组件内做局部增强，不修改任务 JSON 结构。`TaskDialog` 负责首焦点和优先级卡片双向同步；`HistoryWindow` 负责历史任务改名、删除、存储和统一刷新；`history_graph.py` 只调整 WebEngine HTML 的 CSS 与 canvas 绘制策略，不改变图谱数据和 WebChannel 协议。

**Tech Stack:** Python 3.10、PySide6、Qt Widgets、Qt WebEngine、PyInstaller、pytest。

---

## 文件结构与职责

- Modify: `src/floating_todo/ui/task_dialog.py`
  - 新增可点击优先级预览卡。
  - 新增预览卡与下拉框的双向同步。
  - 在窗口显示后聚焦名称输入框。
- Modify: `tests/test_task_dialog.py`
  - 覆盖新建与编辑任务首焦点。
  - 覆盖高、中、低卡片点击、下拉框反向同步和可访问属性。
- Modify: `src/floating_todo/ui/history_window.py`
  - 在历史卡片更多操作菜单中新增改名和删除。
  - 复用现有 `store.save_tasks()` 与 `_render()`。
  - 删除后刷新标签选项，交给现有分页同步逻辑回退页码。
- Modify: `tests/test_history_workspace.py`
  - 覆盖历史菜单、改名边界、删除确认、标签筛选、分页和洞察 HTML 刷新。
- Modify: `src/floating_todo/ui/history_graph.py`
  - 保留自动旋转。
  - 移除 HUD 毛玻璃实时模糊和节点呼吸脉冲。
- Existing behavior to verify: `src/floating_todo/ui/main_window.py`
  - `open_history()` 关闭历史窗口后已调用 `self.refresh()`，会从 store 重新载入任务。本轮不修改，只在完整回归中验证。

## Task 0: 隔离执行环境并确认基线

**Files:**
- Inspect only: `src/floating_todo/ui/task_dialog.py`
- Inspect only: `src/floating_todo/ui/history_window.py`
- Inspect only: `src/floating_todo/ui/history_graph.py`

- [ ] **Step 1: 使用独立 worktree，避免覆盖当前工作区已有修改**

先调用 `using-git-worktrees` skill。当前主工作区存在与本轮无关的修改和未跟踪文件，执行时不得在主工作区直接实现。按 skill 先检测是否已经位于隔离工作区；如果仍在普通仓库且没有既定偏好，先向用户请求创建 worktree 的同意。

用户同意且没有平台原生 worktree 工具时，验证 `.worktrees` 已被忽略，再创建：

```powershell
git check-ignore .worktrees
git worktree add .worktrees/task-dialog-history-flicker -b feature/task-dialog-history-flicker
```

Expected: 新 worktree 基于包含规格和计划文档的提交，`git status --short` 为空。

- [ ] **Step 2: 在独立 worktree 中创建 Python 环境**

Run:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Expected: 依赖安装成功。

- [ ] **Step 3: 在独立 worktree 中运行基线测试**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py tests/test_history_workspace.py -q
```

Expected: 当前测试全部通过。

- [ ] **Step 4: 确认主窗口已有历史关闭后重载逻辑**

Run:

```powershell
rg -n "def open_history|self\.refresh\(\)" src/floating_todo/ui/main_window.py
```

Expected: `open_history()` 在 `dialog.exec()` 和 `_reactivate_window()` 后调用 `self.refresh()`。

## Task 1: 新建任务窗口自动聚焦名称输入框

**Files:**
- Modify: `tests/test_task_dialog.py`
- Modify: `src/floating_todo/ui/task_dialog.py:7`
- Modify: `src/floating_todo/ui/task_dialog.py:414-417`

- [ ] **Step 1: 写入首焦点失败测试**

在 `tests/test_task_dialog.py` 中增加：

```python
def test_dialog_focuses_title_input_when_shown(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.show()
    qapp.processEvents()
    QTest.qWait(0)

    assert dialog.title_input.hasFocus()

    dialog.close()


def test_edit_dialog_focuses_and_selects_existing_title(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog(None, make_task())
    dialog.show()
    qapp.processEvents()
    QTest.qWait(0)

    assert dialog.title_input.hasFocus()
    assert dialog.title_input.selectedText() == "旧任务"

    dialog.close()
```

- [ ] **Step 2: 运行测试，确认 RED**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py::test_dialog_focuses_title_input_when_shown tests/test_task_dialog.py::test_edit_dialog_focuses_and_selects_existing_title -q
```

Expected: FAIL，因为窗口显示后尚未显式聚焦名称输入框，编辑窗口也未选中现有名称。

- [ ] **Step 3: 在窗口显示后调度名称输入框聚焦**

在 `src/floating_todo/ui/task_dialog.py` 中将 QtCore 导入扩展为：

```python
from PySide6.QtCore import QDate, QDateTime, QEvent, QSize, QTimeZone, QTimer, Qt
```

将 `TaskDialog.showEvent()` 更新为：

```python
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_panel_width()
        QTimer.singleShot(0, self._focus_title_input)

    def _focus_title_input(self) -> None:
        if not self.isVisible():
            return
        self.title_input.setFocus(Qt.OtherFocusReason)
        if self.task is not None:
            self.title_input.selectAll()
```

- [ ] **Step 4: 运行首焦点测试，确认 GREEN**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py::test_dialog_focuses_title_input_when_shown tests/test_task_dialog.py::test_edit_dialog_focuses_and_selects_existing_title -q
```

Expected: `2 passed`。

- [ ] **Step 5: 运行任务弹窗回归测试**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交首焦点改动**

```powershell
git add -- src/floating_todo/ui/task_dialog.py tests/test_task_dialog.py
git commit -m "Improve task dialog initial title focus"
```

## Task 2: 让优先级预览卡可直接点击选择

**Files:**
- Modify: `tests/test_task_dialog.py`
- Modify: `src/floating_todo/ui/task_dialog.py:7`
- Modify: `src/floating_todo/ui/task_dialog.py:319-328`
- Modify: `src/floating_todo/ui/task_dialog.py:474-477`
- Modify: `src/floating_todo/ui/task_dialog.py:664-701`
- Modify: `src/floating_todo/ui/task_dialog.py:801-815`

- [ ] **Step 1: 写入优先级卡片交互失败测试**

在 `tests/test_task_dialog.py` 中增加：

```python
def test_priority_preview_cards_select_priority_and_follow_combo(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.show()
    qapp.processEvents()

    high = dialog.priority_preview_cards["P1"]
    medium = dialog.priority_preview_cards["P2"]
    low = dialog.priority_preview_cards["P3"]

    assert medium.property("selected") is True
    assert high.property("selected") is False
    assert low.property("selected") is False

    QTest.mouseClick(high, Qt.LeftButton)
    assert dialog.priority_combo.currentData() == "P1"
    assert high.property("selected") is True
    assert medium.property("selected") is False

    QTest.mouseClick(low, Qt.LeftButton)
    assert dialog.priority_combo.currentData() == "P3"
    assert low.property("selected") is True
    assert high.property("selected") is False

    dialog.priority_combo.setCurrentIndex(dialog.priority_combo.findData("P2"))
    assert medium.property("selected") is True
    assert low.property("selected") is False

    assert high.toolTip() == "选择高优先级"
    assert medium.accessibleName() == "选择中优先级"
    assert low.cursor().shape() == Qt.PointingHandCursor

    dialog.close()
```

- [ ] **Step 2: 运行测试，确认 RED**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py::test_priority_preview_cards_select_priority_and_follow_combo -q
```

Expected: FAIL，因为 `TaskDialog` 尚无 `priority_preview_cards`，现有预览卡只是 `QFrame`。

- [ ] **Step 3: 新增可点击预览卡类型**

在 `src/floating_todo/ui/task_dialog.py` 中将 QtCore 导入扩展为：

```python
from PySide6.QtCore import QDate, QDateTime, QEvent, QSize, QTimeZone, QTimer, Qt, Signal
```

在 `TaskDialog` 前增加：

```python
class PriorityPreviewCard(QFrame):
    clicked = Signal(str)

    def __init__(self, priority: str) -> None:
        super().__init__()
        self.priority = priority
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"选择{priority_text(priority)}优先级")
        self.setAccessibleName(f"选择{priority_text(priority)}优先级")

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.priority)
```

- [ ] **Step 4: 保存三张卡片并连接双向同步**

在 `_build_ui()` 的优先级区域替换三行 `_priority_preview(...)` 调用：

```python
        self.priority_preview_cards = {
            "P1": _priority_preview("高", "紧急且重要", "P1"),
            "P2": _priority_preview("中", "重要但不紧急", "P2"),
            "P3": _priority_preview("低", "可延后处理", "P3"),
        }
        for column, priority in enumerate(PRIORITY_ORDER):
            card = self.priority_preview_cards[priority]
            card.clicked.connect(self._set_priority_value)
            priority_grid.addWidget(card, 0, column)
```

在 `TaskDialog.__init__()` 的信号连接区增加：

```python
        self.priority_input.currentIndexChanged.connect(self._sync_priority_preview_selection)
        self._sync_priority_preview_selection()
```

在 `_set_priority_value()` 后增加：

```python
    def _sync_priority_preview_selection(self, *args) -> None:
        selected = self._selected_priority()
        for priority, card in self.priority_preview_cards.items():
            card.setProperty("selected", priority == selected)
            card.style().unpolish(card)
            card.style().polish(card)
```

- [ ] **Step 5: 让工厂函数返回可点击卡片**

将 `_priority_preview()` 的开头改为：

```python
def _priority_preview(title: str, subtitle: str, priority: str) -> PriorityPreviewCard:
    frame = PriorityPreviewCard(priority)
    frame.setObjectName(f"taskPriorityPreview{priority}")
```

其余布局保持不变，并让内部标签不拦截鼠标点击：

```python
    icon = QLabel("")
    icon.setObjectName("taskPriorityPreviewIcon")
    icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    title_label = QLabel(title)
    title_label.setObjectName("taskPriorityPreviewTitle")
    title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("taskPriorityPreviewSubtitle")
    subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
```

- [ ] **Step 6: 增加清晰选中态样式**

在 `_task_dialog_style()` 的优先级卡片样式后增加：

```css
QFrame#taskPriorityPreviewP1[selected="true"],
QFrame#taskPriorityPreviewP2[selected="true"],
QFrame#taskPriorityPreviewP3[selected="true"] {
  border: 2px solid rgba(125, 211, 252, 0.92);
}
```

并将 `QFrame#taskPriorityPreviewP2` 默认边框由：

```css
  border: 1px solid rgba(56, 189, 248, 0.55);
```

改为：

```css
  border: none;
```

这样默认高亮完全由 `selected` 属性驱动，而不是写死在中优先级样式中。

- [ ] **Step 7: 运行优先级卡片测试，确认 GREEN**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py::test_priority_preview_cards_select_priority_and_follow_combo -q
```

Expected: `1 passed`。

- [ ] **Step 8: 运行任务弹窗回归测试**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_task_dialog.py -q
```

Expected: 全部通过。

- [ ] **Step 9: 提交优先级快捷选择改动**

```powershell
git add -- src/floating_todo/ui/task_dialog.py tests/test_task_dialog.py
git commit -m "Make task priority preview cards selectable"
```

## Task 3: 为历史记录增加改名能力

**Files:**
- Modify: `tests/test_history_workspace.py`
- Modify: `src/floating_todo/ui/history_window.py:1641-1647`
- Modify: `src/floating_todo/ui/history_window.py:1813-1837`

- [ ] **Step 1: 更新历史菜单契约并写入改名失败测试**

在 `test_history_workspace_pagination_record_menu_and_chart_render()` 中将菜单断言更新为：

```python
    assert [action.text() for action in menu.actions()] == [
        "查看/编辑备注",
        "修改任务名称",
        "删除历史记录",
        "复制记录摘要",
        "导出当前记录",
    ]
```

在 `tests/test_history_workspace.py` 中增加：

```python
def test_rename_history_task_saves_trimmed_title_and_refreshes_graph(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.history_window as history_window

    task = make_task("旧名称", "done-rename", status="done", tag="项目")
    store = MemoryStore([task])
    window = history_window.HistoryWindow([task], store)
    window._set_history_section("analysis")
    monkeypatch.setattr(history_window.QInputDialog, "getText", lambda *args, **kwargs: ("  新名称  ", True))

    window.rename_history_task("done-rename")

    assert store.saved_tasks == [replace(task, title="新名称")]
    assert "新名称" in window._analysis_graph_html
    assert "旧名称" not in window._analysis_graph_html

    window.close()
```

在同一文件中增加边界测试：

```python
@pytest.mark.parametrize(
    ("returned_title", "accepted"),
    [
        ("旧名称", True),
        ("   ", True),
        ("新名称", False),
    ],
)
def test_rename_history_task_ignores_noop_blank_cancel_and_missing_task(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    returned_title: str,
    accepted: bool,
) -> None:
    import floating_todo.ui.history_window as history_window

    task = make_task("旧名称", "done-rename", status="done")
    store = MemoryStore([task])
    window = history_window.HistoryWindow([task], store)
    monkeypatch.setattr(history_window.QInputDialog, "getText", lambda *args, **kwargs: (returned_title, accepted))

    window.rename_history_task("done-rename")
    window.rename_history_task("missing")

    assert store.saved_tasks is None

    window.close()
```

- [ ] **Step 2: 运行改名测试，确认 RED**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py::test_rename_history_task_saves_trimmed_title_and_refreshes_graph tests/test_history_workspace.py::test_rename_history_task_ignores_noop_blank_cancel_and_missing_task -q
```

Expected: FAIL，因为 `HistoryWindow` 尚无 `rename_history_task()`。

- [ ] **Step 3: 在历史菜单中加入改名入口**

在 `_build_record_card()` 的菜单构建处改为：

```python
        menu = QMenu(menu_button)
        menu.addAction("查看/编辑备注", lambda: self.open_note_editor(task))
        menu.addAction("修改任务名称", lambda: self.rename_history_task(task.id))
        menu.addAction("删除历史记录", lambda: self.delete_history_task(task.id))
        menu.addAction("复制记录摘要", lambda: self._copy_record_summary(task))
        menu.addAction("导出当前记录", lambda: self._export_single_record(task))
```

此时 `delete_history_task()` 尚未实现，测试只读取菜单动作，不触发删除动作。

- [ ] **Step 4: 实现历史改名**

在 `edit_history_graph_tag()` 前增加：

```python
    def rename_history_task(self, task_id: str) -> None:
        task = self._task_by_id(task_id)
        if task is None or task.status != "done":
            return
        title, accepted = QInputDialog.getText(self, "修改任务名称", "新的任务名称：", text=task.title)
        normalized = title.strip()
        if not accepted or not normalized or normalized == task.title:
            return
        self.tasks = [replace(item, title=normalized) if item.id == task_id else item for item in self.tasks]
        self.store.save_tasks(self.tasks)
        self._render()
```

- [ ] **Step 5: 运行改名与菜单测试，确认 GREEN**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py::test_rename_history_task_saves_trimmed_title_and_refreshes_graph tests/test_history_workspace.py::test_rename_history_task_ignores_noop_blank_cancel_and_missing_task tests/test_history_workspace.py::test_history_workspace_pagination_record_menu_and_chart_render -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交历史改名改动**

```powershell
git add -- src/floating_todo/ui/history_window.py tests/test_history_workspace.py
git commit -m "Add history task rename action"
```

## Task 4: 为历史记录增加删除能力

**Files:**
- Modify: `tests/test_history_workspace.py`
- Modify: `src/floating_todo/ui/history_window.py:1822-1837`

- [ ] **Step 1: 写入删除确认和刷新失败测试**

在 `tests/test_history_workspace.py` 中增加：

```python
def test_delete_history_task_removes_record_and_returns_to_valid_page(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    tasks = [
        make_task(f"记录 {index}", f"done-{index}", status="done", tag="唯一标签" if index == 8 else "项目")
        for index in range(9)
    ]
    store = MemoryStore(tasks)
    window = HistoryWindow(tasks, store)
    window.page_size_combo.setCurrentIndex(window.page_size_combo.findData(8))
    window._selected_page_index = 1
    window._render()
    monkeypatch.setattr(window, "confirm_delete_history_task", lambda task: True)

    window.delete_history_task("done-8")

    assert store.saved_tasks == tasks[:8]
    assert window._selected_page_index == 0
    assert window.tag_filter.findData("唯一标签") == -1
    assert window.tag_filter.currentData() == "all"
    assert window.page_summary_label.text().startswith("1-8 / 8 条")

    window.close()
```

增加标签筛选回退测试：

```python
def test_delete_history_task_returns_removed_selected_tag_to_all(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    tasks = [
        make_task("保留记录", "done-keep", status="done", tag="项目"),
        make_task("删除记录", "done-remove", status="done", tag="唯一标签"),
    ]
    store = MemoryStore(tasks)
    window = HistoryWindow(tasks, store)
    window.tag_filter.setCurrentIndex(window.tag_filter.findData("唯一标签"))
    monkeypatch.setattr(window, "confirm_delete_history_task", lambda task: True)

    window.delete_history_task("done-remove")

    assert store.saved_tasks == tasks[:1]
    assert window.tag_filter.findData("唯一标签") == -1
    assert window.tag_filter.currentData() == "all"

    window.close()
```

增加取消和不存在任务测试：

```python
def test_delete_history_task_ignores_declined_and_missing_task(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    task = make_task("保留记录", "done-keep", status="done")
    store = MemoryStore([task])
    window = HistoryWindow([task], store)
    monkeypatch.setattr(window, "confirm_delete_history_task", lambda selected: False)

    window.delete_history_task("missing")
    window.delete_history_task("done-keep")

    assert store.saved_tasks is None
    assert window.tasks == [task]

    window.close()
```

增加非历史任务保护测试：

```python
def test_delete_history_task_ignores_non_completed_task(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    task = make_task("进行中任务", "active-keep", status="active")
    store = MemoryStore([task])
    window = HistoryWindow([task], store)
    monkeypatch.setattr(window, "confirm_delete_history_task", lambda selected: True)

    window.delete_history_task("active-keep")

    assert store.saved_tasks is None
    assert window.tasks == [task]

    window.close()
```

- [ ] **Step 2: 运行删除测试，确认 RED**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py::test_delete_history_task_removes_record_and_returns_to_valid_page tests/test_history_workspace.py::test_delete_history_task_returns_removed_selected_tag_to_all tests/test_history_workspace.py::test_delete_history_task_ignores_declined_and_missing_task tests/test_history_workspace.py::test_delete_history_task_ignores_non_completed_task -q
```

Expected: FAIL，因为 `HistoryWindow` 尚无 `delete_history_task()` 和 `confirm_delete_history_task()`。

- [ ] **Step 3: 实现历史删除和确认弹窗**

在 `rename_history_task()` 后增加：

```python
    def delete_history_task(self, task_id: str) -> None:
        task = self._task_by_id(task_id)
        if task is None or task.status != "done" or not self.confirm_delete_history_task(task):
            return
        selected_tag = str(self.tag_filter.currentData() or "all")
        self.tasks = [item for item in self.tasks if item.id != task_id]
        self.store.save_tasks(self.tasks)
        self._refresh_tag_filter_options(selected=selected_tag)
        self._render()

    def confirm_delete_history_task(self, task: Task) -> bool:
        result = QMessageBox.question(
            self,
            "删除历史记录",
            f"确认永久删除历史记录“{task.title}”吗？\n删除后无法恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return result == QMessageBox.Yes
```

现有 `_refresh_tag_filter_options()` 会在原标签不存在时自动回退到索引 `0`，即“全部标签”。现有 `_sync_pagination()` 会在当前页超出范围时自动回退到最后一个有效页。

- [ ] **Step 4: 运行删除测试，确认 GREEN**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py::test_delete_history_task_removes_record_and_returns_to_valid_page tests/test_history_workspace.py::test_delete_history_task_returns_removed_selected_tag_to_all tests/test_history_workspace.py::test_delete_history_task_ignores_declined_and_missing_task tests/test_history_workspace.py::test_delete_history_task_ignores_non_completed_task -q
```

Expected: `4 passed`。

- [ ] **Step 5: 运行历史窗口回归测试**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py -q
```

Expected: 全部通过。

- [ ] **Step 6: 提交历史删除改动**

```powershell
git add -- src/floating_todo/ui/history_window.py tests/test_history_workspace.py
git commit -m "Add history record deletion"
```

## Task 5: 修复 3D 洞察 HUD 面板频闪

**Files:**
- Modify: `tests/test_history_workspace.py:55-116`
- Modify: `src/floating_todo/ui/history_graph.py:168-173`
- Modify: `src/floating_todo/ui/history_graph.py:236`

- [ ] **Step 1: 写入频闪策略失败测试**

在 `test_history_graph_payload_extracts_keyword_relationships()` 的 HTML 断言中增加：

```python
    assert "if(!drag) rotY+=.0012" in html
    assert "requestAnimationFrame(animate)" in html
    assert "backdrop-filter" not in html
    assert "performance.now()*.002" not in html
    assert "pulse=1+Math.sin" not in html
    assert "ctx.arc(p.x,p.y,r,0,Math.PI*2)" in html
```

- [ ] **Step 2: 运行 HTML 测试，确认 RED**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py::test_history_graph_payload_extracts_keyword_relationships -q
```

Expected: FAIL，因为当前 HTML 仍包含 `backdrop-filter:blur(16px)`、`performance.now()*.002` 和 `pulse=1+Math.sin(...)`。

- [ ] **Step 3: 移除 HUD 毛玻璃实时模糊**

在 `src/floating_todo/ui/history_graph.py` 的 `.glass` 样式中删除：

```css
      backdrop-filter:blur(16px);
```

保留既有渐变背景、边框、阴影和圆角。

- [ ] **Step 4: 移除节点呼吸脉冲，保留自动旋转**

在 `draw()` 中删除：

```javascript
const t=performance.now()*.002;
```

将节点循环中的：

```javascript
pulse=1+Math.sin(t+n.x*.01)*.055;
```

删除，并将：

```javascript
ctx.arc(p.x,p.y,r*pulse,0,Math.PI*2);
```

替换为：

```javascript
ctx.arc(p.x,p.y,r,0,Math.PI*2);
```

保留：

```javascript
function animate() { if(simEnergy>0.008||drag) { step(); step(); } if(!drag) rotY+=.0012; draw(); requestAnimationFrame(animate); }
```

- [ ] **Step 5: 运行图谱 HTML 测试，确认 GREEN**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py::test_history_graph_payload_extracts_keyword_relationships -q
```

Expected: `1 passed`。

- [ ] **Step 6: 运行历史图谱和历史窗口回归测试**

Run:

```powershell
.venv\Scripts\python -m pytest tests/test_history_workspace.py -q
```

Expected: 全部通过。

- [ ] **Step 7: 提交频闪修复**

```powershell
git add -- src/floating_todo/ui/history_graph.py tests/test_history_workspace.py
git commit -m "Reduce history insight WebEngine compositing"
```

## Task 6: 完整验证、便携构建和 ZIP 解压烟雾测试

**Files:**
- Verify: `src/`
- Verify: `tests/`
- Build: `scripts/build.ps1`
- Generate ignored artifact: `dist/Todo list/`
- Generate ignored artifact: `release/Todo-list-V1.0-portable-windows.zip`

- [ ] **Step 1: 运行完整自动化测试**

Run:

```powershell
.venv\Scripts\python -m pytest -q
```

Expected: 全部测试通过，允许仓库已有的显式 skip。

- [ ] **Step 2: 运行源码编译和差异格式检查**

Run:

```powershell
.venv\Scripts\python -m compileall -q src tests
git diff --check
```

Expected: 两条命令退出码均为 `0`。

- [ ] **Step 3: 重新构建便携目录**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

Expected:

```text
Build complete: dist/Todo list/Todo list.exe
```

- [ ] **Step 4: 从构建目录做可见窗口烟雾测试**

Run:

```powershell
$exe = (Resolve-Path 'dist\Todo list\Todo list.exe').Path
$started = Get-Date
$process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -PassThru
try {
    $deadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 150
        $process.Refresh()
        if ($process.HasExited) { throw "Portable app exited early with code $($process.ExitCode)" }
    } while ($process.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline)
    if ($process.MainWindowHandle -eq 0) { throw "Portable app window did not become visible" }
    "dist_smoke_visible=True"
    "dist_smoke_elapsed_ms=$([math]::Round(((Get-Date) - $started).TotalMilliseconds))"
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
}
```

Expected: `dist_smoke_visible=True`。

- [ ] **Step 5: 发布本地便携目录并压缩 ZIP**

Run:

```powershell
$root = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd('\','/')
$releaseRoot = [System.IO.Path]::GetFullPath((Join-Path $root 'release'))
$archive = [System.IO.Path]::GetFullPath((Join-Path $root 'release\Todo-list-V1.0-portable-windows.zip'))
$source = [System.IO.Path]::GetFullPath((Join-Path $root 'dist\Todo list'))
$portable = [System.IO.Path]::GetFullPath((Join-Path $releaseRoot 'V1.0-portable'))
if (-not $releaseRoot.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe release root: $releaseRoot" }
if (-not $archive.StartsWith($releaseRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe archive path: $archive" }
if (-not $source.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe source path: $source" }
if (-not $portable.StartsWith($releaseRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe portable path: $portable" }
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
if (Test-Path -LiteralPath $portable) { Remove-Item -LiteralPath $portable -Recurse -Force }
New-Item -ItemType Directory -Force -Path $portable | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $portable -Recurse -Force
Compress-Archive -LiteralPath $portable -DestinationPath $archive -CompressionLevel Optimal -Force
Get-FileHash -Algorithm SHA256 -LiteralPath $archive
```

Expected: 生成本地便携目录、ZIP 和 SHA256。ZIP 顶层目录为 `V1.0-portable`，其中包含 `Todo list.exe`、`_internal` 和 `data`。

- [ ] **Step 6: 从全新目录解压 ZIP 并启动**

Run:

```powershell
$root = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd('\','/')
$archive = [System.IO.Path]::GetFullPath((Join-Path $root 'release\Todo-list-V1.0-portable-windows.zip'))
$target = [System.IO.Path]::GetFullPath((Join-Path $root 'build\zip-smoke'))
if (-not $target.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe smoke target: $target" }
if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
New-Item -ItemType Directory -Force -Path $target | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $target -Force
$exe = Join-Path $target 'V1.0-portable\Todo list.exe'
$webEngine = Join-Path $target 'V1.0-portable\_internal\PySide6\QtWebEngineProcess.exe'
if (-not (Test-Path -LiteralPath $webEngine -PathType Leaf)) { throw "Missing QtWebEngineProcess.exe" }
$process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -PassThru
try {
    $deadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 150
        $process.Refresh()
        if ($process.HasExited) { throw "Extracted app exited early with code $($process.ExitCode)" }
    } while ($process.MainWindowHandle -eq 0 -and (Get-Date) -lt $deadline)
    if ($process.MainWindowHandle -eq 0) { throw "Extracted app window did not become visible" }
    "zip_smoke_visible=True"
    "zip_smoke_webengine_process=True"
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
}
Start-Sleep -Milliseconds 500
if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
```

Expected:

```text
zip_smoke_visible=True
zip_smoke_webengine_process=True
```

- [ ] **Step 7: 人工验证四条用户流程**

在解压后的便携目录中手工检查：

1. 打开新增任务窗口后，不点击鼠标即可直接输入名称。
2. 点击高、中、低优先级卡片时，下拉框和卡片高亮同步变化。
3. 历史记录更多菜单可改名和删除；取消删除不会丢失数据。
4. 打开洞察页观察至少 20 秒：图谱缓慢旋转仍存在，图例、风格洞察和节点详情面板不再频闪。

- [ ] **Step 8: 检查最终状态**

Run:

```powershell
git status --short
git log --oneline --decorate --max-count=8
```

Expected: 仅存在本轮提交和明确保留的 ignored 构建产物；不得混入用户原有修改。

## Task 7: 请求代码审查并准备发布

**Files:**
- Review: `src/floating_todo/ui/task_dialog.py`
- Review: `src/floating_todo/ui/history_window.py`
- Review: `src/floating_todo/ui/history_graph.py`
- Review: `tests/test_task_dialog.py`
- Review: `tests/test_history_workspace.py`

- [ ] **Step 1: 调用请求代码审查流程**

调用 `requesting-code-review` skill，重点检查：

1. 历史删除是否可能误删进行中任务。
2. 标签筛选和分页是否在删除后保持有效状态。
3. 优先级预览卡是否保持下拉框兼容和无障碍属性。
4. 频闪修复是否保留自动旋转、拖动、缩放、选中节点光晕和 WebChannel 操作。
5. 是否触碰了主工作区中用户原有的未提交修改。

- [ ] **Step 2: 仅在用户确认后更新 GitHub Release**

本轮功能验证完成后，先报告本地 ZIP 路径、大小和 SHA256。只有用户明确要求发布时，才替换 GitHub Release 资产并更新 README 或 Release 简介。
