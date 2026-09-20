"""SnowLuma 账号管理脚本（切换登录账号 / 卸载 hook）。

作用：
  把"在 5099 网页上点卸载、再重新加载账号"这套手工操作，变成一条命令。
  走的是 SnowLuma WebUI 自己的 HTTP API（和网页同一条通道），不靠改配置文件，
  因此不会出现"两个账号同时建 session、抢 3100/3001 端口"的脏状态。

用法：
  python deploy/snowluma_account.py list              # 列出 QQ 进程 / 账号 / 加载状态
  python deploy/snowluma_account.py list --raw        # 附带服务端原始 JSON（排障用）
  python deploy/snowluma_account.py switch 1000000001  # 切换到目标账号（卸载其它账号 + 重载目标）
  python deploy/snowluma_account.py unload 2000000002  # 只卸载某个账号的 hook
  python deploy/snowluma_account.py unload 17700      # 也支持按进程 PID 卸载

密码来源（不落盘）：
  - 环境变量 SNOWLUMA_WEBUI_PASSWORD
  - 否则交互式输入（不回显）

能脚本化 / 不能脚本化的边界：
  - 「在 SnowLuma 里卸载旧账号、加载目标账号」-> 本脚本全自动（走 API）
  - 「QQ 客户端退出旧号 / 登录新号」           -> 无法脚本化（需要密码与手机验证，
    QQ 客户端也不提供稳定可用的命令行换号接口）。所以本脚本要求目标账号
    已经在桌面版 QQ 里登录好；没登录就只提示、不做任何破坏性操作。
"""
from __future__ import annotations

import getpass
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # QQ机器人-SnowLuma-NoneBot/
SNOWLUMA_DIR = BASE / "SnowLuma"
CONFIG_PATH = BASE / "部署配置.json"

DEFAULTS = {
    "snowluma_dir": "SnowLuma",
    "snowluma_bot_qq": "",
    "snowluma_webui_port": 5099,
    "snowluma_http_port": 3100,
    "snowluma_ws_port": 3001,
    "bot_port": 8081,
}

# 服务端字段名可能随版本变化，一律做多键兼容
UIN_KEYS = ("uin", "qq", "qqNumber", "qq_number", "account", "loginUin", "login_uin",
            "bizUin", "biz_uin", "uinStr", "qqUin")
NICK_KEYS = ("nickname", "nickName", "nick", "name", "displayName")
PID_KEYS = ("pid", "processId", "process_id", "id")
STATE_KEYS = ("state", "status", "phase", "hookState")
LOADED_KEYS = ("loaded", "hookLoaded", "injected", "hooked", "active", "injectedHook")
LOADED_STATES = {"loaded", "inject", "injected", "active", "running", "hooked", "on"}

OK = "[OK]  "
WARN = "[WARN]"
BAD = "[BAD] "
INFO = "[INFO]"


def say(tag: str, msg: str):
    print(f"{tag} {msg}")


# --------------------------------------------------------------------------- 配置

def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            for k in DEFAULTS:
                if k in raw and raw[k] not in ("", None):
                    cfg[k] = raw[k]
            cfg["snowluma_webui_port"] = int(raw.get("snowluma_webui_port", cfg["snowluma_webui_port"]))
            cfg["snowluma_http_port"] = int(raw.get("snowluma_http_port", cfg["snowluma_http_port"]))
            cfg["snowluma_ws_port"] = int(raw.get("snowluma_ws_port", cfg["snowluma_ws_port"]))
            cfg["bot_port"] = int(raw.get("bot_port", cfg["bot_port"]))
        except Exception as exc:
            say(WARN, f"读取 部署配置.json 失败，改用默认值：{exc}")
    return cfg


def save_cfg_qq(uin: str):
    """把目标账号写回 部署配置.json，让启动/自检脚本口径一致。"""
    if not CONFIG_PATH.exists():
        return
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        if str(raw.get("snowluma_bot_qq", "")) == uin:
            return
        old = raw.get("snowluma_bot_qq", "")
        raw["snowluma_bot_qq"] = uin
        CONFIG_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        say(OK, f"部署配置.json：snowluma_bot_qq {old} -> {uin}")
    except Exception as exc:
        say(WARN, f"更新 部署配置.json 失败：{exc}")


