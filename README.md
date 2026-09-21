<div align="center">

# QQ Group Manager Bot

**基于 SnowLuma + NoneBot2 的 QQ 群管理机器人**

_以真实桌面 QQ 为协议底座，标准 OneBot v11 接口，开箱即用的群管插件套件_

[![Release](https://img.shields.io/github/v/release/GuiDI-666/qq-group-bot-snowluma?include_prereleases&color=blue)](https://github.com/GuiDI-666/qq-group-bot-snowluma/releases)
[![OneBot v11](https://img.shields.io/badge/OneBot-v11-black)](https://github.com/botuniverse/onebot-11)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)](README.md#-快速开始)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

</div>

---

## ✨ 功能特性

一套覆盖日常群管场景的插件套件，全部命令以 `/` 前缀触发：

| 模块 | 能力 |
|---|---|
| 🛡 **入群自动审批** | 按申请者 QQ 等级自动通过 / 拒绝，可设生效群、兜底策略（`approve`/`reject`/`ignore`）与拒绝理由模板 |
| 🧹 **广告拦截** | 正则规则 + 违禁词双通道，命中即撤回并禁言，时长可配 |
| ⛔ **黑名单** | 拉黑并踢出、拒绝其再入群；被拉黑用户入群申请自动拒绝 |
| 🔇 **禁言 / 踢出** | `@某人` 或 QQ 号均可定位，时长默认 10 分钟，可自定义 |
| 👋 **欢迎 / 退群提示** | 模板支持 `{at}`、`{nickname}`、`{level}` 占位符，群里随时改 |
| 🤫 **全局静默** | `h`/`m`/`s` 三种时长单位，静默期间对所有群完全静默 |
| 📊 **活跃统计** | 一键拉取超过 N 天未发言的成员名单 |
| ⚙️ **运行时设置** | 等级门槛、广告规则、提示语、管理群名单全部可通过命令热修改，`/查看设置` 一屏总览 |

<details>
<summary><b>📖 完整命令表（点击展开）</b></summary>

| 命令 | 说明 | 权限 |
|---|---|---|
| `/禁言 @某人 [分钟]` | 禁言，默认 10 分钟 | 管理员/群主 |
| `/解禁 @某人` | 解除禁言 | 管理员/群主 |
| `/踢出 @某人` | 移出群聊 | 群主 |
| `/拉黑 @某人 [原因]` | 拉黑并踢出 | 管理员/群主 |
| `/解除拉黑 @某人` | 移出黑名单 | 管理员/群主 |
| `/黑名单` | 查看黑名单 | 管理员/群主 |
| `/设置等级 30` | 修改入群审批等级门槛 | 管理员/群主 |
| `/查看等级` | 查看入群审批完整设置 | 管理员/群主 |
| `/查看设置` | 所有设置一屏总览 | 管理员/群主 |
| `/添加广告` / `/删除广告` | 维护广告拦截规则 | 管理员/群主 |
| `/广告列表` | 查看广告规则与违禁词 | 管理员/群主 |
| `/设置欢迎` / `/设置退群` | 修改欢迎语 / 退群提示 | 管理员/群主 |
| `/添加管理群` / `/移除管理群` | 设置生效群白名单（私聊） | 超级管理员 |
| `/静默 2h` / `/静默 off` | 全局静默 / 解除（私聊） | 管理员 |
| `/未发言 30` | 拉取 N 天未发言成员 | 管理员/群主 |
| `/ping` / `/状态` | 存活检查与运行状态 | 所有人 |

</details>

## 🏗 架构

```
┌─────────────────┐    hook 注入    ┌──────────────────────┐
│  桌面版 QQ 客户端 │ ◄────────────  │  SnowLuma 协议端      │
│  (真实 NTQQ)     │                │  WebUI:5099          │
└─────────────────┘                │  HTTP :3100 (OneBot) │
                                   │  WS   :3001 (OneBot) │
                                   └──────────┬───────────┘
                                              │ WebSocket (反向 WS)
                                              ▼
                                   ┌──────────────────────┐
                                   │  NoneBot2 业务框架     │
                                   │  :8081  群管插件套件   │
                                   └──────────────────────┘
```

**为什么选 SnowLuma 作协议端？**

- SnowLuma 通过 **hook 注入真实桌面版 QQ 客户端**，协议表现接近真人客户端，规避非官方协议端常见的风控踢下线问题
- 输出标准 **OneBot v11**，与 NapCat 等主流协议端接口一致，NoneBot2 侧插件无需任何改动即可迁移
- 自带 Node.js 运行时，解压即用，无额外环境依赖

## 📦 快速开始

### 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（x64） |
| 桌面版 QQ | **9.9.28-46928**（见下方版本警告） |
| Python | 3.9 ~ 3.13（部署脚本可自动寻找/安装） |
| Node.js | 无需安装（SnowLuma 自带） |

> ### ⚠️ QQ 版本强绑定
> SnowLuma 的 hook 与 QQ 版本**严格对齐**。当前对齐版本为 **QQ 9.9.28-46928**：
> - 安装任何更高版本（如 9.9.35+）hook 即失效
> - **必须关闭 QQ 自动更新**；若发现 `QQ安装目录\versions\` 下出现形如 `9.9.28-46928-9.9.32-*.zip` 的升级包，**立即删除**
> - 协议端 SnowLuma 可独立升级（升级它不必动 QQ）
> - 运行 `自检-SnowLuma版.bat` 可一键确认当前版本是否匹配

### 三步跑通

```bat
:: 1. 克隆仓库
git clone https://github.com/GuiDI-666/qq-group-bot-snowluma.git
cd qq-group-bot-snowluma

:: 2. 复制配置模板并填入自己的参数（账号、端口、路径）
copy 部署配置.example.json 部署配置.json

:: 3. 双击运行（或命令行执行）
一键部署-SnowLuma版.bat   :: 准备 Python 环境 → 解压 SnowLuma → 写 OneBot 配置 → 体检
启动-SnowLuma版.bat       :: 启动协议端 + 业务框架
```

随后在浏览器打开 **http://127.0.0.1:5099**（SnowLuma 面板）扫码登录机器人账号，
最后用 `自检-SnowLuma版.bat` 做全链路体检。详见 **[docs/部署说明.md](docs/部署说明.md)**。

### 一键脚本一览

| 脚本 | 用途 |
|---|---|
| `一键部署-SnowLuma版.bat` | 准备 Python 环境与依赖 → 解压 SnowLuma → 写 OneBot 配置 → 体检 |
| `启动-SnowLuma版.bat` | 启动协议端（新窗口）+ 业务框架 |
| `自检-SnowLuma版.bat` | 全链路体检：目录、QQ 版本、端口、hook 注入、WS 连接、账号接入 |
| `切换账号.bat` | 切换登录账号（自动卸载旧账号 hook、重载目标账号） |
| `关闭-SnowLuma版.bat` | 精确停止本套进程（按端口属主定位，不误伤其它程序） |

## ⚙️ 配置

所有参数集中在 **`部署配置.json`**（模板见 `部署配置.example.json`），业务侧的群管策略
（等级门槛、广告规则、提示语等）优先通过群内命令修改，落盘于 `qq-group-bot/config.json`。

<details>
<summary><b>主要配置项（点击展开）</b></summary>

```jsonc
{
  "snowluma_dir": "SnowLuma",          // 协议端目录（可写绝对路径）
  "snowluma_bot_qq": "123456789",      // 机器人登录的 QQ 号
  "bot_port": 8081,                    // NoneBot 监听端口
  "snowluma_http_port": 3100,          // SnowLuma OneBot HTTP
  "snowluma_ws_port": 3001,            // SnowLuma OneBot WS
  "snowluma_webui_port": 5099          // SnowLuma WebUI
}
```

</details>

## 🗺 端口分配

| 端口 | 归属 |
|---|---|
| 5099 | SnowLuma WebUI（管理面板） |
| 3100 | SnowLuma OneBot HTTP |
| 3001 | SnowLuma OneBot WS |
| 8081 | NoneBot2 业务框架 |

## 📖 文档

| 文档 | 内容 |
|---|---|
| [docs/部署说明.md](docs/部署说明.md) | 从零部署到跑通的完整步骤、排障表、维护要点 |
| [docs/功能说明.md](docs/功能说明.md) | 群管功能清单、完整命令表、配置项说明 |
| [docs/框架调研与迁移决策.md](docs/框架调研与迁移决策.md) | 协议端选型调研与决策记录 |
| [CHANGELOG.md](CHANGELOG.md) | 版本更新说明 |

## ❗ 注意事项

- SnowLuma 必须与桌面版 QQ 以**同一个 Windows 用户、相同权限**运行，否则注入失败
- 同一个 QQ 号**不要同时接入两个协议端**（如 SnowLuma 与 NapCat 同时在线会互踢）
- 切换登录账号请使用 `切换账号.bat`，手动复制配置文件会造成端口占用（`EADDRINUSE`）
- 业务框架必须在 `qq-group-bot/` 目录下启动，否则读不到 `.env`、端口会落错

## 📄 免责声明

- 本项目基于第三方协议端 **SnowLuma**（hook 真实桌面 QQ）与 **NoneBot2** 构建，与腾讯官方无任何关联
- 仅供**学习研究**使用，请遵守当地法律法规及腾讯软件许可协议；因使用本项目产生的账号风控、封禁等后果由使用者自行承担
- 请勿用于任何商业用途或灰产场景

## 📃 License

本项目以 [MIT](./LICENSE) 许可证开源。仓库内 `SnowLuma/` 协议端为其独立发行物，
遵循 SnowLuma 原始许可（source-available，非商业使用需授权），详见其官方仓库。
