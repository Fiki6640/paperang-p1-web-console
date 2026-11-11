#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置服务:把 Web 页面各设置分组的应用逻辑收拢为纯函数,供新旧两套入口共用。

- 新 JSON 端点(paperang_api.py 的 /api/v1/settings/*)直接调用本模块
- 旧 form 路由(app.py 的 /settings/* 等)改为薄封装,flash 文案走本模块返回值

统一返回: {"ok": bool, "severity": "success"|"error"|"warning"|"info", "message": str}
校验失败时额外带 "field" 字段指明出错项(修复原实现静默吞掉解析错误的问题)。

依赖通过 bind() 注入(app.py 的 init/reinit 函数与运行时实例访问器),
避免本模块反向 import app 造成循环依赖。
"""
import logging

# 注入的依赖(由 app.py 启动时绑定)
_reinit_printer = None      # 打印机连接参数变更后重建 PrinterManager
_reinit_weather = None      # 天气配置变更后重建 WeatherService
_get_printer = None         # () -> printer_manager | None
_get_scheduler = None       # () -> SchedulerService | None
_jobs = {}                  # job_id -> 定时任务函数(重注册用)

WEATHER_PROVIDERS = ('caiyun', 'qweather', 'openmeteo')


def bind(reinit_printer, reinit_weather, get_printer, get_scheduler, jobs):
    """app.py 启动时注入依赖。jobs: {'daily_weather': fn, 'daily_temp_chart': fn}"""
    global _reinit_printer, _reinit_weather, _get_printer, _get_scheduler, _jobs
    _reinit_printer = reinit_printer
    _reinit_weather = reinit_weather
    _get_printer = get_printer
    _get_scheduler = get_scheduler
    _jobs = jobs


def _result(ok, severity, message, **extra):
    out = {"ok": ok, "severity": severity, "message": message}
    out.update(extra)
    return out


def _parse_int(value, field, label):
    try:
        return int(str(value).strip()), None
    except (TypeError, ValueError):
        return None, "参数 %s 必须为整数" % label


# ---------- 打印机 ----------

def apply_printer(data):
    """data: serial_port, baudrate, width, density, bt_mac, auto_reconnect"""
    import config
    from utils import schedule_store

    old_port = config.SERIAL_PORT
    old_baud = config.SERIAL_BAUDRATE
    old_width = config.PRINTER_WIDTH

    port = str(data.get('serial_port') or old_port).strip() or old_port
    # None = 表单/JSON 未携带该字段,与旧 form 路由语义一致:回退 config 现值
    baudrate, err = _parse_int(data.get('baudrate') or old_baud, 'baudrate', '波特率')
    if err:
        return _result(False, 'error', err, field='baudrate')
    width, err = _parse_int(data.get('width') or old_width, 'width', '打印宽度')
    if err:
        return _result(False, 'error', err, field='width')
    density, err = _parse_int(data.get('density') or config.PRINT_DENSITY, 'density', '打印密度')
    if err:
        return _result(False, 'error', err, field='density')
    if not 0 <= density <= 255:
        return _result(False, 'error', '打印密度须在 0-255 之间', field='density')

    bt_mac = str(data.get('bt_mac') or getattr(config, 'PRINTER_BT_MAC', '')).strip()
    auto_reconnect = bool(data.get('auto_reconnect', getattr(config, 'AUTO_RECONNECT', True)))

    config.SERIAL_PORT = port
    config.SERIAL_BAUDRATE = baudrate
    config.PRINTER_WIDTH = width
    config.PRINT_DENSITY = density
    config.PRINTER_BT_MAC = bt_mac
    config.AUTO_RECONNECT = auto_reconnect
    schedule_store.save({
        'SERIAL_PORT': port, 'SERIAL_BAUDRATE': baudrate, 'PRINTER_WIDTH': width,
        'PRINT_DENSITY': density, 'PRINTER_BT_MAC': bt_mac, 'AUTO_RECONNECT': auto_reconnect,
    })

    connection_changed = (port != old_port or baudrate != old_baud or width != old_width)
    pm = _get_printer() if _get_printer else None

    if connection_changed:
        # 串口/波特率/宽度变了:旧连接必须重建,否则新配置到重启都不生效
        if _reinit_printer:
            _reinit_printer()
        pm = _get_printer() if _get_printer else None
        if pm and pm.is_connected():
            return _result(True, 'success', '打印机设置已保存并按新配置重新连接')
        return _result(True, 'warning', '设置已保存，但打印机未连接（将按新配置自动重连）')

    if pm:
        result = pm.set_density(density)
        if result["success"]:
            return _result(True, 'success', '打印机设置已保存')
        return _result(True, 'error', '设置已保存，但密度下发失败: %s' % result["error"])
    return _result(True, 'warning', '打印机未初始化，设置已保存但未应用')


# ---------- 天气 ----------

def apply_weather(data):
    import config
    from utils import schedule_store

    provider = str(data.get('weather_provider') or getattr(config, 'WEATHER_PROVIDER', 'caiyun')).strip()
    if provider not in WEATHER_PROVIDERS:
        return _result(False, 'error', '天气数据源必须是 caiyun / qweather / openmeteo',
                       field='weather_provider')

    # API Key 语义: 字段缺失或空字符串 = 保留原值(页面不回显明文);None = 清除
    caiyun_key = data.get('caiyun_api_key')
    if caiyun_key is None:
        caiyun_key = ''
    elif caiyun_key == '':
        caiyun_key = getattr(config, 'CAIYUN_API_KEY', '')
    weather_key = data.get('weather_api_key')
    if weather_key is None:
        weather_key = ''
    elif weather_key == '':
        weather_key = getattr(config, 'WEATHER_API_KEY', '')

    city = str(data.get('weather_city') or getattr(config, 'WEATHER_CITY', '')).strip()

    def _parse_coord(value, field, label):
        """空 = 保留原值;非空必须可解析为 float,否则报错(不再静默吞掉)"""
        if value is None or str(value).strip() == '':
            return getattr(config, field, None), None
        try:
            return float(str(value).strip()), None
        except (TypeError, ValueError):
            return None, '参数 %s 必须为数字（如 22.5000）' % label

    latitude, err = _parse_coord(data.get('weather_latitude'), 'WEATHER_LATITUDE', '纬度')
    if err:
        return _result(False, 'error', err, field='weather_latitude')
    longitude, err = _parse_coord(data.get('weather_longitude'), 'WEATHER_LONGITUDE', '经度')
    if err:
        return _result(False, 'error', err, field='weather_longitude')

    location_name = str(data.get('weather_location_name')
                        or getattr(config, 'WEATHER_LOCATION_NAME', '') or city).strip()

    config.WEATHER_PROVIDER = provider
    config.CAIYUN_API_KEY = caiyun_key
    config.WEATHER_API_KEY = weather_key
    config.WEATHER_CITY = city
    config.WEATHER_LATITUDE = latitude
    config.WEATHER_LONGITUDE = longitude
    config.WEATHER_LOCATION_NAME = location_name
    schedule_store.save({
        'WEATHER_PROVIDER': provider, 'CAIYUN_API_KEY': caiyun_key,
        'WEATHER_API_KEY': weather_key, 'WEATHER_CITY': city,
        'WEATHER_LATITUDE': latitude, 'WEATHER_LONGITUDE': longitude,
        'WEATHER_LOCATION_NAME': location_name,
    })

    if _reinit_weather:
        _reinit_weather()
    return _result(True, 'success', '天气设置已保存')


# ---------- 温度曲线数据源 ----------

def apply_temp_source(data):
    import config
    from utils import schedule_store

    # 空值 = 保留原值(与旧 form 路由语义一致);None = 清除
    ha_url = data.get('ha_url')
    if ha_url is None:
        ha_url = ''
    elif str(ha_url).strip() == '':
        ha_url = getattr(config, 'TEMP_HA_URL', '')

    token = data.get('ha_token')
    if token is None:
        token = ''
    elif str(token).strip() == '':
        token = getattr(config, 'TEMP_HA_TOKEN', '')  # 留空表示不修改已保存的令牌

    entity = data.get('entity_id')
    if entity is None:
        entity = ''
    elif str(entity).strip() == '':
        entity = getattr(config, 'TEMP_ENTITY_ID', '')

    config.TEMP_HA_URL = str(ha_url).strip()
    config.TEMP_HA_TOKEN = str(token).strip()
    config.TEMP_ENTITY_ID = str(entity).strip()
    schedule_store.save({
        'TEMP_HA_URL': config.TEMP_HA_URL,
        'TEMP_HA_TOKEN': config.TEMP_HA_TOKEN,
        'TEMP_ENTITY_ID': config.TEMP_ENTITY_ID,
    })
    return _result(True, 'success', '温度曲线数据源已保存')


# ---------- 定时任务 ----------

def _validate_time(print_time, label):
    try:
        hour, minute = map(int, str(print_time).split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return hour, minute, None
    except (TypeError, ValueError):
        return None, None, '%s定时打印的时间格式应为 HH:MM（24 小时制）' % label


def _apply_schedule_group(group, enabled, print_time):
    """应用一组定时任务(天气或温度曲线),返回结果 dict"""
    import config
    from utils import schedule_store

    if group == 'weather':
        job_id, enable_key, time_key, label = (
            'daily_weather', 'ENABLE_DAILY_WEATHER', 'DAILY_PRINT_TIME', '天气')
    else:
        job_id, enable_key, time_key, label = (
            'daily_temp_chart', 'ENABLE_DAILY_TEMP_CHART', 'TEMP_PRINT_TIME', '温度曲线')
    func = _jobs.get(job_id)
    scheduler = _get_scheduler() if _get_scheduler else None

    hour, minute, err = _validate_time(print_time, label)
    if err:
        return _result(False, 'error', err, field=group)

    if enabled:
        setattr(config, enable_key, True)
        setattr(config, time_key, print_time)
        if scheduler and func:
            scheduler.add_daily_job(job_id, hour, minute, func)
        schedule_store.save({enable_key: True, time_key: print_time})
        msg = '定时打印已启用，时间: %s' % print_time
        if not scheduler:
            msg += '（调度器未就绪，重启后生效）'
        return _result(True, 'success', msg)
    else:
        setattr(config, enable_key, False)
        if scheduler:
            scheduler.pause_job(job_id)
        schedule_store.save({enable_key: False})
        return _result(True, 'info', '定时打印已暂停')


def apply_schedule(data):
    """data: {'weather': {'enabled': bool, 'print_time': 'HH:MM'}[, 'temp': {...}]}"""
    results = []
    if 'weather' in data:
        g = data['weather']
        results.append(_apply_schedule_group('weather',
                                             bool(g.get('enabled')),
                                             g.get('print_time', '')))
    if 'temp' in data:
        g = data['temp']
        results.append(_apply_schedule_group('temp',
                                             bool(g.get('enabled')),
                                             g.get('print_time', '')))
    if not results:
        return _result(False, 'error', '未提供任何定时任务设置')
    failed = [r for r in results if not r['ok']]
    if failed:
        return failed[0]
    return results[0] if len(results) == 1 else _result(
        True, results[0]['severity'], '；'.join(r['message'] for r in results))


# ---------- 通知 ----------

def apply_notify(data):
    import config
    from utils import schedule_store

    # Bark URL 语义: 缺失/空 = 保留原值;None = 清除(页面上有显式"清除"入口)
    bark_url = data.get('bark_url', '')
    if bark_url is None:
        bark_url = ''
    elif str(bark_url).strip() == '':
        bark_url = getattr(config, 'BARK_URL', '')
    bark_group = data.get('bark_group', '')
    if bark_group is None:
        bark_group = ''
    elif str(bark_group).strip() == '':
        bark_group = getattr(config, 'BARK_GROUP', '')

    config.BARK_URL = str(bark_url).strip()
    config.BARK_GROUP = str(bark_group).strip()
    schedule_store.save({'BARK_URL': config.BARK_URL, 'BARK_GROUP': config.BARK_GROUP})
    if config.BARK_URL:
        return _result(True, 'success', '通知设置已保存（打印失败将推送到 Bark）')
    return _result(True, 'info', '通知设置已保存（未配置 Bark URL，失败仅记日志）')


# ---------- 快照 ----------

def _job_snapshot(scheduler, job_id, fallback_time):
    status = scheduler.get_job_status(job_id) if scheduler else None
    if status:
        return {"enabled": status["enabled"],
                "print_time": "%02d:%02d" % (status["hour"], status["minute"]),
                "next_run_time": status["next_run_time"]}
    import config
    enabled_key = 'ENABLE_DAILY_WEATHER' if job_id == 'daily_weather' else 'ENABLE_DAILY_TEMP_CHART'
    return {"enabled": bool(getattr(config, enabled_key, False)),
            "print_time": fallback_time,
            "next_run_time": None}


def snapshot():
    """GET /api/v1/settings 用:全部分组当前值(敏感项只回 has_* 布尔)"""
    import config
    scheduler = _get_scheduler() if _get_scheduler else None
    return {
        "printer": {
            "serial_port": config.SERIAL_PORT,
            "baudrate": config.SERIAL_BAUDRATE,
            "width": config.PRINTER_WIDTH,
            "density": config.PRINT_DENSITY,
            "bt_mac": getattr(config, 'PRINTER_BT_MAC', ''),
            "auto_reconnect": bool(getattr(config, 'AUTO_RECONNECT', True)),
        },
        "weather": {
            "provider": getattr(config, 'WEATHER_PROVIDER', 'caiyun'),
            "has_caiyun_key": bool(getattr(config, 'CAIYUN_API_KEY', '')),
            "has_weather_key": bool(getattr(config, 'WEATHER_API_KEY', '')),
            "city": getattr(config, 'WEATHER_CITY', ''),
            "latitude": getattr(config, 'WEATHER_LATITUDE', None),
            "longitude": getattr(config, 'WEATHER_LONGITUDE', None),
            "location_name": getattr(config, 'WEATHER_LOCATION_NAME', ''),
        },
        "temp": {
            "ha_url": getattr(config, 'TEMP_HA_URL', ''),
            "has_token": bool(getattr(config, 'TEMP_HA_TOKEN', '')),
            "entity_id": getattr(config, 'TEMP_ENTITY_ID', ''),
        },
        "schedule": {
            "weather": _job_snapshot(scheduler, 'daily_weather',
                                     getattr(config, 'DAILY_PRINT_TIME', '')),
            "temp": _job_snapshot(scheduler, 'daily_temp_chart',
                                  getattr(config, 'TEMP_PRINT_TIME', '')),
        },
        "notify": {
            "has_bark_url": bool(getattr(config, 'BARK_URL', '')),
            "bark_group": getattr(config, 'BARK_GROUP', ''),
        },
    }


def _parse_device_reply(data):
    """解析 queryXxx() 的返回 (原始帧, [Info包...]) → {命令名: payload bytes}"""
    packets = data[1] if isinstance(data, tuple) and len(data) > 1 else []
    out = {}
    for p in packets:
        try:
            from printer.const import BtCommandByte
            name = BtCommandByte.findCommand(p.command)
        except Exception:
            name = "CMD_%s" % p.command
        out[name] = p.payload
    return out


def _device_summary(reply):
    """把三类查询的应答转成人读友好的摘要;解析不出就给简短 hex,不再透传原始帧"""
    if reply is None:
        return None
    try:
        packets = _parse_device_reply(reply)
        # 电池: PRT_SENT_BAT_STATUS 载荷首字节 = 电量百分比
        for name in ("PRT_SENT_BAT_STATUS", "PRT_GET_BAT_STATUS"):
            payload = packets.get(name)
            if payload:
                return {"battery": "%d%%" % payload[0]}
        # SN: PRT_SENT_SN 载荷为 ASCII
        for name in ("PRT_SENT_SN", "PRT_GET_SN"):
            payload = packets.get(name)
            if payload:
                return {"sn": payload.decode("ascii", "replace").strip()}
        # 硬件信息: 无固定结构,显示可读字符 + hex
        for name in ("PRT_SENT_HW_INFO", "PRT_GET_HW_INFO"):
            payload = packets.get(name)
            if payload:
                text = payload.decode("ascii", "replace")
                printable = "".join(c if 32 <= ord(c) < 127 else "." for c in text)
                return {"hardware": "%s (hex: %s)" % (printable, payload.hex()[:40])}
        # 兜底: 给命令名,不给原始帧
        return {"raw_commands": ", ".join(packets.keys()) or "无应答"}
    except Exception as e:
        logging.warning("device reply parse failed: %s" % e)
        return None


def _jsonable(v):
    """把串口查询的原始返回转成可 JSON 序列化的结构。
    电池/SN/硬件响应里常含 bytes,直接 jsonify 会 500(json.dumps 不认 bytes)。"""
    if isinstance(v, (bytes, bytearray)):
        text = v.decode('utf-8', 'replace').strip()
        return text if text else v.hex()
    if isinstance(v, dict):
        keys = [k.decode('utf-8', 'replace') if isinstance(k, (bytes, bytearray)) else str(k)
                for k in v.keys()]
        return {k: _jsonable(x) for k, x in zip(keys, v.values())}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def device_info():
    """设备信息(电池/SN/硬件),打印机离线或查询失败时对应项为 null"""
    pm = _get_printer() if _get_printer else None
    connected = bool(pm and pm.is_connected())
    info = {"connected": connected, "battery": None, "sn": None, "hardware": None}

    def _safe(fn):
        try:
            result = fn()
            if result and result.get("success"):
                return _device_summary(result.get("data"))
            return None
        except Exception as e:
            logging.warning("device query failed: %s" % e)
            return None

    # 只在串口确实连通时才发查询;离线时每次查询都会触发 3 轮重连(约 9s),
    # 页面刷新一次就卡死一次,直接返回空值
    if connected:
        info["battery"] = _safe(pm.get_battery_status)
        info["sn"] = _safe(pm.get_sn)
        info["hardware"] = _safe(pm.get_hardware_info)
    return info