def sl_dir(cfg: dict) -> Path:
    d = Path(cfg["snowluma_dir"])
    return d if d.is_absolute() else BASE / d


# --------------------------------------------------------------------------- HTTP

def webui_base(cfg: dict) -> str:
    # SNOWLUMA_WEBUI_PORT 仅用于联调/测试（指向模拟服务），日常不用设
    port = os.environ.get("SNOWLUMA_WEBUI_PORT") or cfg["snowluma_webui_port"]
    return f"http://127.0.0.1:{port}"


def http_json(url: str, method: str = "GET", token: str | None = None,
              payload: dict | None = None, timeout: float = 15.0):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "snowluma-account-script"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"message": body[:200]}
        return e.code, parsed
    except Exception as e:
        return 0, {"message": f"{type(e).__name__}: {e}"}


def get_password() -> str | None:
    pwd = os.environ.get("SNOWLUMA_WEBUI_PASSWORD")
    if pwd:
        return pwd
    if not sys.stdin.isatty():
        say(BAD, "没有交互终端，也未设置环境变量 SNOWLUMA_WEBUI_PASSWORD")
        return None
    try:
        return getpass.getpass("请输入 SnowLuma WebUI 登录密码（不回显、不保存）：")
    except Exception as exc:
        say(BAD, f"读取密码失败：{exc}")
        return None


def login(cfg: dict) -> str | None:
    pwd = get_password()
    if not pwd:
        return None
    code, resp = http_json(webui_base(cfg) + "/api/login", "POST", payload={"password": pwd})
    if code == 200 and isinstance(resp.get("token"), str) and resp["token"]:
        return resp["token"]
    if resp.get("needsTotp"):
        say(BAD, "WebUI 已开启两步验证（TOTP）：请在网页上操作，或先用网页关掉 TOTP")
        return None
    if code == 0:
        say(BAD, f"连不上 SnowLuma WebUI（{webui_base(cfg)}）：{resp.get('message')}")
        say(INFO, "协议端没起来？双击『启动-SnowLuma版.bat』后再试")
    else:
        say(BAD, f"登录失败（HTTP {code}）：{resp.get('message') or resp}")
    return None


# --------------------------------------------------------------------------- 进程

