# DeepSeek Monitor Windows 插件汇总

> 整理时间：2026-06-12
> 来源：GitHub 搜索结果

---

## 概述

DeepSeek Monitor Windows 是一系列用于监控 DeepSeek API 账户余额、用量统计和费用趋势的 Windows 桌面工具。以下按功能完整度和 Stars 排序整理。

---

## 1. MiaTxxx/Deepseek-（功能最全，推荐）

| 属性 | 值 |
|------|-----|
| GitHub | https://github.com/MiaTxxx/Deepseek- |
| Stars | 较高 |
| 技术栈 | Electron 33 + Vite 5 + React 18 + TypeScript 5 + TailwindCSS + Recharts |
| 平台 | Windows / macOS / Linux |

### 功能亮点

- **💰 API 余额**：通过官方 `/user/balance` 接口实时查询
- **📊 用量统计**：深度分析本月请求数、Token 输入/输出细分、模型分布及消耗金额
- **📈 模型调度曲线**：提供带有日粒度数据的 7 日 Token 消耗趋势图
- **🪟 常驻悬浮窗**：支持 `alwaysOnTop` 与拖拽，以极高的信息密度常驻桌面角落
- **🖱️ 系统托盘**：提供便捷的系统托盘图标，一键隐藏/显示主监控面板
- **🤖 智能接口学习**：当官方平台内部接口变动时，通过「诊断」功能可一键重新抓取绑定
- **🔒 本地加密存储**：API Key 与登录 Cookie 仅经过加密存在本机，绝不上传任何第三方

### 使用步骤

1. **配置密钥**：填入 DeepSeek API Key，点击「测试连接」
2. **账号授权**：点击「登录 DeepSeek」，在弹出的独立安全窗口中完成账号登录
3. **接口绑定**：点击「诊断接口」，在新弹出的浏览器窗口里点击进入「用量统计」页 → 等待数据加载完毕 → 关闭窗口
4. **完成**：自动绑定成功，返回主面板即可查看所有实时监测数据

### 本地构建

```bash
git clone https://github.com/MiaTxxx/deepseek-monitor.git
cd deepseek-monitor
npm install
npm run electron:dev
```

### 打包编译

```bash
npm run electron:build
```

产物在 `dist/` 目录中：
- Windows: `.exe` 安装器
- macOS: `.dmg` 文件
- Linux: `AppImage` 文件

### 数据存储

- API Key 与登录 Cookie 使用 `electron-store` 加密存储在本机
- 零遥测，所有数据仅本地运行

---

## 2. Danniez/DeepSeek-DeskBand（任务栏余额显示）

| 属性 | 值 |
|------|-----|
| GitHub | https://github.com/Danniez/DeepSeek-DeskBand |
| Stars | - |
| 技术栈 | C# (.NET) |
| 平台 | Windows 任务栏 |

### 简介

Windows 任务栏余额显示器，直接在任务栏实时显示 DeepSeek API 可用余额。

> 本项目所有代码均由 Github Copilot 使用 DeepSeek-V4 模型生成。

### 功能一览

| 功能 | 说明 |
|------|------|
| 余额显示 | 任务栏实时显示 `xx.xx` |
| 自动刷新 | 每 30 秒自动查询 |
| 状态灯 | 绿=正常 / 黄=未配置 / 红=错误 |
| 详情面板 | 点击弹出：总余额 / 充值余额 / 赠送余额 |
| 安全存储 | API Key 存 Windows Credential Manager，卸载自动清除 |

### 安装方式

**MSI 安装包（推荐）**：
1. 双击 `DeepSeekDeskBand.msi` → 下一步 → 安装
2. 右键任务栏 → **工具栏** → 勾选 **"DeepSeek DeskBand"**
3. 左键点击组件 → **设置 API Key**

### 卸载

**设置 → 应用 → 应用和功能 → DeepSeek DeskBand → 卸载**

---

## 3. Joyi-code/DeepSeekMonitorWindows（Tauri 版）

