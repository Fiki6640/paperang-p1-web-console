#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实蓝牙链路探测。

rfcomm 节点存在 ≠ 蓝牙在线：`rfcomm bind` 只创建 tty 节点，RFCOMM 链路要在
打开串口时才建立，打印机断电时 open 照样成功、写入才报 Errno 5——所以
"串口已打开"不能作为打印机在线的依据。

这里用 `hcitool name <MAC>` 做真实探测：远程取名需要与打印机建立 ACL 连接，
打印机不在线时会立即失败。探测由后台线程按固定间隔刷新，结果缓存供状态
接口/页面零延迟读取（探测最坏要等页面超时几秒，不能放在请求路径里同步做）。
"""
import logging
import shutil
import subprocess
import threading
import time

_lock = threading.Lock()
# {"state": "online"|"offline"|"unknown", "name": str|None,
#  "detail": str, "checked_at": float(epoch)}
_state = {"state": "unknown", "name": None, "detail": "尚未探测", "checked_at": 0.0}
_thread_started = False


def check_once(mac, timeout=8):
    """主动探测一次，返回 (state, name, detail)。不读写缓存。"""
    hcitool = shutil.which("hcitool")
    if not hcitool:
        return "unknown", None, "hcitool 不可用(非 Linux 或未装 bluez)"
    try:
        proc = subprocess.run(
            [hcitool, "name", mac],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "offline", None, "探测超时(设备无应答)"
    if proc.returncode == 0 and proc.stdout.strip():
        return "online", proc.stdout.strip(), "hcitool name 应答正常"
    raw = (proc.stderr or proc.stdout).strip() or "设备无应答"
    if "host is down" in raw.lower():
        raw = "设备无应答(Host is down)"
    return "offline", None, raw


def start_background_probe(mac, interval=30):
    """启动后台探测线程（幂等）。无 hcitool 的环境(如 Windows 开发机)保持 unknown。"""
    global _thread_started
    with _lock:
        if _thread_started:
            return
        _thread_started = True

    def _loop():
        while True:
            try:
                state, name, detail = check_once(mac)
                with _lock:
                    _state.update(state=state, name=name, detail=detail,
                                  checked_at=time.time())
                if state != "online":
                    logging.info("BT probe: %s offline (%s)" % (mac, detail))
            except Exception as e:
                logging.warning("BT probe error: %s" % str(e))
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True, name="bt-probe").start()
    logging.info("BT link probe thread started (mac=%s, interval=%ds)" % (mac, interval))


def get_state():
    """返回缓存状态的副本，不阻塞、不触发探测。"""
    with _lock:
        return dict(_state)