def pick(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    for v in d.values():
        if isinstance(v, dict):
            r = pick(v, keys, None)
            if r is not None:
                return r
    return default


def is_loaded(p: dict) -> bool | None:
    v = pick(p, LOADED_KEYS, None)
    if isinstance(v, bool):
        return v
    st = pick(p, STATE_KEYS, None)
    if isinstance(st, str):
        return st.strip().lower() in LOADED_STATES
    return None


def norm(p: dict) -> dict:
    uin = pick(p, UIN_KEYS, None)
    pid = pick(p, PID_KEYS, None)
    return {
        "uin": str(uin) if uin not in (None, "") else "",
        "pid": int(pid) if str(pid or "").isdigit() else None,
        "nick": str(pick(p, NICK_KEYS, "") or ""),
        "loaded": is_loaded(p),
        "raw": p,
    }


def get_processes(token: str, cfg: dict) -> tuple[list[dict], dict]:
    code, resp = http_json(webui_base(cfg) + "/api/processes", token=token)
    if code != 200:
        say(BAD, f"获取进程列表失败（HTTP {code}）：{resp.get('message') or resp}")
        return [], resp
    items = resp.get("list") or resp.get("processes") or (resp if isinstance(resp, list) else [])
    return [norm(x) for x in items if isinstance(x, dict)], resp


def print_processes(procs: list[dict], me: str = ""):
    if not procs:
        say(WARN, "SnowLuma 没有检测到任何 QQ 进程（桌面版 QQ 没运行？）")
        return
    print()
    print(f"  {'PID':<8} {'QQ 号':<12} {'昵称':<14} {'hook 状态':<10}")
    print("  " + "-" * 50)
    for p in procs:
        mark = "  <- 目标" if me and p["uin"] == me else ""
        st = {True: "已加载", False: "未加载", None: "未知"}[p["loaded"]]
        print(f"  {str(p['pid'] or '-'):<8} {p['uin'] or '-':<12} {p['nick'][:12]:<14} {st:<10}{mark}")
    print()


def api_process(token: str, cfg: dict, pid: int, action: str) -> bool:
    code, resp = http_json(f"{webui_base(cfg)}/api/processes/{pid}/{action}", "POST", token=token)
    if code == 200:
        say(OK, f"进程 {pid}：{action} 成功")
        return True
    say(BAD, f"进程 {pid}：{action} 失败（HTTP {code}）：{resp.get('message') or resp}")
    return False


# --------------------------------------------------------------------------- 配置模板

def onebot_template(cfg: dict, uin: str) -> dict:
    """按本项目口径生成某个账号的协议端配置（端口避开旧项目 3000，WS 客户端指向业务框架）。"""
    return {
        "mode": "snapshot",
        "networks": {
            "httpServers": [{
                "name": "http-default",
                "accessToken": secrets.token_urlsafe(32),
                "messageFormat": "array",
                "reportSelfMessage": False,
                "host": "127.0.0.1",
                "port": cfg["snowluma_http_port"],
                "path": "/",
                "enableWebSocket": False,
            }],
            "httpClients": [],
            "wsServers": [{
                "name": "ws-default",
                "accessToken": secrets.token_urlsafe(32),
                "messageFormat": "array",
                "reportSelfMessage": False,
                "host": "127.0.0.1",
                "port": cfg["snowluma_ws_port"],
                "path": "/",
                "role": "Universal",
            }],
            "wsClients": [{
                "name": "nonebot-business",
                "messageFormat": "array",
                "reportSelfMessage": False,
                "url": f"ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws",
                "role": "Universal",
                "reconnectIntervalMs": 5000,
            }],
        },
        "statusCommand": {"enabled": True, "swallow": False, "cooldownSeconds": 5, "trigger": "#sl"},
        "historySync": {"enabled": False},
        "notifications": {"channelIds": []},
    }


def ensure_config(cfg: dict, uin: str) -> tuple[Path, bool]:
    """确保目标账号的协议端配置存在且端口/WS 客户端正确。返回 (路径, 是否新建)。"""
    path = sl_dir(cfg) / "config" / f"onebot_{uin}.json"
    if not path.exists():
        path.write_text(json.dumps(onebot_template(cfg, uin), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        say(OK, f"已生成协议端配置：{path.relative_to(BASE)}")
        return path, True

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        say(WARN, f"配置读取失败（{exc}），将按模板重建")
        path.write_text(json.dumps(onebot_template(cfg, uin), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path, True

    changed = False
    nets = data.setdefault("networks", {})
    for key, want in (("httpServers", cfg["snowluma_http_port"]), ("wsServers", cfg["snowluma_ws_port"])):
        for item in nets.get(key) or []:
            if item.get("port") != want:
                say(INFO, f"修正 {key} 端口 {item.get('port')} -> {want}")
                item["port"] = want
                changed = True
    want_url = f"ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws"
    clients = nets.get("wsClients") or []
    if not clients:
        nets["wsClients"] = [{
            "name": "nonebot-business", "messageFormat": "array", "reportSelfMessage": False,
            "url": want_url, "role": "Universal", "reconnectIntervalMs": 5000,
        }]
        say(INFO, f"补上 WS 客户端 -> {want_url}")
        changed = True
    else:
        for cl in clients:
            if cl.get("url") != want_url:
                say(INFO, f"修正 WS 客户端 {cl.get('url')} -> {want_url}")
                cl["url"] = want_url
                cl.setdefault("name", "nonebot-business")
                changed = True

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        say(OK, f"已校正协议端配置：{path.relative_to(BASE)}")
    return path, changed


# --------------------------------------------------------------------------- 命令

def cmd_list(cfg: dict, raw: bool = False) -> int:
    token = login(cfg)
    if not token:
        return 3
    procs, resp = get_processes(token, cfg)
    print_processes(procs)
    if raw:
        print(json.dumps(resp, ensure_ascii=False, indent=2)[:4000])
    return 0


def find_procs(procs: list[dict], key: str) -> list[dict]:
    """key 可以是 QQ 号，也可以是 PID。"""
    if key.isdigit() and len(key) <= 6:
        hit = [p for p in procs if p["pid"] == int(key)]
        if hit:
            return hit
    return [p for p in procs if p["uin"] == key]


def do_unload(token: str, cfg: dict, target: dict, label: str) -> bool:
    if target["pid"] is None:
        say(WARN, f"{label}：拿不到 PID，跳过卸载")
        return False
    return api_process(token, cfg, target["pid"], "unload")


def cmd_unload(cfg: dict, key: str) -> int:
    token = login(cfg)
    if not token:
        return 3
    procs, _ = get_processes(token, cfg)
    print_processes(procs, me=key)
    hits = find_procs(procs, key)
    if not hits:
        say(BAD, f"没找到 QQ={key} 或 PID={key} 的进程")
        return 2
    ok_any = False
    for h in hits:
        ok_any |= do_unload(token, cfg, h, f"QQ {h['uin'] or '?'}")
    return 0 if ok_any else 1


def cmd_switch(cfg: dict, target: str) -> int:
    if not target:
        target = str(cfg.get("snowluma_bot_qq") or "")
    if not target:
        say(BAD, "没指定目标 QQ 号（命令行参数为空，部署配置.json 里也没有）")
        return 2

    token = login(cfg)
    if not token:
        return 3

    print()
    say(INFO, f"目标账号：{target}")
    procs, _ = get_processes(token, cfg)
    print_processes(procs, me=target)

    tgt = [p for p in procs if p["uin"] == target]
    if not tgt:
        say(BAD, f"SnowLuma 没检测到 QQ {target} 的进程：请先在桌面版 QQ 里登录 {target}")
        say(INFO, "QQ 客户端换号需要人工（密码 / 手机验证），脚本无法代劳；登录后再跑一次本命令")
        online = [p["uin"] or f"PID {p['pid']}" for p in procs]
        if online:
            say(INFO, f"当前在线：{', '.join(online)}")
        return 2

    # 1) 卸载所有非目标账号
    others = [p for p in procs if p["uin"] and p["uin"] != target]
    if others:
        print(f"\n【1/3】卸载非目标账号（{len(others)} 个）")
        for p in others:
            do_unload(token, cfg, p, f"QQ {p['uin']}（{p['nick'] or '未知昵称'}）")
    else:
        print("\n【1/3】没有其它账号需要卸载")

    # 2) 校正目标账号的协议端配置
    print("\n【2/3】校正目标账号的协议端配置")
    _, config_changed = ensure_config(cfg, target)

    # 3) 重新加载目标账号（让新配置生效）
    print("\n【3/3】重新加载目标账号")
    tgt_p = tgt[0]
    need_reload = config_changed or (tgt_p["loaded"] is not True)
    if tgt_p["pid"] is not None and need_reload:
        do_unload(token, cfg, tgt_p, f"QQ {target}（重载前卸载）")
        api_process(token, cfg, tgt_p["pid"], "load")
    elif tgt_p["pid"] is not None:
        say(INFO, f"QQ {target} 已处于加载状态，配置无变化，无需重载")

    save_cfg_qq(target)

    # 4) 复核
    print("\n【复核】")
    procs2, _ = get_processes(token, cfg)
    print_processes(procs2, me=target)
    stray = [p["uin"] for p in procs2 if p["uin"] and p["uin"] != target and p["loaded"] is True]
    if stray:
        say(WARN, f"仍有其它账号处于加载状态：{', '.join(stray)}（可在网页上或再跑一次本命令）")
    else:
        say(OK, f"当前只有 {target} 处于接管状态")
    say(INFO, f"接着可双击『自检-SnowLuma版.bat』确认链路；业务框架端口 {cfg['bot_port']}")
    return 0


def main() -> int:
    cfg = load_cfg()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    action = args[0] if args else "list"

    if action == "list":
        return cmd_list(cfg, raw="--raw" in flags)
    if action == "unload":
        if len(args) < 2:
            print(__doc__)
            return 2
        return cmd_unload(cfg, args[1])
    if action == "switch":
        return cmd_switch(cfg, args[1] if len(args) > 1 else "")
    if action == "sync-config":
        uin = args[1] if len(args) > 1 else str(cfg.get("snowluma_bot_qq") or "")
        if not uin:
            say(BAD, "没指定 QQ 号")
            return 2
        path, changed = ensure_config(cfg, uin)
        say(OK if changed else INFO, f"{path.name}：{'已更新' if changed else '无需改动'}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
