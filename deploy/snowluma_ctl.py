"""SnowLuma 版运维控制脚本（自检 / 停止）。

用途：
  python deploy/snowluma_ctl.py check        # 全网体检：目录、端口、进程、日志、QQ 版本
  python deploy/snowluma_ctl.py stop         # 精确停止 SnowLuma 与业务框架（不碰 NapCat 旧栈）
  python deploy/snowluma_ctl.py stop --yes   # 跳过交互确认

设计原则：
  - 只按"端口属主 PID + 可执行文件路径"定位目标进程，绝不做 taskkill /IM 这类模糊杀进程，
    避免连带杀掉同 Console/Job 树里的旧栈（NapCat 主号）或看门狗。
  - 自检输出全部为可读文本，不依赖第三方库（只用标准库）。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # QQ机器人-SnowLuma-NoneBot/
SNOWLUMA_DIR = BASE / "SnowLuma"
BOT_DIR = BASE / "qq-group-bot"
CONFIG_PATH = BASE / "部署配置.json"

DEFAULTS = {
    "snowluma_dir": "SnowLuma",
    "snowluma_bot_qq": "1000000001",
    "snowluma_webui_port": 5099,
    "snowluma_http_port": 3100,
    "snowluma_ws_port": 3001,
    "bot_port": 8081,
}

OK = "[OK]  "
WARN = "[WARN]"
BAD = "[BAD] "
INFO = "[INFO]"

PROBLEMS: list[str] = []
SUGGESTS: list[str] = []


def say(tag: str, msg: str):
    print(f"{tag} {msg}")
    if tag == BAD:
        PROBLEMS.append(msg)


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            for k in DEFAULTS:
                if k in raw and raw[k] not in ("", None):
                    cfg[k] = raw[k]
            cfg["bot_port"] = int(raw.get("bot_port", cfg["bot_port"]))
        except Exception as exc:
            say(WARN, f"读取 部署配置.json 失败，改用默认值：{exc}")
    return cfg


def sl_dir_hint(cfg: dict) -> Path:
    """解析 SnowLuma 目录（支持绝对/相对配置）。"""
    d = Path(cfg["snowluma_dir"])
    return d if d.is_absolute() else BASE / d


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.6) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def pid_of_port(port: int) -> int | None:
    """通过 netstat 解析监听指定端口的 PID。"""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=20).stdout.decode("gbk", "replace")
    except Exception:
        return None
    pat = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)", re.M)
    m = pat.search(out)
    return int(m.group(1)) if m else None


def exe_path(pid: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wt.DWORD(2048)
        buf = ctypes.create_unicode_buffer(2048)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        k32.CloseHandle(h)


def newest_log(folder: Path, pattern: str) -> Path | None:
    items = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def tail_text(path: Path, limit: int = 400_000) -> str:
    try:
        data = path.read_bytes()
        return data[-limit:].decode("utf-8", "replace")
    except Exception:
        return ""


def find_qq_install() -> tuple[str, str | None, list[str]]:
    """返回 (安装目录, 版本号, 待安装的更新包列表)。"""
    candidates: list[Path] = []

    for drive in ("C:", "D:", "E:", "F:", "G:"):
        for sub in ("Program Files\\Tencent\\QQNT", "Program Files (x86)\\Tencent\\QQNT",
                    "Program Files\\qq", "Program Files (x86)\\qq", "Tencent\\QQNT", "qq"):
            p = Path(f"{drive}\\{sub}")
            if (p / "QQ.exe").exists():
                candidates.append(p)

    for root in (Path.home() / "AppData/Local/Programs", Path("C:/Program Files/Tencent")):
        if root.exists():
            for p in root.glob("**/QQ.exe"):
                candidates.append(p.parent)

    for p in candidates:
        vers = p / "versions"
        if vers.is_dir():
            version = None
            pending = []
            for item in vers.iterdir():
                if item.is_dir() and re.fullmatch(r"\d+\.\d+\.\d+-\d+", item.name):
                    version = item.name
                elif item.suffix == ".zip":
                    pending.append(item.name)
            return str(p), version, pending
    return "", None, []


def snowluma_supported_qq() -> str | None:
    """从 SnowLuma 主程序里读出它对齐的 QQ 版本号。"""
    hits = list(SNOWLUMA_DIR.glob("*.mjs")) + list(SNOWLUMA_DIR.glob("*.js"))
    for f in hits:
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = re.search(r'qqVersion\s*:\s*"([\d.]+-\d+)"', txt)
        if m:
            return m.group(1)
    return None


def check() -> int:
    cfg = load_cfg()
    sl_dir = sl_dir_hint(cfg)
    uin = str(cfg["snowluma_bot_qq"])

    print("=" * 62)
    print("  QQ机器人（SnowLuma + NoneBot）自检")
    print(f"  时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 62)

    # ---------- 1. 文件完整性 ----------
    print("\n【1】文件完整性")
    needed = {
        "协议端入口": sl_dir / "launcher.bat",
        "协议端内核": sl_dir / "node.exe",
        "hook 组件": sl_dir / "native" / "snowluma-win32-x64.dll",
        "业务框架入口": BOT_DIR / "bot.py",
        "业务框架依赖清单": BOT_DIR / "requirements.txt",
    }
    for label, p in needed.items():
        if p.exists():
            say(OK, f"{label}：{p.relative_to(BASE) if BASE in p.parents else p}")
        else:
            say(BAD, f"缺少{label}：{p}")
    if not (sl_dir / "launcher.bat").exists():
        SUGGESTS.append("SnowLuma 未就绪：双击『一键部署-SnowLuma版.bat』，或见 docs\\部署说明-SnowLuma版.md 第 3 节")

    py = BASE / "venv" / "Scripts" / "python.exe"
    if py.exists():
        say(OK, f"项目虚拟环境：venv\\Scripts\\python.exe")
    else:
        say(WARN, "未找到项目虚拟环境 venv\\，启动脚本会自动探测系统里装了 nonebot 的 Python")

    # ---------- 2. QQ 客户端版本（hook 能否注入的关键） ----------
    print("\n【2】桌面版 QQ（NTQQ）版本匹配")
    qq_dir, qq_ver, pending = find_qq_install()
    supported = snowluma_supported_qq()
    if not qq_dir:
        say(BAD, "未找到桌面版 QQ（QQ.exe）安装目录，SnowLuma 需要注入正在运行的 QQ.exe")
        SUGGESTS.append("安装桌面版 QQ：https://im.qq.com/pcqq/index.shtml")
    else:
        say(OK, f"QQ 安装目录：{qq_dir}")
        say(INFO, f"已安装版本：{qq_ver or '未知'}")
        say(INFO, f"SnowLuma 对齐版本：{supported or '未读取到'}")
        if supported and qq_ver:
            if qq_ver == supported:
                say(OK, "版本完全匹配，hook 可正常注入")
            else:
                say(WARN, f"版本不一致（装了 {qq_ver}，SnowLuma 对齐 {supported}）：若 hook 注入失败，先怀疑这里")
                SUGGESTS.append(f"把 QQ 装回 {supported}，或等 SnowLuma 发新版适配")
        if pending:
            say(WARN, f"检测到已下载的 QQ 更新包：{', '.join(pending)}（QQ 一旦自动升级可能破坏 hook）")
            SUGGESTS.append("到 QQ 设置里关闭自动更新")

    # ---------- 3. 端口与进程 ----------
    print("\n【3】端口与进程")
    ports = {
        f"SnowLuma WebUI（{cfg['snowluma_webui_port']}）": cfg["snowluma_webui_port"],
        f"SnowLuma WS 服务端（{cfg['snowluma_ws_port']}）": cfg["snowluma_ws_port"],
        f"SnowLuma HTTP（{cfg['snowluma_http_port']}）": cfg["snowluma_http_port"],
        f"业务框架 NoneBot（{cfg['bot_port']}）": cfg["bot_port"],
    }
    sl_pids, bot_pid = set(), None
    for label, port in ports.items():
        pid = pid_of_port(port)
        if pid:
            exe = exe_path(pid)
            say(OK, f"{label} 监听中（PID {pid}，{Path(exe).name}）")
            if port != cfg["bot_port"]:
                sl_pids.add(pid)
            else:
                bot_pid = pid
        else:
            say(BAD, f"{label} 未监听")
    if not sl_pids:
        SUGGESTS.append("协议端没起来：双击『启动-SnowLuma版.bat』（SnowLuma 需桌面版 QQ 处于登录状态）")
    if not bot_pid:
        SUGGESTS.append("业务框架没起来：同上，启动脚本会一并拉起")

    # 旧栈端口（提示信息，不算故障）
    nap_ports = [p for p in (3000, 6099) if port_open(p)]
    if nap_ports:
        say(INFO, f"另一个项目（原 NapCat 版机器人）仍在运行，占用端口：{', '.join(map(str, nap_ports))}（两个项目可并存）")

    # ---------- 4. 协议端日志 ----------
    print("\n【4】协议端日志（SnowLuma）")
    log_dir = sl_dir / "logs"
    log_file = newest_log(log_dir, "snowluma-*.log") if log_dir.is_dir() else None
    if not log_file:
        say(BAD, "未找到 SnowLuma 日志，协议端可能从未启动成功")
    else:
        txt = tail_text(log_file)
        say(INFO, f"日志文件：{log_file.name}（{log_file.stat().st_size // 1024} KB）")
        if f"login detected: PID=" in txt and f"UIN={uin}" in txt:
            say(OK, f"hook 注入成功，账号 {uin} 已登录")
        elif "login detected" in txt:
            say(WARN, "有 hook 注入记录，但账号与配置里的小号不一致（是不是登错号了）")
        else:
            say(BAD, "日志里没有 hook 注入记录：QQ 未运行 / 权限不一致 / QQ 版本不匹配")
            SUGGESTS.append("确认桌面版 QQ 已登录，且 SnowLuma 与 QQ 用同一个 Windows 用户、同样权限运行")
        if f"[nonebot-business] connected ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws" in txt:
            say(OK, f"已连上业务框架（ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws）")
        elif "WS-Client]" in txt and "connected" in txt:
            say(WARN, "WS 客户端有连接记录，但目标地址不是业务框架 → 检查 SnowLuma\\config\\onebot_%s.json 的 wsClients" % uin)
        else:
            say(BAD, "WS 客户端未连接到业务框架")
            SUGGESTS.append(f"在 SnowLuma WebUI(5099) → 网络配置里加 WebSocket 客户端：ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws")

    # ---------- 5. 业务框架日志 ----------
    print("\n【5】业务框架（NoneBot）")
    bot_log = BASE / "logs" / "bot.log"
    if not bot_log.exists():
        say(WARN, "未找到 logs\\bot.log（业务框架可能由『启动-SnowLuma版.bat』在控制台直接输出）")
    else:
        btxt = tail_text(bot_log)
        if f"Bot {uin} connected" in btxt:
            say(OK, f"小号 {uin} 已接入业务框架，群管功能生效")
        else:
            hits = re.findall(r"Bot (\d+) connected", btxt)
            if hits:
                say(WARN, f"业务框架当前接入的是 {', '.join(sorted(set(hits)))}，未见小号 {uin}")
            else:
                say(BAD, "业务框架还没有任何账号接入记录")

    # ---------- 汇总 ----------
    print("\n" + "=" * 62)
    if PROBLEMS:
        print(f"  结论：发现 {len(PROBLEMS)} 个问题")
        for i, p in enumerate(PROBLEMS, 1):
            print(f"   {i}. {p}")
    else:
        print("  结论：核心链路正常（SnowLuma 协议端 + NoneBot 业务框架）")
    if SUGGESTS:
        print("\n  建议动作：")
        for s in dict.fromkeys(SUGGESTS):
            print(f"   - {s}")
    print("=" * 62)
    return 0 if not PROBLEMS else 1


def stop(yes: bool = False) -> int:
    cfg = load_cfg()
    targets: list[tuple[str, int, str]] = []

    for label, port in (("SnowLuma", cfg["snowluma_webui_port"]),
                        ("SnowLuma", cfg["snowluma_ws_port"]),
                        ("SnowLuma", cfg["snowluma_http_port"]),
                        ("业务框架 NoneBot", cfg["bot_port"])):
        pid = pid_of_port(port)
        if not pid:
            continue
        exe = exe_path(pid)
        lower, name = exe.lower(), Path(exe).name.lower()
        is_snowluma = name == "node.exe" and ("snowluma" in lower or str(sl_dir_hint(cfg)).lower() in lower)
        is_bot = name.startswith("python")
        if (label == "SnowLuma" and is_snowluma) or (label != "SnowLuma" and is_bot):
            targets.append((label, pid, exe))
        else:
            print(f"{WARN} 端口 {port} 被 {exe} 占用（PID {pid}），看起来不是本项目进程，跳过")

    if not targets:
        print(f"{INFO} 没有发现需要停止的进程")
        return 0

    print("即将停止下列进程：")
    for label, pid, exe in targets:
        print(f"  - {label}：PID {pid}  {exe}")
    print("\n注意：不会动旧栈（NapCat 主号 / 看门狗），旧机器人会继续运行。")
    if not yes:
        ans = input("确认停止？输入 Y 继续：").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消")
            return 0

    k32 = ctypes.windll.kernel32
    PROCESS_TERMINATE = 0x0001
    for label, pid, exe in targets:
        h = k32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if h:
            k32.TerminateProcess(h, 0)
            k32.CloseHandle(h)
            print(f"{OK} 已停止 {label}（PID {pid}）")
        else:
            print(f"{BAD} 无法停止 {label}（PID {pid}），可能需要管理员权限")
    return 0


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action == "check":
        return check()
    if action == "stop":
        return stop(yes="--yes" in sys.argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
