#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天气服务模块
支持: 彩云天气 / 和风天气 / Open-Meteo
"""
import requests
from datetime import datetime


# 中文星期映射
WEEKDAY_CN = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

# 彩云天气 skycon 字符串 -> 中文描述
CAIYUN_SKYCON = {
    'CLEAR_DAY': '晴',
    'CLEAR_NIGHT': '晴',
    'PARTLY_CLOUDY_DAY': '多云',
    'PARTLY_CLOUDY_NIGHT': '多云',
    'CLOUDY': '阴',
    'LIGHT_HAZE': '轻度雾霾',
    'MODERATE_HAZE': '中度雾霾',
    'HEAVY_HAZE': '重度雾霾',
    'LIGHT_RAIN': '小雨',
    'MODERATE_RAIN': '中雨',
    'HEAVY_RAIN': '大雨',
    'STORM_RAIN': '暴雨',
    'FOG': '雾',
    'LIGHT_SNOW': '小雪',
    'MODERATE_SNOW': '中雪',
    'HEAVY_SNOW': '大雪',
    'STORM_SNOW': '暴雪',
    'DUST': '浮尘',
    'SAND': '沙尘',
    'WIND': '大风',
}

# 天气描述 -> 图标类型映射（用 PIL 绘制几何图形）
WEATHER_ICON_TYPES = {
    '晴': 'sun',
    '多云': 'partly_cloudy',
    '阴': 'cloud',
    '小雨': 'rain_light',
    '中雨': 'rain',
    '大雨': 'rain_heavy',
    '暴雨': 'rain_storm',
    '阵雨': 'rain_light',
    '中阵雨': 'rain',
    '大阵雨': 'rain_heavy',
    '毛毛雨': 'rain_light',
    '冻雨': 'rain',
    '雷阵雨': 'thunder',
    '小雪': 'snow_light',
    '中雪': 'snow',
    '大雪': 'snow_heavy',
    '暴雪': 'snow_storm',
    '阵雪': 'snow_light',
    '雾': 'fog',
    '霾': 'fog',
    '沙': 'dust',
    '尘': 'dust',
    '风': 'wind',
}


def get_weather_icon_type(text):
    """根据天气描述返回图标类型"""
    if not text:
        return ''
    if text in WEATHER_ICON_TYPES:
        return WEATHER_ICON_TYPES[text]
    for key in sorted(WEATHER_ICON_TYPES.keys(), key=len, reverse=True):
        if key in text:
            return WEATHER_ICON_TYPES[key]
    return ''


def draw_weather_icon(img, x, y, size, icon_type):
    """加载 PNG 天气图标并粘贴到图像上"""
    try:
        from PIL import Image as _Image
        import os as _os

        # 图标目录：相对于项目根目录
        icon_dirs = [
            _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'static', 'weather_icons'),
            '/home/pi/paperang-p1/static/weather_icons',
        ]
        icon_path = None
        for d in icon_dirs:
            p = _os.path.join(d, f'{icon_type}.png')
            if _os.path.exists(p):
                icon_path = p
                break

        if not icon_path:
            return  # 找不到图标就跳过

        # 加载图标并缩放
        icon = _Image.open(icon_path).convert('L')
        if icon.size[0] != size:
            icon = icon.resize((size, size), _Image.LANCZOS)

        # 粘贴到目标图像（L 模式直接 paste）
        img.paste(icon, (x, y))
    except Exception as e:
        print(f"加载天气图标失败: {e}")


def _draw_cloud(draw, cx, cy, r, line_w):
    """绘制云形（多个圆组合）"""  # 保留兼容
    pass

# Open-Meteo weather code -> 中文描述
OPENMETEO_CODES = {
    0: '晴',
    1: '大部分晴朗',
    2: '多云',
    3: '阴',
    45: '雾',
    48: '雾凇',
    51: '小毛毛雨',
    53: '毛毛雨',
    55: '大毛毛雨',
    56: '冻毛毛雨',
    57: '冻毛毛雨',
    61: '小雨',
    63: '中雨',
    65: '大雨',
    66: '冻雨',
    67: '大雨',
    71: '小雪',
    73: '中雪',
    75: '大雪',
    77: '小雪',
    80: '阵雨',
    81: '中阵雨',
    82: '大阵雨',
    85: '阵雪',
    86: '大雪',
    95: '雷阵雨',
    96: '雷阵雨伴冰雹',
    99: '强雷阵雨',
}


class WeatherService:
    def __init__(self, api_key='', city='', width=384,
                 latitude=None, longitude=None, location_name='',
                 provider='caiyun', caiyun_key='', cache_ttl=1800):
        self.api_key = api_key
        self.city = city
        self.width = width
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name or city
        self.provider = provider
        self.caiyun_key = caiyun_key
        self._session = requests.Session()
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = cache_ttl  # 缓存时长（秒），限制实际 API 请求频率

    def get_weather_now(self):
        import time
        now = time.time()
        # 缓存有效期内直接返回缓存数据
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache
        # 获取新数据
        if self.provider == 'caiyun' and self.caiyun_key:
            data = self._get_caiyun_weather()
        elif self.api_key:
            data = self._get_qweather()
        else:
            data = self._get_open_meteo()
        # 成功获取则更新缓存
        if data:
            self._cache = data
            self._cache_time = now
        return data

    def _get_caiyun_weather(self):
        """彩云天气 API"""
        try:
            lng = self.longitude
            lat = self.latitude
            url = f"https://api.caiyunapp.com/v2.6/{self.caiyun_key}/{lng},{lat}/weather"
            params = {
                'dailysteps': 3,
                'hourlysteps': 13,
            }
            resp = self._session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if data.get('status') != 'ok':
                print(f"彩云天气返回错误: {data.get('status')}")
                return None

            result = data.get('result', {})
            realtime = result.get('realtime', {})
            daily = result.get('daily', {})

            # 实时数据
            temp = realtime.get('temperature', 0)
            skycon = realtime.get('skycon', '')
            text = CAIYUN_SKYCON.get(skycon, '未知')
            humidity_val = realtime.get('humidity', 0)
            # humidity 是 0-1 小数，转成百分比
            humidity = str(int(round(float(humidity_val) * 100))) if humidity_val else '--'
            wind = realtime.get('wind', {})
            wind_dir = wind.get('direction', 0)
            wind_speed = wind.get('speed', 0)
            feels_like = realtime.get('apparent_temperature', temp)

            # 风向转换
            directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
            dir_idx = round(wind_dir / 45) % 8
            wind_dir_text = directions[dir_idx]

            # 风力等级转换 (km/h -> 风级)
            def kmh_to_level(kmh):
                if kmh < 1: return 0
                elif kmh < 6: return 1
                elif kmh < 12: return 2
                elif kmh < 20: return 3
                elif kmh < 29: return 4
                elif kmh < 39: return 5
                elif kmh < 50: return 6
                elif kmh < 62: return 7
                elif kmh < 75: return 8
                else: return 9

            wind_level = kmh_to_level(wind_speed)

            # 每日数据
            daily_temp = daily.get('temperature', [{}])
            temp_max = daily_temp[0].get('max') if daily_temp else None
            temp_min = daily_temp[0].get('min') if daily_temp else None

            # 日出日落在 astro 字段
            astro_list = daily.get('astro', [{}])
            sunrise = ''
            sunset = ''
            if astro_list:
                sunrise = astro_list[0].get('sunrise', {}).get('time', '')
                sunset = astro_list[0].get('sunset', {}).get('time', '')

            # 逐小时降水概率（hourly.precipitation[].probability，0-1 小数）
            hourly = result.get('hourly', {})
            precip_hourly = hourly.get('precipitation', [])
            precip_probs = []
            for item in precip_hourly:
                prob = item.get('probability')
                if prob is None:
                    continue
                # 提取小时（datetime 字段格式：YYYY-MM-DDTHH:MM...）
                dt_str = item.get('datetime', '')
                hour_str = ''
                if 'T' in dt_str:
                    hour_str = dt_str.split('T')[1][:2]
                precip_probs.append({
                    'hour': hour_str,
                    'prob': int(round(float(prob) * 100)),  # 0-100 整数
                })

            # 逐小时气温（hourly.temperature[].value，单位 ℃）
            temp_hourly = hourly.get('temperature', [])
            hourly_temps = []
            for item in temp_hourly:
                val = item.get('value')
                if val is None:
                    continue
                # 提取小时（datetime 字段格式：YYYY-MM-DDTHH:MM...）
                dt_str = item.get('datetime', '')
                hour_str = ''
                if 'T' in dt_str:
                    hour_str = dt_str.split('T')[1][:2]
                hourly_temps.append({
                    'hour': hour_str,
                    'temp': float(val),
                })

            return {
                'city': self.location_name,
                'temp': str(round(float(temp), 1)),
                'temp_min': str(round(float(temp_min), 1)) if temp_min is not None else None,
                'temp_max': str(round(float(temp_max), 1)) if temp_max is not None else None,
                'text': text,
                'feelsLike': str(round(float(feels_like), 1)),
                'humidity': humidity,
                'windDir': wind_dir_text,
                'windScale': str(wind_level),
                'icon': self._weather_icon(text),
                'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'sunrise': sunrise,
                'sunset': sunset,
                'precip_probs': precip_probs,
                'hourly_temps': hourly_temps,
            }
        except Exception as e:
            print(f"彩云天气获取失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_qweather(self):
        """和风天气 API"""
        try:
            url = f"https://devapi.qweather.com/v7/weather/now"
            params = {
                'location': self.city,
                'key': self.api_key,
            }
            resp = self._session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get('code') != '200':
                print(f"和风天气返回错误码: {data.get('code')}")
                return None
            
            now_data = data.get('now', {})
            return {
                'city': self.location_name,
                'temp': now_data.get('temp', '--'),
                'text': now_data.get('text', '--'),
                'feelsLike': now_data.get('feelsLike', '--'),
                'humidity': now_data.get('humidity', '--'),
                'windDir': now_data.get('windDir', '--'),
                'windScale': now_data.get('windScale', '--'),
                'icon': self._weather_icon(now_data.get('text', '')),
                'updateTime': now_data.get('updateTime', ''),
            }
        except Exception as e:
            print(f"和风天气获取失败: {e}")
            return None

    def _get_open_meteo(self):
        """Open-Meteo 免费 API"""
        try:
            url = f"https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'current': ['temperature_2m', 'relative_humidity_2m', 'apparent_temperature',
                           'wind_speed_10m', 'wind_direction_10m', 'weather_code'],
                'daily': ['temperature_2m_max', 'temperature_2m_min', 'weather_code',
                         'sunrise', 'sunset'],
                'timezone': 'auto',
                'forecast_days': 3,
            }
            resp = self._session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            current = data.get('current', {})
            daily = data.get('daily', {})
            
            temp = current.get('temperature_2m', '--')
            feels_like = current.get('apparent_temperature', '--')
            humidity = current.get('relative_humidity_2m', '--')
            weather_code = current.get('weather_code', 0)
            weather_text = OPENMETEO_CODES.get(weather_code, '未知')
            
            wind_speed = current.get('wind_speed_10m', 0)
            wind_dir = current.get('wind_direction_10m', 0)
            
            # 风向转换
            directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
            dir_idx = round(wind_dir / 45) % 8
            wind_dir_text = directions[dir_idx]
            
            # 风力等级
            def kmh_to_level(kmh):
                if kmh < 1: return 0
                elif kmh < 6: return 1
                elif kmh < 12: return 2
                elif kmh < 20: return 3
                elif kmh < 29: return 4
                elif kmh < 39: return 5
                elif kmh < 50: return 6
                elif kmh < 62: return 7
                elif kmh < 75: return 8
                else: return 9
            
            wind_level = kmh_to_level(wind_speed)
            
            temp_max = daily.get('temperature_2m_max', [None])[0]
            temp_min = daily.get('temperature_2m_min', [None])[0]
            sunrise = daily.get('sunrise', [None])[0]
            sunset = daily.get('sunset', [None])[0]
            
            return {
                'city': self.location_name,
                'temp': str(round(temp, 1)) if temp != '--' else '--',
                'temp_min': str(round(temp_min, 1)) if temp_min is not None else None,
                'temp_max': str(round(temp_max, 1)) if temp_max is not None else None,
                'text': weather_text,
                'feelsLike': str(round(feels_like, 1)) if feels_like != '--' else '--',
                'humidity': str(humidity),
                'windDir': wind_dir_text,
                'windScale': str(wind_level),
                'icon': self._weather_icon(weather_text),
                'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'sunrise': sunrise[11:16] if sunrise else '',
                'sunset': sunset[11:16] if sunset else '',
            }
        except Exception as e:
            print(f"Open-Meteo 获取失败: {e}")
            return None

    def _weather_icon(self, text):
        text = str(text)
        if '晴' in text:
            return '☀️'
        elif '多云' in text:
            return '⛅'
        elif '阴' in text:
            return '☁️'
        elif '雨' in text and '雷' in text:
            return '⛈️'
        elif '雨' in text:
            return '🌧️'
        elif '雪' in text:
            return '❄️'
        elif '雾' in text or '霾' in text:
            return '🌫️'
        else:
            return '🌤️'

    def generate_weather_image(self, weather_data):
        if not weather_data:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont
            import os

            width = self.width

            # 字体加载（优先霞鹜文楷，保持本地调试与树莓派一致）
            _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            font_paths = [
                os.path.join(_project_root, 'fonts', 'LXGWWenKai-Medium.ttf'),
                "/usr/share/fonts/truetype/lxgw/LXGWWenKai-Medium.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            font_path = None
            for fp in font_paths:
                if os.path.exists(fp):
                    font_path = fp
                    break

            def make_font(size):
                if font_path:
                    return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            # 各级字号
            font_title = make_font(22)    # 标题
            font_big = make_font(48)      # 大气温
            font_med = make_font(20)      # 天气描述
            font_small = make_font(20)    # 详情
            font_tiny = make_font(18)     # 底部备注
            font_axis = make_font(16)     # 折线图坐标轴

            # 数据
            city = weather_data.get('city', '未知')
            temp = weather_data.get('temp', '--')
            text = weather_data.get('text', '--')
            humidity = weather_data.get('humidity', '--')
            wind_dir = weather_data.get('windDir', '--')
            wind_scale = weather_data.get('windScale', '--')
            feels_like = weather_data.get('feelsLike', '--')
            update_time = weather_data.get('updateTime', '')
            temp_max = weather_data.get('temp_max')
            temp_min = weather_data.get('temp_min')
            # 高温提醒：当天最高气温 > 35°C 时触发
            hot_alert = False
            try:
                hot_alert = bool(temp_max) and float(temp_max) > 35
            except (TypeError, ValueError):
                hot_alert = False
            sunrise = weather_data.get('sunrise', '')
            sunset = weather_data.get('sunset', '')
            precip_probs = weather_data.get('precip_probs', []) or []
            hourly_temps = weather_data.get('hourly_temps', []) or []

            now = datetime.now()
            weekday_cn = WEEKDAY_CN[now.weekday()]
            date_str = now.strftime(f'%Y-%m-%d {weekday_cn}')

            # 计算高度
            h = 0
            h += 10 + 24 + 8          # 标题区
            h += 8 + 60 + 8           # 大气温区
            h += 4 + 22 + 8           # 天气描述
            h += 6 + 2 + 8            # 分隔线
            if temp_max and temp_min:
                # 高温提醒时最高温字体放大，行高随之增大
                h += (32 if hot_alert else 20) + 4
            # 降水概率块（分隔线 + 标题 + 折线图）
            if precip_probs:
                h += 6 + 2 + 8        # 分隔线
                h += 18 + 4           # 块标题
                h += 10               # 下移 10px
                h += 90               # 折线图区域（含坐标轴，缩小 10px）
                h += 8                # 块底部间距
            # 逐时气温块（分隔线 + 标题 + 折线图）
            if hourly_temps:
                h += 6 + 2 + 8        # 分隔线
                h += 18 + 4           # 块标题
                h += 10               # 下移 10px
                h += 90               # 折线图区域
                h += 8                # 块底部间距
            h += 6 + 2 + 8            # 分隔线
            h += 18 + 6 + 18 + 6 + 18  # 体感/湿度/风
            if sunrise and sunset:
                h += 6 + 18
            h += 8 + 2 + 8            # 分隔线
            h += 16 + 10              # 更新时间
            total_height = h

            img = Image.new('L', (width, total_height), color=255)
            draw = ImageDraw.Draw(img)

            x_margin = 10
            y = 8

            # 1. 顶部标题：日期 城市
            draw.text((x_margin, y), f"{date_str}  {city}", fill=0, font=font_title)
            y += 24 + 8

            # 2. 核心区：天气图标 + 天气描述 + 大气温
            icon_size = 48
            icon_x = x_margin
            icon_type = get_weather_icon_type(text)
            if icon_type:
                draw_weather_icon(img, icon_x, y, icon_size, icon_type)
            # 天气描述放在图标右侧
            desc_x = icon_x + icon_size + 8
            draw.text((desc_x, y - 7) , text, fill=0, font=font_big)
            # 测量描述宽度以确定温度位置
            try:
                desc_w = draw.textlength(text, font=font_big)
            except Exception:
                desc_w = len(text) * 48
            # 温度放在描述右侧
            temp_str = f"{temp}°C"
            temp_x = desc_x + desc_w + 16
            draw.text((temp_x, y - 6), temp_str, fill=0, font=font_big)
            y += 60 + 8

            # 3. 最高/最低温（高温提醒时最高温放大 50% 并加三个感叹号）
            if temp_max and temp_min:
                if hot_alert:
                    font_hot = make_font(int(font_med.size * 1.5))   # 20 → 30，放大 50%
                    hot_text = f"↑ {temp_max}°C"
                    draw.text((x_margin, y), hot_text, fill=0, font=font_hot)
                    hot_w = draw.textlength(hot_text, font=font_hot)
                    draw.text((x_margin + hot_w + 16, y), f"↓ {temp_min}°C", fill=0, font=font_med)
                    y += 32 + 4
                else:
                    draw.text((x_margin, y), f"↑ {temp_max}°C    ↓ {temp_min}°C", fill=0, font=font_med)
                    y += 22 + 4

            # 3.5 降水概率块（分隔线 + 标题 + 折线图）
            if precip_probs:
                # 分隔线
                y += 6
                draw.line([(x_margin, y), (width - x_margin, y)], fill=0, width=1)
                y += 2 + 8
                # 块标题
                draw.text((x_margin, y), "逐时降水概率", fill=0, font=font_small)
                y += 18 + 4
                # 下移 10px
                y += 10
                # 折线图区域
                chart_left = x_margin + 32       # 左侧留 32px 给 Y 轴标签
                chart_right = width - x_margin
                chart_top = y
                chart_bottom = y + 54           # 绘图区高度 54（原 64）
                chart_w = chart_right - chart_left
                chart_h = chart_bottom - chart_top
                # Y 轴：0%, 50%, 100%
                for pct, label in [(0, '0%'), (50, '50'), (100, '100')]:
                    yy = chart_bottom - int(chart_h * pct / 100)
                    draw.text((x_margin, yy - 8), label, fill=0, font=font_axis)
                    # 横向网格线（虚线效果，用短破折号）
                    if pct != 0 and pct != 100:
                        for gx in range(chart_left, chart_right, 4):
                            draw.point([(gx, yy)], fill=0)
                # X 轴底线
                draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=0, width=1)
                # Y 轴
                draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=0, width=1)
                # 计算各点坐标
                n = len(precip_probs)
                if n >= 2:
                    pts = []
                    for idx, item in enumerate(precip_probs):
                        px = chart_left + int(chart_w * idx / (n - 1))
                        prob = item.get("prob", 0) / 100
                        py = chart_bottom - int(chart_h * prob / 100)
                        pts.append((px, py))
                    # 绘制折线
                    for i in range(len(pts) - 1):
                        draw.line([pts[i], pts[i + 1]], fill=0, width=2)
                    # 绘制数据点（小实心圆）
                    for px, py in pts:
                        draw.ellipse([(px - 2, py - 2), (px + 2, py + 2)], fill=0)
                    # X 轴标签：每隔几个显示一次（避免拥挤）
                    label_step = max(1, n // 6)
                    for idx, item in enumerate(precip_probs):
                        if idx % label_step != 0 and idx != n - 1:
                            continue
                        px = chart_left + int(chart_w * idx / (n - 1))
                        hour = item.get('hour', '')
                        # 标签居中对齐
                        try:
                            tw = draw.textlength(hour, font=font_axis)
                        except Exception:
                            tw = len(hour) * 8
                        draw.text((px - tw / 2, chart_bottom + 4), hour, fill=0, font=font_axis)
                y = chart_bottom + 18 + 8

            # 3.6 逐时气温块（分隔线 + 标题 + 折线图，样式同降水曲线）
            if hourly_temps:
                # 分隔线
                y += 6
                draw.line([(x_margin, y), (width - x_margin, y)], fill=0, width=1)
                y += 2 + 8
                # 块标题
                draw.text((x_margin, y), "逐时气温", fill=0, font=font_small)
                y += 18 + 4
                # 下移 10px
                y += 10
                # 折线图区域
                chart_left = x_margin + 32       # 左侧留 32px 给 Y 轴标签
                chart_right = width - x_margin
                chart_top = y
                chart_bottom = y + 54           # 绘图区高度 54
                chart_w = chart_right - chart_left
                chart_h = chart_bottom - chart_top
                # Y 轴范围：顶部为当天最高气温，底部为当天最低气温
                temps = [float(item.get('temp', 0)) for item in hourly_temps]
                try:
                    t_top = float(temp_max) if temp_max else max(temps)
                except (TypeError, ValueError):
                    t_top = max(temps)
                t_bot = min(temps)
                try:
                    if temp_min:
                        t_bot = min(t_bot, float(temp_min))
                except (TypeError, ValueError):
                    pass
                if t_top <= t_bot:
                    t_bot = t_top - 10
                # Y 轴标签：底部最低温 / 中间均值 / 顶部最高温
                for frac, label in [
                    (0.0, str(int(round(t_bot)))),
                    (0.5, str(int(round((t_top + t_bot) / 2)))),
                    (1.0, str(int(round(t_top)))),
                ]:
                    yy = chart_bottom - int(chart_h * frac)
                    draw.text((x_margin, yy - 8), label, fill=0, font=font_axis)
                    # 横向网格线（虚线效果，用短破折号）
                    if frac not in (0.0, 1.0):
                        for gx in range(chart_left, chart_right, 4):
                            draw.point([(gx, yy)], fill=0)
                # X 轴底线 + Y 轴
                draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=0, width=1)
                draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=0, width=1)
                # 计算各点坐标
                n = len(hourly_temps)
                if n >= 2:
                    pts = []
                    for idx, item in enumerate(hourly_temps):
                        px = chart_left + int(chart_w * idx / (n - 1))
                        # 温度映射到 Y 轴，clamp 防止超出绘图区
                        frac = (float(item.get('temp', 0)) - t_bot) / (t_top - t_bot)
                        frac = max(0.0, min(1.0, frac))
                        py = chart_bottom - int(chart_h * frac)
                        pts.append((px, py))
                    # 绘制折线
                    for i in range(len(pts) - 1):
                        draw.line([pts[i], pts[i + 1]], fill=0, width=2)
                    # 绘制数据点（小实心圆）
                    for px, py in pts:
                        draw.ellipse([(px - 2, py - 2), (px + 2, py + 2)], fill=0)
                    # X 轴标签：每隔几个显示一次（避免拥挤）
                    label_step = max(1, n // 6)
                    for idx, item in enumerate(hourly_temps):
                        if idx % label_step != 0 and idx != n - 1:
                            continue
                        px = chart_left + int(chart_w * idx / (n - 1))
                        hour = item.get('hour', '')
                        # 标签居中对齐
                        try:
                            tw = draw.textlength(hour, font=font_axis)
                        except Exception:
                            tw = len(hour) * 8
                        draw.text((px - tw / 2, chart_bottom + 4), hour, fill=0, font=font_axis)
                y = chart_bottom + 18 + 8

            # 4. 分隔线
            y += 6
            draw.line([(x_margin, y), (width - x_margin, y)], fill=0, width=1)
            y += 2 + 8

            # 5. 详情区：体感 / 湿度 / 风
            draw.text((x_margin, y), f"体感 {feels_like}°C", fill=0, font=font_small)
            y += 18 + 6
            draw.text((x_margin, y), f"湿度 {humidity}%", fill=0, font=font_small)
            y += 18 + 6
            draw.text((x_margin, y), f"{wind_dir}风 {wind_scale}级", fill=0, font=font_small)
            y += 18 + 6
            if sunrise and sunset:
                draw.text((x_margin, y), f"日出 {sunrise}   日落 {sunset}", fill=0, font=font_small)
                y += 18 + 6

            # 6. 分隔线
            y += 8
            draw.line([(x_margin, y), (width - x_margin, y)], fill=0, width=1)
            y += 2 + 8

            # 7. 底部更新时间
            draw.text((x_margin, y), f"更新: {update_time}", fill=0, font=font_tiny)

            return img
        except Exception as e:
            print(f"生成天气图片失败: {e}")
            import traceback
            traceback.print_exc()
            return None
