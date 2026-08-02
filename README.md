# 📌 Highlights Everywhere | 高亮无处不在

> **Highlight text, take notes, find them instantly via Spotlight.**
> **选中即高亮，随手记笔记，Spotlight 一键搜到。**

<p align="center">
  <img src="images/demo-web-highlight.png" alt="Highlight text on any webpage with colored toolbar" width="750">
</p>

<p align="center">
  <em>选中文字 → 工具栏自动弹出 → 选颜色 / 直接写备注 → 自动高亮保存</em>
</p>

<p align="center">
  <img src="images/demo-notes-folder.png" alt="Highlights aggregated in Apple Notes" width="750">
</p>

<p align="center">
  <em>高亮自动同步到 Apple 备忘录「Highlights」文件夹——同一个链接的所有高亮聚合在一条备忘录里，每条带 🔗 原文位置链接，手机直接阅读</em>
</p>

<p align="center">
  <img src="images/demo-spotlight-notes.png" alt="Spotlight finds your highlights in Notes" width="750">
</p>

<p align="center">
  <em>Cmd+Space 直接搜到高亮内容（备忘录 + 本地文件都可搜）</em>
</p>

---

## 中文介绍

### 这是什么？

一个让你在 **任何地方记笔记、做高亮** 的工具。选中文字 → 选颜色 / 写备注 → 存下来。**高亮自动写入 Apple 备忘录（Notes）**——手机打开备忘录就能读，Mac 上 Cmd+Space 也能搜到。

> 💡 **数据存在 Apple 备忘录里**：每条高亮同步到备忘录「Highlights」文件夹，同一个链接（URL）的高亮聚合在同一条备忘录中，可加多条备注，每条带「🔗 原文位置」链接，点击跳回原文片段。本地同时保留一份 Markdown 聚合文件（供浏览器恢复高亮）。

### 核心功能

| 功能 | 说明 |
|------|------|
| 🎨 **7 种颜色高亮** | 🟡黄 🟢绿 🔵蓝 🔴红 🟣紫 🟠橙 🩷粉 |
| 💬 **备注批注** | 每条高亮都可以写备注；同原文重复高亮时新备注**覆盖**旧备注 |
| 📱 **备忘录同步** | 高亮自动写入 Apple 备忘录「Highlights」文件夹，**同一链接聚合在同一条备忘录**，手机直接读 |
| 🔗 **原文跳转** | 每条备忘录高亮带「🔗 原文位置」链接，点击跳回原文片段（`#hl=id`） |
| ✏️ **可编辑** | 点已高亮文字 → 改颜色 / 改备注 / 删除，备忘录同步更新 |
| 🔍 **Spotlight 搜索** | Cmd+Space 直接搜（备忘录 + 本地文件都可搜） |
| 🌐 **Web 展示** | 打开 `localhost:8899`，浏览器看全部高亮 |
| 🖥️ **CLI 工具** | `hl` 命令行保存、搜索、统计 |
| 🚀 **开机自启** | 服务器后台自动运行，无需手动启动 |

### 快速开始

> 💡 **数据存在 Apple 备忘录里**：高亮保存后自动写入备忘录「Highlights」文件夹（同一链接聚合一条），手机备忘录直接阅读。本地 `~/Highlights/` 保留一份 Markdown 聚合文件（浏览器恢复高亮用）。

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/highlights-everywhere.git
cd highlights-everywhere

# 2. 一键安装
chmod +x install.sh
./install.sh

# 3. 打开任意网页，选中文字试试
```

或者手动安装：

```bash
# 复制 CLI 工具
cp hl ~/scripts/

# 启动服务器（后台永久运行）
cp com.highlights.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.highlights.server.plist

# 安装 Tampermonkey 脚本（浏览器自动高亮）
# 打开 http://localhost:8899/highlight.user.js
# Tampermonkey 会自动提示安装
```

### 使用流程

```
1. 打开任意网页
2. 选中一段文字 → 🟡🟢🔵🔴🟣🟠🩷 工具栏出现
3. 点一个颜色 → 文字立刻高亮
4. 写备注 → ✓ 保存
5. 点已高亮的文字 → 可编辑 / 改颜色 / 删除
6. 刷新页面 → 高亮自动恢复
7. Cmd+Space 搜内容 / localhost:8899 网页看全部
```

### CLI 命令

```bash
hl "要保存的文字"              # 保存高亮
hl -c green -m "备注" "文字"   # 绿色 + 备注
hl -t "标签1,标签2" "文字"     # 带标签
hl search 关键词               # 搜索
hl list                       # 最近 10 条
hl stats                      # 统计
hl open                       # 打开文件夹
hlweb                         # 启动服务器 + 打开网页
```

### 技术原理

```
用户选中文字 → Tampermonkey 脚本
  → fetch 发送到本地服务器（localhost:8899）
  → 服务器写入 Apple 备忘录（按链接聚合到同一条 note）+ 本地聚合文件
  → 备忘录 iCloud 同步到手机，直接阅读
  → macOS Spotlight 索引本地文件，Cmd+Space 可搜
