#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行时设置持久化(原名"定时任务状态持久化",现覆盖 Web 页面全部可改配置)
Web 页面上保存的设置原先只改 config 模块内存属性,重启即回 config.py 默认值
(定时打印表现为"暂停后一重启又变回开启",天气/打印机设置则整体丢失)。
落到本 JSON 文件后,启动时覆盖 config 默认值,重启保持用户最后一次在页面上的设置。

安全: 文件固定在仓库根目录且已被 .gitignore 忽略;API Key / HA 令牌 / Bark URL
等敏感项也落在这里,与 config_local.py 的"凭据不入仓库"约定一致。
"""
import json
import logging
import os

# 状态文件固定在仓库根目录(与 app.py 同级),可用环境变量改到别处
# (如根文件系统只读的部署需要挪到可写目录)
STATE_PATH = os.environ.get(
    'SCHEDULE_STATE_FILE',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'schedule_state.json'))

# 允许持久化的配置键(白名单)。定时的 4 个键是最早一批,其余为设置页各组;
# 敏感项(API Key/令牌/Bark URL)是有意加入的,依赖 .gitignore 保证不入仓库
ALLOWED_KEYS = (
    # 定时任务
    'ENABLE_DAILY_WEATHER', 'DAILY_PRINT_TIME',
    'ENABLE_DAILY_TEMP_CHART', 'TEMP_PRINT_TIME',
    # 打印机
    'SERIAL_PORT', 'SERIAL_BAUDRATE', 'PRINTER_WIDTH', 'PRINT_DENSITY',
    'PRINTER_BT_MAC', 'AUTO_RECONNECT',
    # 天气
    'WEATHER_PROVIDER', 'CAIYUN_API_KEY', 'WEATHER_API_KEY', 'WEATHER_CITY',
    'WEATHER_LATITUDE', 'WEATHER_LONGITUDE', 'WEATHER_LOCATION_NAME',
    # 温度曲线数据源
    'TEMP_HA_URL', 'TEMP_HA_TOKEN', 'TEMP_ENTITY_ID',
    # 通知
    'BARK_URL', 'BARK_GROUP',
)


def load():
    """读取持久化状态;文件不存在/损坏返回空 dict(视为全部用 config.py 默认值)"""
    try:
        with open(STATE_PATH, encoding='utf-8') as f:
            state = json.load(f)
        if isinstance(state, dict):
            return {k: state[k] for k in ALLOWED_KEYS if k in state}
        logging.warning("Schedule state file has wrong format, ignoring: %s" % STATE_PATH)
        return {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logging.warning("Schedule state file unreadable, using config defaults: %s" % e)
        return {}


def save(updates):
    """合并写入(读-改-写,临时文件原子替换);updates 只接受白名单内的键。

    值类型支持 str/int/float/bool(JSON 原生),读取后 setattr 到 config 模块
    需保持类型,调用方负责传入正确类型。
    """
    state = load()
    state.update({k: updates[k] for k in ALLOWED_KEYS if k in updates})
    tmp = STATE_PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_PATH)
    except OSError as e:
        logging.error("Failed to save schedule state to %s: %s" % (STATE_PATH, e))


def apply_to_config(config):
    """把持久化状态覆盖到 config 模块(启动时调用一次),返回应用的键值"""
    state = load()
    for key, value in state.items():
        setattr(config, key, value)
    if state:
        logging.info("Applied persisted schedule state: %s keys" % len(state))
    return state
