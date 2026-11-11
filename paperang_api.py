#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paperang P1 REST JSON API 蓝图
==============================
供 Home Assistant 等外部系统调用的 REST 接口（前缀 /api/v1）。

集成方法（在原项目 app.py 中添加两行）：

    from paperang_api import register as register_api
    register_api(app, lambda: printer_manager, lambda: weather_service, reconnect_printer)

建议放在 init_printer() / init_weather_service() 定义之后、main() 之前。
"""
import base64
import tempfile
import os
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file
from PIL import Image

from printer import bt_link
from services import settings_service

api_bp = Blueprint('paperang_api', __name__, url_prefix='/api/v1')

# 依赖访问器（由 register() 注入，请求时动态取值，确保拿到最新实例）
_get_printer = None
_get_weather = None
_reconnect = None


def register(app, get_printer, get_weather, reconnect_fn):
    """注册 REST API 蓝图。

    参数：
        app           Flask 应用实例
        get_printer   无参 callable，返回当前 printer_manager（或 None）
        get_weather   无参 callable，返回当前 weather_service（或 None）
        reconnect_fn  无参 callable，返回 bool 表示重连是否成功
    """
    global _get_printer, _get_weather, _reconnect
    _get_printer = get_printer
    _get_weather = get_weather
    _reconnect = reconnect_fn
    app.register_blueprint(api_bp)


# ---------- 通用工具 ----------

def _printer():
    pm = _get_printer() if _get_printer else None
    return pm


def _need_printer():
    """返回 (printer_manager, error_response)。error_response 为 None 表示可用。"""
    pm = _printer()
    if pm is None:
        return None, (jsonify({"success": False, "error": "打印机未初始化"}), 503)
    return pm, None


def _result(resp, ok_code=200, fail_code=500):
    code = ok_code if resp.get("success") else fail_code
    return jsonify(resp), code


# ---------- 接口实现 ----------

@api_bp.route('/health')
def health():
    return jsonify({"ok": True, "service": "paperang-p1"})


@api_bp.route('/status')
def status():
    pm = _printer()
    if pm:
        resp = pm.get_status()
        resp["density"] = pm.density
        return jsonify(resp)
    # 打印机未初始化时仍返回基本配置，便于 HA 侧识别服务在线
    from flask import current_app
    try:
        import config
        return jsonify({
            "connected": False,
            "port": config.SERIAL_PORT,
            "baudrate": config.SERIAL_BAUDRATE,
            "width": config.PRINTER_WIDTH,
            "density": config.PRINT_DENSITY,
            "bt": bt_link.get_state(),
        })
    except Exception:
        return jsonify({"connected": False, "bt": bt_link.get_state()})


@api_bp.route('/info')
def info():
    pm, err = _need_printer()
    if err:
        return err
    return jsonify({
        "connected": pm.is_connected(),
        "port": pm.port,
        "baudrate": pm.baudrate,
        "width": pm.width,
        "density": pm.density,
        "auto_reconnect": pm.auto_reconnect,
        "bt": bt_link.get_state(),
    })


@api_bp.route('/print/text', methods=['POST'])
def print_text():
    pm, err = _need_printer()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    if not str(text).strip():
        return jsonify({"success": False, "error": "text 不能为空"}), 400
    try:
        font_size = int(data.get('font_size', 24))
        line_spacing = int(data.get('line_spacing', 8))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "font_size/line_spacing 必须为整数"}), 400
    return _result(pm.print_text(text, font_size=font_size, line_spacing=line_spacing))


@api_bp.route('/print/image', methods=['POST'])
def print_image():
    pm, err = _need_printer()
    if err:
        return err
    try:
        ctype = (request.content_type or '').lower()
        if ctype.startswith('application/json'):
            data = request.get_json(silent=True) or {}
            image_b64 = data.get('image', '')
            if not image_b64:
                return jsonify({"success": False, "error": "image(base64) 不能为空"}), 400
            img_bytes = base64.b64decode(image_b64)
            img = Image.open(BytesIO(img_bytes))
            # print_image_from_image 内部固定 threshold 二值化
            result = pm.print_image_from_image(img, method='threshold')
            return _result(result)
        elif 'image' in request.files:
            file = request.files['image']
            method = request.form.get('method', 'dither')
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            file.save(tmp.name)
            tmp.close()
            try:
                result = pm.print_image_file(tmp.name, method=method)
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass
            return _result(result)
        else:
            return jsonify({"success": False, "error": "未提供图片（JSON base64 或 multipart 均可）"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route('/print/weather', methods=['POST'])
def print_weather():
    pm, err = _need_printer()
    if err:
        return err
    ws = _get_weather() if _get_weather else None
    if ws is None:
        return jsonify({"success": False, "error": "天气服务未初始化"}), 503
    try:
        weather_data = ws.get_weather_now()
        if not weather_data:
            return jsonify({"success": False, "error": "获取天气数据失败"}), 502
        weather_img = ws.generate_weather_image(weather_data)
        if not weather_img:
            return jsonify({"success": False, "error": "生成天气图片失败"}), 500
        return _result(pm.print_image_from_image(weather_img))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route('/weather/preview')
def weather_preview():
    ws = _get_weather() if _get_weather else None
    if ws is None:
        return jsonify({"error": "天气服务未初始化"}), 500
    weather_data = ws.get_weather_now()
    if not weather_data:
        return jsonify({"error": "获取天气数据失败"}), 502
    img = ws.generate_weather_image(weather_data)
    if not img:
        return jsonify({"error": "生成天气图片失败"}), 500
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@api_bp.route('/weather/data')
def weather_data():
    ws = _get_weather() if _get_weather else None
    if ws is None:
        return jsonify({"error": "天气服务未初始化"}), 500
    data = ws.get_weather_now()
    if not data:
        return jsonify({"error": "获取天气数据失败"}), 502
    return jsonify(data)


@api_bp.route('/feed', methods=['POST'])
def feed():
    pm, err = _need_printer()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        length = int(data.get('length', 100))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "length 必须为整数"}), 400
    return _result(pm.feed_line(length))


@api_bp.route('/self-test', methods=['POST'])
def self_test():
    pm, err = _need_printer()
    if err:
        return err
    return _result(pm.print_self_test())


@api_bp.route('/reconnect', methods=['POST'])
def reconnect():
    success = bool(_reconnect()) if _reconnect else False
    return jsonify({"success": success}), (200 if success else 500)


@api_bp.route('/density', methods=['POST'])
def set_density():
    pm, err = _need_printer()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    density = data.get('density')
    if density is None:
        return jsonify({"success": False, "error": "density 不能为空"}), 400
    try:
        density = int(density)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "density 必须为整数"}), 400
    return _result(pm.set_density(density))


# ---------- 设置(JSON 端点,业务逻辑与旧 form 路由共用 settings_service) ----------

def _settings_result(resp):
    """settings_service 的返回值转 HTTP: 校验失败 400,成功 200"""
    if not resp.get("ok"):
        return jsonify({"success": False, "error": resp["message"],
                        "field": resp.get("field")}), 400
    return jsonify({"success": True, "message": resp["message"],
                    "severity": resp["severity"]})


@api_bp.route('/settings')
def get_settings():
    return jsonify(settings_service.snapshot())


@api_bp.route('/settings/printer', methods=['POST'])
def save_settings_printer():
    data = request.get_json(silent=True) or {}
    return _settings_result(settings_service.apply_printer(data))


@api_bp.route('/settings/weather', methods=['POST'])
def save_settings_weather():
    data = request.get_json(silent=True) or {}
    return _settings_result(settings_service.apply_weather(data))


@api_bp.route('/settings/temp', methods=['POST'])
def save_settings_temp():
    data = request.get_json(silent=True) or {}
    return _settings_result(settings_service.apply_temp_source(data))


@api_bp.route('/settings/schedule', methods=['POST'])
def save_settings_schedule():
    data = request.get_json(silent=True) or {}
    return _settings_result(settings_service.apply_schedule(data))


@api_bp.route('/settings/notify', methods=['POST'])
def save_settings_notify():
    data = request.get_json(silent=True) or {}
    return _settings_result(settings_service.apply_notify(data))


@api_bp.route('/device-info')
def device_info():
    return jsonify(settings_service.device_info())


def _error_placeholder_png(message, width=1000, height=384):
    """预览生成失败时返回的占位图(带错误说明,页面/控制台都不会出现 500)"""
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    text = message[:60]
    # 居中多行:按 40 字符粗略折行
    lines = [text[i:i + 40] for i in range(0, len(text), 40)] or ['预览生成失败']
    y = height // 2 - 14 * len(lines)
    for line in lines:
        draw.text((width // 2 - len(line) * 5, y), line, fill=(120, 120, 120))
        y += 28
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io


@api_bp.route('/temp-chart/preview')
def temp_chart_preview():
    import config
    if not getattr(config, 'TEMP_HA_URL', '') or not getattr(config, 'TEMP_HA_TOKEN', ''):
        resp = send_file(
            _error_placeholder_png('未配置 HA 地址 / 令牌，请到设置页填写'),
            mimetype='image/png')
        resp.headers['Cache-Control'] = 'no-store'
        return resp
    try:
        days_ago = int(request.args.get('days_ago', 1))
    except ValueError:
        days_ago = 1
    try:
        from services import temp_chart as temp_chart_service
        day = temp_chart_service.fetch_day(
            config.TEMP_HA_URL, config.TEMP_HA_TOKEN,
            getattr(config, 'TEMP_ENTITY_ID', temp_chart_service.DEFAULT_ENTITY),
            days_ago=days_ago,
        )
        img = temp_chart_service.render_dashboard(day)
    except Exception as e:
        resp = send_file(
            _error_placeholder_png('预览生成失败: %s' % str(e)),
            mimetype='image/png')
        resp.headers['Cache-Control'] = 'no-store'
        return resp
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    resp = send_file(img_io, mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@api_bp.route('/temp-chart/print', methods=['POST'])
def temp_chart_print():
    """SPA 用的 JSON 打印端点;旧 form 路由 POST /temp-chart/print 继续保留给 HA"""
    pm, err = _need_printer()
    if err:
        return err
    import config
    if not getattr(config, 'TEMP_HA_URL', '') or not getattr(config, 'TEMP_HA_TOKEN', ''):
        return jsonify({"success": False, "error": "请先在设置中填写 HA 地址与令牌"}), 400
    data = request.get_json(silent=True) or {}
    try:
        days_ago = int(data.get('days_ago', 1))
    except (TypeError, ValueError):
        days_ago = 1
    try:
        from services import temp_chart as temp_chart_service
        day = temp_chart_service.fetch_day(
            config.TEMP_HA_URL, config.TEMP_HA_TOKEN,
            getattr(config, 'TEMP_ENTITY_ID', temp_chart_service.DEFAULT_ENTITY),
            days_ago=days_ago,
        )
        img = temp_chart_service.render_print(day, native_width=config.PRINTER_WIDTH)
        result = pm.print_image_from_image(img)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    return _result(result)
