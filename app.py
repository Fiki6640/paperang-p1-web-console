#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paperang P1 Web 打印控制台
Flask 主应用入口
"""
import os
import sys
import secrets
import logging
import tempfile
from flask import (Flask, request, redirect, url_for, flash, jsonify,
                   send_file, send_from_directory)
from io import BytesIO

import config
from printer import PrinterManager, bt_link
from services.weather_service import WeatherService
from services.scheduler_service import SchedulerService
from services import temp_chart as temp_chart_service
from services import settings_service
from utils import schedule_store

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 前端 SPA 构建产物(Vite → frontend/dist);不存在时页面路由给出构建提示
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = os.path.join(BASE_DIR, 'frontend', 'dist')

app = Flask(__name__)
# 优先用环境变量固定密钥（多进程/重启后 session 不失效），否则每次启动随机生成
app.secret_key = os.environ.get('APP_SECRET_KEY') or secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

printer_manager = None
weather_service = None
scheduler_service = None


from paperang_api import register as register_api
register_api(app, lambda: printer_manager, lambda: weather_service, lambda: reconnect_printer())


def init_printer():
    global printer_manager
    printer_manager = None
    try:
        pm = PrinterManager(
            port=config.SERIAL_PORT,
            baudrate=config.SERIAL_BAUDRATE,
            width=config.PRINTER_WIDTH,
            density=config.PRINT_DENSITY,
            auto_reconnect=config.AUTO_RECONNECT
        )
        printer_manager = pm
        if pm.is_connected():
            logging.info("Printer initialized: %s" % config.SERIAL_PORT)
        else:
            logging.warning("Printer manager created but not connected: %s" % config.SERIAL_PORT)
    except Exception as e:
        logging.error("Failed to initialize printer: %s" % str(e))
        printer_manager = None


def reconnect_printer():
    global printer_manager
    try:
        if printer_manager:
            printer_manager.disconnect()
            printer_manager = None

        import time
        time.sleep(3)

        # 检查端口是否可用
        import serial as pyserial
        try:
            test_ser = pyserial.Serial(port=config.SERIAL_PORT, baudrate=config.SERIAL_BAUDRATE, timeout=1)
            test_ser.close()
            time.sleep(0.5)
        except Exception as e:
            logging.error("Port %s not available: %s" % (config.SERIAL_PORT, str(e)))
            return False

        pm = PrinterManager(
            port=config.SERIAL_PORT,
            baudrate=config.SERIAL_BAUDRATE,
            width=config.PRINTER_WIDTH,
            density=config.PRINT_DENSITY,
            auto_reconnect=config.AUTO_RECONNECT
        )
        printer_manager = pm
        logging.info("Printer reconnected: %s" % config.SERIAL_PORT)
        return pm.is_connected()
    except Exception as e:
        logging.error("Failed to reconnect printer: %s" % str(e))
        return False


def restart_printer_manager():
    """设置变更(串口/波特率/宽度)后重建打印机管理器;先断开旧连接避免串口被占用"""
    global printer_manager
    if printer_manager:
        try:
            printer_manager.disconnect()
        except Exception as e:
            logging.warning("Failed to disconnect old printer manager: %s" % str(e))
    init_printer()


def _serve_spa():
    """返回 SPA 入口页;前端未构建时给出可读提示"""
    index_path = os.path.join(FRONTEND_DIST, 'index.html')
    if os.path.isfile(index_path):
        return send_file(index_path)
    return ("前端尚未构建：请在开发机上进入 frontend/ 执行 npm install && npm run build，"
            "或参考 README.md 的前端构建说明。"), 503


@app.route('/assets/<path:filename>')
def frontend_assets(filename):
    return send_from_directory(os.path.join(FRONTEND_DIST, 'assets'), filename)


@app.route('/<path:path>')
def spa_catch_all(path):
    """未匹配任何 API/页面路由的路径:dist 里有对应文件则返回,否则回退 SPA 入口
    (客户端路由负责展示 404)。send_from_directory 自带路径穿越防护。"""
    if path and os.path.isfile(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    return _serve_spa()


def init_weather_service():
    global weather_service
    weather_service = WeatherService(
        api_key=config.WEATHER_API_KEY,
        city=config.WEATHER_CITY,
        width=config.PRINTER_WIDTH,
        latitude=getattr(config, "WEATHER_LATITUDE", None),
        longitude=getattr(config, "WEATHER_LONGITUDE", None),
        location_name=getattr(config, "WEATHER_LOCATION_NAME", config.WEATHER_CITY),
        provider=getattr(config, "WEATHER_PROVIDER", "caiyun"),
        caiyun_key=getattr(config, "CAIYUN_API_KEY", ""),
        cache_ttl=getattr(config, "WEATHER_CACHE_TTL", 1800),
    )
    logging.info("Weather service initialized (provider=%s)" % getattr(config, "WEATHER_PROVIDER", "caiyun"))


def init_scheduler_service():
    global scheduler_service
    scheduler_service = SchedulerService()
    if config.ENABLE_DAILY_WEATHER and config.DAILY_PRINT_TIME:
        try:
            hour, minute = map(int, config.DAILY_PRINT_TIME.split(':'))
            scheduler_service.add_daily_job(
                'daily_weather',
                hour,
                minute,
                print_daily_weather
            )
            logging.info("Daily weather job scheduled at %s" % config.DAILY_PRINT_TIME)
        except Exception as e:
            logging.error("Failed to schedule daily weather: %s" % str(e))
    if getattr(config, 'ENABLE_DAILY_TEMP_CHART', False) and getattr(config, 'TEMP_PRINT_TIME', ''):
        try:
            hour, minute = map(int, config.TEMP_PRINT_TIME.split(':'))
            scheduler_service.add_daily_job(
                'daily_temp_chart',
                hour,
                minute,
                print_daily_temp_chart
            )
            logging.info("Daily temp chart job scheduled at %s" % config.TEMP_PRINT_TIME)
        except Exception as e:
            logging.error("Failed to schedule daily temp chart: %s" % str(e))


def print_daily_weather():
    if not printer_manager or not weather_service:
        logging.warning("Printer or weather service not available")
        return
    try:
        weather_data = weather_service.get_weather_now()
        if weather_data:
            weather_img = weather_service.generate_weather_image(weather_data)
            if weather_img:
                result = printer_manager.print_image_from_image(weather_img)
                if result["success"]:
                    msg = "Daily weather printed successfully"
                    if result["attempts"] > 1:
                        msg += " (auto-reconnected %d times)" % (result["attempts"] - 1)
                    logging.info(msg)
                else:
                    logging.error("Daily weather print failed: %s" % result["error"])
    except Exception as e:
        logging.error("Failed to print daily weather: %s" % str(e))


def print_daily_temp_chart():
    """定时任务: 拉 HA 历史生成温度曲线并打印(原生 384px 竖版,零缩放)"""
    if not printer_manager:
        logging.warning("Printer not available for temp chart job")
        return
    if not getattr(config, 'TEMP_HA_URL', '') or not getattr(config, 'TEMP_HA_TOKEN', ''):
        logging.warning("Temp chart job skipped: TEMP_HA_URL / TEMP_HA_TOKEN not configured")
        return
    try:
        day = temp_chart_service.fetch_day(
            config.TEMP_HA_URL, config.TEMP_HA_TOKEN,
            getattr(config, 'TEMP_ENTITY_ID', temp_chart_service.DEFAULT_ENTITY),
        )
        img = temp_chart_service.render_print(day, native_width=config.PRINTER_WIDTH)
        result = printer_manager.print_image_from_image(img)
        vals = [v for _, v in day['samples']]
        if result["success"]:
            msg = "Daily temp chart printed: max %.1f min %.1f avg %.1f, %d samples" % (
                max(vals), min(vals), sum(vals) / len(vals), len(vals))
            if result["attempts"] > 1:
                msg += " (auto-reconnected %d times)" % (result["attempts"] - 1)
            logging.info(msg)
        else:
            logging.error("Daily temp chart print failed: %s" % result["error"])
    except Exception as e:
        logging.error("Failed to print daily temp chart: %s" % str(e))


# 设置服务依赖注入(必须在各 init/print_daily_* 定义之后)
settings_service.bind(
    reinit_printer=restart_printer_manager,
    reinit_weather=init_weather_service,
    get_printer=lambda: printer_manager,
    get_scheduler=lambda: scheduler_service,
    jobs={'daily_weather': print_daily_weather,
          'daily_temp_chart': print_daily_temp_chart},
)


@app.context_processor
def inject_printer_status():
    status = {
        "connected": False,
        "port": config.SERIAL_PORT,
        "baudrate": config.SERIAL_BAUDRATE,
        "width": config.PRINTER_WIDTH,
        "bt": bt_link.get_state(),
    }
    if printer_manager:
        status.update(printer_manager.get_status())
    return dict(printer_status=status)


# ---------- SPA 页面路由(前端未构建时 _serve_spa 给出提示) ----------

@app.route('/')
def index():
    return _serve_spa()


@app.route('/text-print', methods=['GET', 'POST'])
def text_print():
    if request.method == 'POST':
        # 旧 form 入口(现在浏览器走 SPA + /api/v1/print/text);保留兼容
        text = request.form.get('text', '')
        font_size = int(request.form.get('font_size', 20))
        line_spacing = int(request.form.get('line_spacing', 8))

        if not text.strip():
            flash('请输入要打印的内容', 'warning')
        elif not printer_manager:
            flash('打印机未初始化', 'error')
        else:
            result = printer_manager.print_text(text, font_size=font_size, line_spacing=line_spacing)
            if result["success"]:
                msg = '打印任务已发送！'
                if result["attempts"] > 1:
                    msg += ' (自动重连 %d 次)' % (result["attempts"] - 1)
                flash(msg, 'success')
            else:
                flash('打印失败: %s' % result["error"], 'error')
        return redirect(url_for('text_print'))

    return _serve_spa()


@app.route('/image-print', methods=['GET', 'POST'])
def image_print():
    if request.method == 'POST':
        # 旧 form 入口(现在浏览器走 SPA + /api/v1/print/image);保留兼容
        if 'image' not in request.files:
            flash('请选择图片文件', 'warning')
        elif not printer_manager:
            flash('打印机未初始化', 'error')
        else:
            file = request.files['image']
            method = request.form.get('method', 'dither')

            if file.filename == '':
                flash('请选择图片文件', 'warning')
            else:
                try:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    file.save(tmp.name)
                    tmp.close()

                    result = printer_manager.print_image_file(tmp.name, method=method)
                    os.unlink(tmp.name)

                    if result["success"]:
                        msg = '图片打印任务已发送！'
                        if result["attempts"] > 1:
                            msg += ' (自动重连 %d 次)' % (result["attempts"] - 1)
                        flash(msg, 'success')
                    else:
                        flash('打印失败: %s' % result["error"], 'error')
                except Exception as e:
                    flash('处理失败: %s' % str(e), 'error')
        return redirect(url_for('image_print'))

    return _serve_spa()


@app.route('/weather')
def weather():
    return _serve_spa()


@app.route('/weather/preview')
def weather_preview():
    if not weather_service:
        return "天气服务未初始化", 500
    weather_data = weather_service.get_weather_now()
    if not weather_data:
        return "获取天气数据失败", 500
    img = weather_service.generate_weather_image(weather_data)
    if not img:
        return "生成天气图片失败", 500
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')


@app.route('/weather/print', methods=['POST'])
def weather_print():
    if not printer_manager:
        flash('打印机未初始化', 'error')
    elif not weather_service:
        flash('天气服务未初始化', 'warning')
    else:
        try:
            weather_data = weather_service.get_weather_now()
            if weather_data:
                weather_img = weather_service.generate_weather_image(weather_data)
                if weather_img:
                    result = printer_manager.print_image_from_image(weather_img)
                    if result["success"]:
                        msg = '天气打印任务已发送！'
                        if result["attempts"] > 1:
                            msg += ' (自动重连 %d 次)' % (result["attempts"] - 1)
                        flash(msg, 'success')
                    else:
                        flash('打印失败: %s' % result["error"], 'error')
                else:
                    flash('生成天气图片失败', 'error')
            else:
                flash('获取天气数据失败', 'error')
        except Exception as e:
            flash('处理失败: %s' % str(e), 'error')
    
    return redirect(url_for('weather'))


@app.route('/weather/schedule', methods=['POST'])
def weather_schedule():
    resp = settings_service.apply_schedule({
        'weather': {
            'enabled': 'enabled' in request.form,
            'print_time': request.form.get('print_time', config.DAILY_PRINT_TIME),
        },
    })
    flash(resp['message'], resp['severity'])
    return redirect(url_for('weather'))


@app.route('/temp-chart')
def temp_chart_page():
    return _serve_spa()


@app.route('/temp-chart/preview')
def temp_chart_preview():
    if not getattr(config, 'TEMP_HA_URL', '') or not getattr(config, 'TEMP_HA_TOKEN', ''):
        return "未配置 TEMP_HA_URL / TEMP_HA_TOKEN", 500
    try:
        days_ago = int(request.args.get('days_ago', 1))
    except ValueError:
        days_ago = 1
    try:
        day = temp_chart_service.fetch_day(
            config.TEMP_HA_URL, config.TEMP_HA_TOKEN,
            getattr(config, 'TEMP_ENTITY_ID', temp_chart_service.DEFAULT_ENTITY),
            days_ago=days_ago,
        )
        img = temp_chart_service.render_dashboard(day)
    except Exception as e:
        return "生成失败: %s" % str(e), 500
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    resp = send_file(img_io, mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-store'  # 预览随数据实时变化,禁用缓存
    return resp


@app.route('/temp-chart/print', methods=['POST'])
def temp_chart_print():
    if not printer_manager:
        flash('打印机未初始化', 'error')
    elif not getattr(config, 'TEMP_HA_URL', '') or not getattr(config, 'TEMP_HA_TOKEN', ''):
        flash('请先在下方填写 HA 地址与令牌', 'warning')
    else:
        try:
            day = temp_chart_service.fetch_day(
                config.TEMP_HA_URL, config.TEMP_HA_TOKEN,
                getattr(config, 'TEMP_ENTITY_ID', temp_chart_service.DEFAULT_ENTITY),
            )
            img = temp_chart_service.render_print(day, native_width=config.PRINTER_WIDTH)
            result = printer_manager.print_image_from_image(img)
            if result["success"]:
                msg = '温度曲线打印任务已发送！(原生 384px 竖版)'
                if result["attempts"] > 1:
                    msg += ' (自动重连 %d 次)' % (result["attempts"] - 1)
                flash(msg, 'success')
            else:
                flash('打印失败: %s' % result["error"], 'error')
        except Exception as e:
            flash('处理失败: %s' % str(e), 'error')

    return redirect(url_for('temp_chart_page'))


@app.route('/temp-chart/schedule', methods=['POST'])
def temp_chart_schedule():
    resp = settings_service.apply_schedule({
        'temp': {
            'enabled': 'enabled' in request.form,
            'print_time': request.form.get('print_time',
                                           getattr(config, 'TEMP_PRINT_TIME', '00:05')),
        },
    })
    flash(resp['message'], resp['severity'])
    return redirect(url_for('temp_chart_page'))


@app.route('/temp-chart/settings', methods=['POST'])
def temp_chart_settings():
    resp = settings_service.apply_temp_source({
        'ha_url': request.form.get('ha_url'),
        'ha_token': request.form.get('ha_token'),
        'entity_id': request.form.get('entity_id'),
    })
    flash(resp['message'], resp['severity'])
    return redirect(url_for('temp_chart_page'))


@app.route('/settings')
def settings():
    return _serve_spa()


@app.route('/settings/printer', methods=['POST'])
def save_printer_settings():
    resp = settings_service.apply_printer({
        'serial_port': request.form.get('serial_port'),
        'baudrate': request.form.get('baudrate'),
        'width': request.form.get('width'),
        'density': request.form.get('density'),
    })
    flash(resp['message'], resp['severity'])
    return redirect(url_for('settings'))


@app.route('/settings/weather', methods=['POST'])
def save_weather_settings():
    resp = settings_service.apply_weather({
        'weather_provider': request.form.get('weather_provider'),
        'caiyun_api_key': request.form.get('caiyun_api_key'),
        'weather_api_key': request.form.get('weather_api_key'),
        'weather_city': request.form.get('weather_city'),
        'weather_latitude': request.form.get('weather_latitude'),
        'weather_longitude': request.form.get('weather_longitude'),
        'weather_location_name': request.form.get('weather_location_name'),
    })
    flash(resp['message'], resp['severity'])
    return redirect(url_for('settings'))


@app.route('/settings/schedule', methods=['POST'])
def save_schedule_settings():
    resp = settings_service.apply_schedule({
        'weather': {
            'enabled': 'enable_daily_weather' in request.form,
            'print_time': request.form.get('daily_print_time', config.DAILY_PRINT_TIME),
        },
    })
    flash(resp['message'], resp['severity'])
    return redirect(url_for('settings'))


@app.route('/api/self-test', methods=['POST'])
def api_self_test():
    if not printer_manager:
        flash('打印机未初始化', 'error')
    else:
        result = printer_manager.print_self_test()
        if result["success"]:
            msg = '自检页已发送'
            if result["attempts"] > 1:
                msg += ' (自动重连 %d 次)' % (result["attempts"] - 1)
            flash(msg, 'success')
        else:
            flash('打印失败: %s' % result["error"], 'error')
    return redirect(url_for('index'))


@app.route('/api/feed', methods=['POST'])
def api_feed():
    if not printer_manager:
        flash('打印机未初始化', 'error')
    else:
        result = printer_manager.feed_line(100)
        if result["success"]:
            msg = '走纸完成'
            if result["attempts"] > 1:
                msg += ' (自动重连 %d 次)' % (result["attempts"] - 1)
            flash(msg, 'success')
        else:
            flash('走纸失败: %s' % result["error"], 'error')
    return redirect(url_for('index'))


@app.route('/api/reconnect', methods=['POST'])
def api_reconnect():
    success = reconnect_printer()
    # 串口节点能打开≠蓝牙在线,用一次实时探测给出真实结论
    state, _name, detail = bt_link.check_once(config.PRINTER_BT_MAC)
    if state == "online" and success:
        flash('重新连接成功！', 'success')
    elif state == "online":
        flash('打印机蓝牙在线，但串口连接失败，请查看服务日志', 'warning')
    elif success:
        flash('打印机蓝牙不在线(%s)，请检查打印机电源' % detail, 'error')
    else:
        flash('连接失败，请检查打印机状态', 'error')
    return redirect(url_for('index'))


@app.route('/api/status', methods=['POST'])
def api_status():
    bt = bt_link.get_state()
    if printer_manager and printer_manager.is_connected():
        if bt["state"] == "offline":
            flash('串口已打开，但打印机蓝牙不在线(%s)，请检查打印机电源' % bt["detail"], 'warning')
        else:
            try:
                printer_manager.get_status()
                flash('打印机状态: 已连接 (%s)' % config.SERIAL_PORT, 'info')
            except Exception as e:
                flash('查询失败: %s' % str(e), 'error')
    else:
        flash('打印机未连接', 'warning')
    return redirect(url_for('index'))


def main():
    # 页面保存过的设置(定时/打印机/天气/HA/通知)先覆盖 config.py 默认值,
    # 再初始化各服务——否则天气/打印机服务会先拿占位默认值跑起来
    schedule_store.apply_to_config(config)
    init_printer()
    init_weather_service()
    init_scheduler_service()

    if getattr(config, 'BT_PROBE_INTERVAL', 0) > 0:
        bt_link.start_background_probe(
            config.PRINTER_BT_MAC, interval=config.BT_PROBE_INTERVAL)

    logging.info("Starting Paperang P1 Web Server on %s:%d" % (config.FLASK_HOST, config.FLASK_PORT))
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )


if __name__ == '__main__':
    main()
