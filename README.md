# Todo list

`Todo list` 是一个 Windows 桌面悬浮待办与时间管理工具，使用 Python + PySide6 开发。它适合放在桌面上持续查看当前任务、工作计时、截止倒计时、提醒状态和历史完成情况。

## 下载

在 [Releases](https://github.com/chenboyu666/Todo_list/releases/tag/v1.0) 页面下载 `Todo-list-V1.0-windows.exe`，双击运行即可。

首次启动后，程序会在运行目录旁自动创建 `data` 文件夹，用于保存任务、设置、历史记录和自定义资源。

## 功能亮点

- 桌面悬浮窗口：无边框科技风界面，支持拖动、缩放、置顶、托盘恢复和鼠标穿透。
- 实时信息面板：顶部显示实时数字时钟，并统计今日完成、进行中、临近截止和超时任务。
- 当前任务聚焦：突出展示任务名称、优先级、截止时间、倒计时、工作计时和备注。
- 工作计时：任务可暂停与继续，暂停后保留已工作时长，继续时可重新设为当前任务。
- 截止提醒：临近截止和超时会弹出提醒小窗，提醒间隔可在设置中调整。
- 优先级区分：任务支持高、中、低优先级，并用图标、色彩和卡片状态区分。
- 任务管理：支持新增、编辑、删除、完成、置顶当前任务，以及多列任务卡片浏览。
- 日期选择：日期弹窗支持直接修改年份，日历、月份和选中状态使用统一深色视觉。
- 历史记录：按日期区间、优先级、状态和任务名称筛选完成记录，可编辑备注和完成体会。
- 历史统计：提供优先级结构、完成趋势、准时/超时分布等图表辅助复盘。
- CSV 导出：可选择日期范围导出历史任务数据。
- 个性设置：支持透明度、界面缩放、内置/自定义背景、随机背景文件夹、程序图标、开机启动和托盘行为。

## 使用方式

1. 下载 `Todo-list-V1.0-windows.exe`。
2. 双击启动程序。
3. 点击主界面的新增按钮创建任务。
4. 在任务卡片中可将任务设为当前任务，或展开后编辑、暂停、继续、完成和删除。
5. 通过历史窗口查看完成记录、统计图表，并按日期范围导出 CSV。

## 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m floating_todo
```

## 测试

```powershell
python -m pytest -q
```

测试覆盖任务排序、工作计时、提醒、设置、历史统计、导出、托盘、主窗口交互、日期选择和打包脚本等核心逻辑。

## 构建

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建产物：

```text
dist\Todo list.exe
```

## 运行时数据

程序会在运行目录下自动创建 `data` 文件夹：

```text
data\
  tasks.json
  settings.json
  resources\
```

移动程序时，建议将 exe 与同级 `data` 文件夹一起移动，以保留任务、设置、历史记录、自定义背景和自定义图标。

## 项目结构

```text
src\floating_todo\        程序源码
src\floating_todo\ui\     PySide6 界面
src\floating_todo\assets\ 图标、字体、背景资源
tests\                    自动化测试
scripts\build.ps1         Windows 打包脚本
pyproject.toml            Python 项目配置
requirements.txt          开发和打包依赖
```