| 属性 | 值 |
|------|-----|
| GitHub | https://github.com/Joyi-code/DeepSeekMonitorWindows |
| Stars | 31 |
| 技术栈 | Tauri + React + Rust |
| 语言 | TypeScript |
| 平台 | Windows |
| 许可证 | MIT |

### 简介

基于原作者 felikschu 的支持，给自己的 DeepSeek 余额监控小工具，原先项目仅支持 macOS 平台，目前项目已开源，支持 Windows 平台。

### 功能

- DeepSeek 账户余额实时监控
- Windows 桌面应用

---

## 4. SrtaEstrella/DeepSeekBalanceMonitor（原版，跨平台）

| 属性 | 值 |
|------|-----|
| GitHub | https://github.com/SrtaEstrella/DeepSeekBalanceMonitor |
| 平台 | Windows / Linux |
| 构建 | Python 和 Rust 两种 |

### 简介

Windows 托盘应用和 Linux CLI/Plasma widget，定时查询 DeepSeek API 余额并在余额不足时告警。

### 功能

- **系统托盘**：定时查询余额，余额不足时告警
- **Rainmeter 桌面组件**（可选）：读取本地运行状态（`127.0.0.1:17654`），不存储 API Key
- **KDE Plasma 6 widget**（Linux）
- 支持 Rust 和 Python 两种构建

### 平台要求

| 平台 | 要求 |
|------|------|
| Py-Win | Windows 10+ |
| Rust-Win | Windows 7 SP1+ / 8.1 / 10 / 11 |
| Rust-Linux | RHEL 8 / Ubuntu 20.04+ glibc，KDE Plasma 6.0+ |
| Py-Mac | macOS 10.14+ |

### Rainmeter 安装步骤

1. 从 rainmeter.net 安装 Rainmeter
2. 运行任意 Windows 版本（Python 或 Rust）— 本地状态接口自动启动
3. 从 Releases 下载 `deepseek-balance-monitor-*-rainmeter.rmskin`
4. 双击 `.rmskin` 文件安装皮肤
5. 在 Rainmeter 中加载 `DeepSeekBalanceMonitor\DeepSeekBalanceMonitor.ini`（英文版用 `.en.ini`）

### 高 DPI 屏幕处理

`.exe` → 属性 → 兼容性 → 更改高 DPI 设置 → 勾选「替代高 DPI 缩放行为」并选择「应用程序」。然后加载 2x 缩放的 `DeepSeekBalanceMonitor.hd.ini`（或 `.en.hd.ini`）。

---

## 5. wenyinos/DeepSeekBalanceMonitor（Fork 版）

| 属性 | 值 |
|------|-----|
| GitHub | https://github.com/wenyinos/DeepSeekBalanceMonitor |
| Stars | - |
| 类型 | Fork of SrtaEstrella/DeepSeekBalanceMonitor |

### 简介

Windows 系统托盘应用，定时查询 DeepSeek API 账户余额，以动态托盘图标显示，余额不足时告警。

---

## 对比总结

| 项目 | Stars | 特色 | 适合场景 |
|------|-------|------|----------|
| MiaTxxx/Deepseek- | 较高 | 悬浮窗+托盘+趋势图+用量分析，功能最全 | 需要全面监控 API 用量和费用 |
| Danniez/DeepSeek-DeskBand | - | 任务栏直接显示余额，极轻量 | 只想快速看余额 |
| Joyi-code/DeepSeekMonitorWindows | 31 | Tauri 构建，轻量级 | 喜欢 Tauri 技术栈 |
| SrtaEstrella/DeepSeekBalanceMonitor | - | 原版，支持 Rainmeter/Plasma | 需要桌面组件 |
| wenyinos/DeepSeekBalanceMonitor | - | Fork 版 | - |

---

## 相关资源

- [DeepSeek 官网](https://www.deepseek.com/)
- [DeepSeek API Key 获取](https://platform.deepseek.com/api_keys)
- [DeepSeek GUI（AI 工作台）](https://github.com/XingYu-Zhong/DeepSeek-GUI)
