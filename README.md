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

## 运行环境

- Windows 10/11
- Python 3.10 或更高版本
- PowerShell 或 cmd

不强制使用 conda。普通 Python 虚拟环境 `.venv` 就可以运行和打包。

## 从源码运行

从 GitHub 下载或克隆项目后，在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m floating_todo
```

如果 PowerShell 提示不能激活虚拟环境，可以先执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

如果你正在使用 cmd，也可以直接用虚拟环境里的 Python：

```cmd
.\.venv\Scripts\python -m floating_todo
```

## 打包 exe

项目已经提供打包脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

打包完成后，程序会生成在：

```text
dist\Todo list\Todo list.exe
```

可以双击运行：

```text
dist\Todo list\Todo list.exe
```

注意：这是 PyInstaller 的 `onedir` 打包方式，`Todo list.exe` 依赖同目录下的动态库、Qt 插件和资源文件。分享给别人时不要只发送单独的 exe，应该发送整个 `dist\Todo list` 文件夹，或者发送压缩包。

## V1.0 发布包

本地发布文件会放在：

```text
release\V1.0\
```

推荐分享这个压缩包：

```text
release\V1.0\Todo-list-V1.0-windows.zip
```

使用者只需要解压 zip，然后双击：

```text
Todo list\Todo list.exe
```

## 测试

```powershell
python -m pytest -q
```

当前测试覆盖任务排序、提醒、设置、历史统计、导出、托盘、主窗口交互和打包脚本等核心逻辑。

## 数据保存

打包版本会在程序目录下创建：

```text
dist\Todo list\data\
```

任务、设置、历史记录等数据会保存在这里。移动整个 `Todo list` 文件夹时，数据也会一起移动。

## 常见问题

### 运行 `.\build.ps1` 提示不是命令

如果你在 cmd 里运行，需要用：

```cmd
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

如果你已经在 `scripts` 目录里，则运行：

```cmd
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

### PySide6 下载很慢或文件很大

这是正常的。PySide6 包含 Qt 运行库，首次安装会下载比较大的依赖。下载完成后再次打包会快很多。

### 能不能只发 exe

不建议。当前是文件夹式打包，单独的 exe 离开同目录依赖后通常无法运行。请发送 `release\V1.0\Todo-list-V1.0-windows.zip`。

### conda 环境能不能用

可以，但不是必须。使用 conda 时建议单独创建 Python 3.10 环境：

```cmd
conda create -n todo-list python=3.10 -y
conda activate todo-list
pip install -r requirements.txt
pip install -e .
python -m floating_todo
```

## 项目结构

```text
src\floating_todo\        程序源码
src\floating_todo\ui\     PySide6 界面
src\floating_todo\assets\ 图标、字体、背景资源
tests\                    自动化测试
scripts\build.ps1         Windows 打包脚本
dist\                     本地打包输出，不提交到 GitHub
release\                  本地发布压缩包，不提交到 GitHub
```
