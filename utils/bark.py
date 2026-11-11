#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bark 推送(iOS Bark App)。

BARK_URL 是完整推送地址(含设备 Key,从 Bark App 首页复制),属于私密凭据,
写在本目录 config_local.py(已被 .gitignore 忽略),不入仓库。
所有发送失败只记日志,绝不影响打印主流程。
"""
import json
import logging
import threading
import time
import urllib.request

_lock = threading.Lock()
_last_fail_push = 0.0


def send(title, body):
    """发一条 Bark 通知,返回是否成功。BARK_URL 未配置时静默跳过返回 False。"""
    import config
    url = (getattr(config, "BARK_URL", "") or "").strip()
    if not url:
        return False
    url = url.rstrip("/")
    payload = {
        "title": title,
        "body": body,
        "group": getattr(config, "BARK_GROUP", ""),
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            # 自定义 UA:Cloudflare 会拦 Python-urllib 默认 UA(403)
            headers={"Content-Type": "application/json; charset=utf-8",
                     "User-Agent": "paperang-printer/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            ok = resp.status == 200
        if ok:
            logging.info("Bark push sent: %s" % title)
        else:
            logging.warning("Bark push HTTP %s" % resp.status)
        return ok
    except Exception as e:
        logging.warning("Bark push failed: %s" % str(e))
        return False


def notify_print_failure(body):
    """打印失败通知,带冷却时间防止自动化重复触发时刷屏。"""
    import config
    global _last_fail_push
    cooldown = getattr(config, "BARK_FAIL_COOLDOWN", 300)
    with _lock:
        now = time.time()
        if now - _last_fail_push < cooldown:
            logging.info("Bark print-failure push suppressed (cooldown %ds)" % cooldown)
            return False
        _last_fail_push = now
    return send("🖨️ 打印失败", body)
