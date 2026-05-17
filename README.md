# Todo list

`Todo list` 是一个 Windows 桌面待办浮窗程序，使用 Python + PySide6 开发。它适合放在桌面上持续显示当前任务、截止倒计时、工作进度和历史完成情况。

## 主要功能

- 实时时钟：窗口顶部显示当前时间。
- 桌面浮窗：无边框窗口，可拖动位置、调整大小，并支持置顶显示。
- 多任务管理：支持新增、编辑、删除、完成、暂停、继续任务。
- 当前任务置顶：可以把任意任务设为当前进行中任务，当前任务区域会高亮展示。
- 优先级区分：任务支持 P1、P2、P3 等优先级，优先级颜色固定区分。
- 工作量记录：任务可记录预估工作量，辅助排序和截止时间设置。
- 截止倒计时：显示截止日期、截止时间和剩余时间；时间越紧急，倒计时颜色越偏暖。
- 进度管理：支持拖动进度条，也支持手动输入百分比。
- 任务备注：任务可以填写备注，当前任务和展开后的任务卡片会显示备注。
- 到期提醒：临近截止和超时会出现提醒，可在设置里调整提醒提前量和重复间隔。
- 完成鼓励：点击完成后会弹出确认，并显示鼓励提示。
- 历史任务：可查看已完成任务、编辑备注和完成体会。
- 历史统计：历史窗口包含优先级完成情况、准时/超时情况、完成趋势等统计图。
- 历史筛选：支持按日期、等级分页查看历史任务，也支持按任务名称搜索。
- CSV 导出：可选择日期范围导出历史任务数据。
- 个性设置：支持透明度、背景图片或动图、程序图标、置顶、开机启动、最小化到托盘等设置。
- 鼠标穿透：置顶时可开启鼠标穿透，让点击落到后方窗口；可通过托盘菜单恢复。

## 开发环境

- Windows 10/11
- Python 3.10 或更高版本
- PowerShell 或 cmd

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

当前测试覆盖任务排序、提醒、设置、历史统计、导出、托盘、主窗口交互和打包脚本等核心逻辑。

## 构建

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建产物：

```text
dist\Todo list.exe
```

## 运行时数据

程序会在运行目录下自动创建 `data` 文件夹，用于保存任务、设置和历史记录。

```text
data\
  tasks.json
  settings.json
```

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
