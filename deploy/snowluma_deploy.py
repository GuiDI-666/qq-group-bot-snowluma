"""SnowLuma 协议端部署脚本（配合『一键部署-SnowLuma版.bat』）。

做的事情（幂等，可反复运行）：
  1. 定位 SnowLuma 发行包（zip/tar.gz）并解压到项目内的 SnowLuma\\ 目录
     —— 兼容"包内带顶层文件夹"和"包内直接是本体"两种布局
  2. 生成/补齐 SnowLuma 的 OneBot v11 网络配置：
       HTTP 服务端 127.0.0.1:3100（避开旧栈 NapCat 的 3000）
       WS  服务端 127.0.0.1:3001
       WS  客户端 → ws://127.0.0.1:8080/onebot/v11/ws（连本项目业务框架 NoneBot）
  3. 体检并打印后续人工步骤（扫码登录、启动顺序）

注意：Python 依赖（nonebot2 等）由既有的『一键部署.bat』负责，本脚本只管协议端。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE / "部署配置.json"
DEFAULTS = {
    "snowluma_dir": "SnowLuma",
    "snowluma_bot_qq": "1000000001",
    "snowluma_webui_port": 5099,
    "snowluma_http_port": 3100,
    "snowluma_ws_port": 3001,
    "bot_port": 8081,
}
RELEASE_HINT = (
    "下载地址（任选）：\n"
    "   GitHub            https://github.com/SnowLuma/SnowLuma/releases/latest\n"
    "   加速镜像          https://ghfast.top/<Release 资产链接>\n"
    "   包名形如          SnowLuma-vX.Y.Z-win-x64.zip（选完整版，自带 Node.js）\n"
    "   放到项目根目录后重新运行本脚本即可自动解压。"
)


def log(step: str, msg: str):
    print(f"[{step}] {msg}")


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            for k in DEFAULTS:
                if raw.get(k) not in ("", None):
                    cfg[k] = raw[k]
        except Exception as exc:
            log("警告", f"读取 部署配置.json 失败，使用默认值：{exc}")
    return cfg


def sl_dir(cfg: dict) -> Path:
    d = Path(cfg["snowluma_dir"])
    return d if d.is_absolute() else BASE / d


def find_package() -> Path | None:
    pats = ["SnowLuma*.zip", "SnowLuma*.tar.gz"]
    for pat in pats:
        for p in sorted(BASE.glob(pat)):
            if p.stat().st_size > 1024 * 1024:      # 忽略占位小文件
                return p
    return None


def extract(pkg: Path, target: Path) -> bool:
    """解压发行包。返回是否成功。"""
    staging = BASE / ".snowluma_staging"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    log("解压", f"{pkg.name} → {staging.name}\\")
    try:
        if pkg.suffix == ".zip":
            with zipfile.ZipFile(pkg) as z:
                z.extractall(staging)
        else:
            with tarfile.open(pkg) as t:
                t.extractall(staging)
    except Exception as exc:
        log("错误", f"解压失败：{exc}")
        return False

    # 兼容两种布局：带顶层文件夹 / 直接是本体（以 launcher.bat 为准）
    root = staging
    if not (root / "launcher.bat").exists():
        subs = [d for d in root.iterdir() if d.is_dir()]
        for d in subs:
            if (d / "launcher.bat").exists():
                root = d
                break

    if not (root / "launcher.bat").exists():
        log("错误", "解压后没找到 launcher.bat，发行包结构不符合预期")
        return False

    if target.exists():
        backup = target.with_name(target.name + ".bak")
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        log("提醒", f"{target.name}\\ 已存在，旧目录改名为 {backup.name}\\")
        shutil.move(str(target), str(backup))

    shutil.move(str(root), str(target))
    shutil.rmtree(staging, ignore_errors=True)
    log("完成", f"SnowLuma 已就位：{target}")
    return True


def write_onebot_config(cfg: dict, target: Path) -> Path:
    uin = str(cfg["snowluma_bot_qq"])
    cfg_dir = target / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    path = cfg_dir / f"onebot_{uin}.json"

    data: dict = {"mode": "snapshot", "networks": {"httpServers": [], "httpClients": [], "wsServers": [], "wsClients": []}}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            log("配置", f"读取现有配置 {path.name}，仅补齐缺失项")
        except Exception:
            log("警告", f"{path.name} 解析失败，将重建")

    nets = data.setdefault("networks", {})
    for key in ("httpServers", "httpClients", "wsServers", "wsClients"):
        nets.setdefault(key, [])

    http = nets["httpServers"]
    if not any(s.get("name") == "http-default" for s in http):
        http.append({
            "name": "http-default",
            "accessToken": "",
            "messageFormat": "array",
            "reportSelfMessage": False,
            "host": "127.0.0.1",
            "port": int(cfg["snowluma_http_port"]),
            "path": "/",
            "enableWebSocket": False,
        })
        log("配置", f"新增 HTTP 服务端 127.0.0.1:{cfg['snowluma_http_port']}")
    else:
        for s in http:
            if s.get("name") == "http-default":
                s["port"] = int(cfg["snowluma_http_port"])
        log("配置", f"HTTP 服务端端口已校正为 {cfg['snowluma_http_port']}（避开旧栈的 3000）")

    ws_servers = nets["wsServers"]
    if not any(s.get("name") == "ws-default" for s in ws_servers):
        ws_servers.append({
            "name": "ws-default",
            "accessToken": "",
            "messageFormat": "array",
            "reportSelfMessage": False,
            "host": "127.0.0.1",
            "port": int(cfg["snowluma_ws_port"]),
            "path": "/",
            "role": "Universal",
        })
        log("配置", f"新增 WS 服务端 127.0.0.1:{cfg['snowluma_ws_port']}")

    want = f"ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws"
    clients = nets["wsClients"]
    if any(c.get("url") == want for c in clients):
        log("配置", f"WS 客户端已指向业务框架：{want}")
    else:
        keep = [c for c in clients if not c.get("url", "").startswith("ws://127.0.0.1:6199")]
        keep.append({
            "name": "nonebot-business",
            "messageFormat": "array",
            "reportSelfMessage": False,
            "url": want,
            "role": "Universal",
            "reconnectIntervalMs": 5000,
        })
        nets["wsClients"] = keep
        log("配置", f"WS 客户端已设置为业务框架：{want}")

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log("完成", f"已写入 {path}")
    return path


def main() -> int:
    cfg = load_cfg()
    target = sl_dir(cfg)

    print("=" * 62)
    print("  QQ机器人（SnowLuma + NoneBot）协议端部署")
    print("=" * 62)

    log("步骤 1/4", "准备 Python 运行环境（业务框架 NoneBot）")
    py = ensure_python_env(cfg)

    log("步骤 2/4", "检查 SnowLuma 发行包与目录")
    if (target / "launcher.bat").exists():
        log("完成", f"SnowLuma 已就绪：{target}")
    else:
        pkg = find_package()
        if not pkg:
            log("错误", "没找到 SnowLuma 发行包，且 SnowLuma\\ 目录不存在")
            print()
            print(RELEASE_HINT)
            return 1
        if not extract(pkg, target):
            return 1

    log("步骤 3/4", "写入 OneBot v11 网络配置")
    cfg_file = write_onebot_config(cfg, target)

    log("步骤 4/4", "体检")
    ok = True
    for label, p in (("内核 node.exe", target / "node.exe"),
                     ("hook 组件", target / "native" / "snowluma-win32-x64.dll")):
        if p.exists():
            log("OK", f"{label} 存在")
        else:
            ok = False
            log("错误", f"缺少 {label}：{p}")
    if not py:
        ok = False
        log("错误", "业务框架的 Python 环境未就绪（见上面提示）")

    print()
    print("-" * 62)
    print("后续人工步骤（脚本无法代劳的部分）：")
    print("  1. 确认桌面版 QQ 已登录（SnowLuma 通过 hook 注入正在运行的 QQ.exe）")
    print("  2. 双击『启动-SnowLuma版.bat』，等控制台出现 WebUI 地址")
    print(f"  3. 浏览器打开 http://127.0.0.1:{cfg['snowluma_webui_port']}，用启动日志里的初始账号密码登录")
    print(f"  4. WebUI 里接入 QQ：扫码登录小号 {cfg['snowluma_bot_qq']}（勿与旧栈同号同时在线）")
    print(f"  5. 确认 配置已生效：{cfg_file.name} 里 WS 客户端 = {want_url(cfg)}")
    print("  6. 双击『自检-SnowLuma版.bat』确认全绿")
    print("-" * 62)
    return 0 if ok else 1


def want_url(cfg: dict) -> str:
    return f"ws://127.0.0.1:{cfg['bot_port']}/onebot/v11/ws"


# ---------------------------------------------------------------- Python 环境
def _python_works(exe: str) -> bool:
    try:
        r = subprocess.run([exe, "-c", "import sys;print(sys.version_info[:2])"],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def _has_nonebot(exe: str) -> bool:
    try:
        return subprocess.run([exe, "-c", "import nonebot"], capture_output=True, timeout=30).returncode == 0
    except Exception:
        return False


def find_base_python(cfg: dict) -> str | None:
    """找一个能建 venv 的基础解释器（优先 3.13/3.12/3.11，跳过 WindowsApps 别名）。"""
    cands: list[str] = []
    if cfg.get("python_path"):
        cands.append(str(cfg["python_path"]))

    for launcher in ("py",):
        for ver in ("-3.13", "-3.12", "-3.11"):
            try:
                r = subprocess.run([launcher, ver, "-c", "import sys;print(sys.executable)"],
                                   capture_output=True, timeout=20)
                if r.returncode == 0:
                    cands.append(r.stdout.decode("utf-8", "replace").strip())
            except Exception:
                pass

    for exe_name in ("python", "python3"):
        p = shutil.which(exe_name)
        if p and "WindowsApps" not in p:
            cands.append(p)

    local = Path.home() / "AppData/Local/Programs/Python"
    if local.exists():
        for d in sorted(local.glob("Python3*"), reverse=True):
            cands.append(str(d / "python.exe"))

    wb = Path.home() / ".workbuddy/binaries/python/versions"
    if wb.exists():
        for d in sorted(wb.glob("*/"), reverse=True):
            cands.append(str(d / "python.exe"))

    for c in cands:
        if c and Path(c).exists() and _python_works(c) and str(BASE).lower() not in c.lower():
            return c
    return None


def ensure_python_env(cfg: dict) -> Path | None:
    """确保项目 venv 里有 nonebot；没有就建 venv + 装依赖。返回可用解释器。"""
    venv_py = BASE / "venv" / "Scripts" / "python.exe"
    if venv_py.exists() and _has_nonebot(str(venv_py)):
        log("OK", f"Python 环境就绪：{venv_py}")
        return venv_py

    base = find_base_python(cfg)
    if not base:
        log("错误", "没找到可用的 Python 解释器（需 3.9~3.13）")
        print("   安装后重跑本脚本；或直接在 部署配置.json 里写 python_path。")
        return None

    log("环境", f"使用基础解释器：{base}")
    if not venv_py.exists():
        log("环境", "创建虚拟环境 venv\\ …")
        r = subprocess.run([base, "-m", "venv", str(BASE / "venv")], capture_output=True)
        if r.returncode != 0:
            log("错误", f"创建 venv 失败：{r.stderr.decode('utf-8', 'replace')[:200]}")
            return None

    req = BASE / "qq-group-bot" / "requirements.txt"
    mirrors = ["https://mirrors.aliyun.com/pypi/simple/", "https://pypi.org/simple"]
    for mirror in mirrors:
        log("环境", f"安装依赖（源：{mirror}）…")
        r = subprocess.run([str(venv_py), "-m", "pip", "install", "-r", str(req),
                            "-i", mirror, "--timeout", "60", "--retries", "2"],
                           capture_output=True)
        if r.returncode == 0:
            log("完成", "依赖安装成功")
            return venv_py
        log("警告", f"该源安装失败，换下一个源重试")
    log("错误", "依赖安装失败，请检查网络后重跑")
    return None



if __name__ == "__main__":
    sys.exit(main())