```

- **存储**: Apple 备忘录（用户可见的主存储）+ 本地 Markdown 聚合文件（浏览器恢复高亮用）
- **按来源聚合**: 同一个 URL 的所有高亮聚合在一条备忘录 note 里（`📌 <域名>-<路径>`），本地对应 `~/Highlights/sources/<域名>-<路径>.md`
- **去重**: 同一链接同一原文只存一条，重复高亮时新备注覆盖旧备注
- **原文跳转**: 备忘录每条高亮带 `🔗 原文位置` 链接（`原文URL#hl=<id>`），浏览器打开后自动滚动到该高亮
- **搜索**: macOS `mdfind`（Spotlight），备忘录内容也在系统搜索范围内
- **数据安全**: Apple 备忘录（iCloud 加密同步）+ 本地文件，不上传任何第三方云端

---

## English Introduction

### What is this?

A universal highlighting & note-taking tool for macOS. **Select text in any app → pick a color → add a note → find it later via Spotlight.**

### Features

| Feature | Description |
|---------|-------------|
| 🎨 **7 Colors** | Yellow, Green, Blue, Red, Purple, Orange, Pink |
| 💬 **Notes & Annotations** | Attach comments to every highlight; re-highlighting the same text **overwrites** the old note |
| 📱 **Apple Notes sync** | Every highlight is written to the **Highlights** folder in Apple Notes — **all highlights from the same URL aggregate into one note**, readable on your iPhone |
| 🔗 **Jump to source** | Each note entry carries a `🔗 原文位置` link that opens the original page and scrolls to that exact highlight (`#hl=id`) |
| ✏️ **Editable** | Click any highlight → change color / edit note / delete; Notes stays in sync |
| 🔍 **Spotlight Search** | Cmd+Space finds your highlights (Notes + local files) |
| 🌐 **Web UI** | Open `http://localhost:8899` to browse all highlights |
| 🖥️ **CLI Tool** | `hl` command for save, search, stats |
| 🚀 **Auto-start** | Runs as a background service, no manual startup needed |

### Quick Start

> 💡 **Data lives in Apple Notes**: highlights are written to the **Highlights** folder (aggregated per URL), readable on your iPhone. A local Markdown copy in `~/Highlights/` powers browser restore.

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/highlights-everywhere.git
cd highlights-everywhere

# 2. One-click install
chmod +x install.sh
./install.sh

# 3. Open any webpage and select text
```

Or manually:

```bash
# Copy CLI
cp hl ~/scripts/

# Install background service
cp com.highlights.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.highlights.server.plist

# Install browser script via Tampermonkey
# Open http://localhost:8899/highlight.user.js
```

### Workflow

```
1. Open any webpage
2. Select text → 🟡🟢🔵🔴🟣🟠🩷 toolbar appears
3. Click a color → text is highlighted immediately
4. Add a note → ✓ save
5. Click any highlight → edit / change color / delete
6. Refresh page → highlights restore automatically
7. Cmd+Space to search / localhost:8899 for web UI
```

### CLI Usage

```bash
hl "text to save"                  # Save a highlight
hl -c green -m "note" "text"       # Green + note
hl -t "tag1,tag2" "text"           # With tags
hl search keyword                  # Search
hl list                            # Recent 10
hl stats                           # Statistics
hl open                            # Open highlights folder
hlweb                              # Start server + open web UI
```

### How It Works

```
User selects text → Tampermonkey script
  → fetch to local server (localhost:8899)
  → server writes to Apple Notes (aggregated per URL) + local Markdown file
  → Notes syncs to iPhone via iCloud
  → macOS Spotlight indexes local files for Cmd+Space search
```

- **Storage**: Apple Notes (user-facing) + local per-URL Markdown files (browser restore)
- **Aggregation**: all highlights from the same URL live in one Notes entry (`📌 <domain>-<path>`); local mirror at `~/Highlights/sources/<domain>-<path>.md`
- **Dedup**: same URL + same text = one entry; a new note overwrites the old note
- **Jump to source**: each entry links back to the exact highlight (`原文URL#hl=<id>`)
- **Search**: macOS `mdfind` (Spotlight)
- **Privacy**: Apple Notes (iCloud) + local files, no third-party cloud

---

## Project Structure

```
highlights-everywhere/
├── README.md                  # This file (中英文)
├── install.sh                 # One-click installer
├── hl                         # CLI tool (Python)
├── hl-server.py               # Local API + Web UI server
├── highlight.user.js          # Tampermonkey / bookmarklet script
├── com.highlights.server.plist  # macOS launchd auto-start config
└── hl-ext/                    # Chrome extension (reference)
    ├── manifest.json
    ├── content.js
    ├── background.js
    └── popup.html
```

## Requirements

- macOS (tested on macOS 26.1+, should work on 12.0+)
- Python 3 (built-in on macOS)
- Google Chrome / Safari with Tampermonkey (optional, for browser highlighting)

## License

MIT
