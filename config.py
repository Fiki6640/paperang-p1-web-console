# ==============================
# Paperang P1 配置文件
# ==============================
import os
import platform

# --- 打印机配置 ---
# 串口名称 (Windows: COM4, 树莓派/Linux: /dev/rfcomm0)
# 自动根据平台选择，可在下方手动覆盖
SERIAL_PORT = "COM4" if platform.system() == "Windows" else "/dev/rfcomm0"

# 波特率 (默认 9600)
SERIAL_BAUDRATE = 9600

# 打印宽度 (点)
PRINTER_WIDTH = 384

# 打印密度 (0-255, 越高越黑越清晰, 推荐 80-120)
PRINT_DENSITY = 255

# 自动重连
AUTO_RECONNECT = True

# 打印机蓝牙 MAC(真实在线探测用,需与 deploy/paperang-rfcomm.service 中一致)
PRINTER_BT_MAC = "AA:BB:CC:DD:EE:FF"   # 改成你的打印机 MAC(设置页可改)

# 蓝牙在线探测间隔(秒),后台线程主动 ping 打印机;设为 0 关闭(状态将显示"未知")
BT_PROBE_INTERVAL = 30

# --- Bark 推送(iOS) ---
# 完整推送地址(含设备 Key,从 Bark App 首页复制)。属于私密凭据,
# 与 HA 令牌一样写进 config_local.py 覆盖,不入仓库。留空 = 不推送
BARK_URL = ""

# 通知分组(Bark App 内按分组归档)
BARK_GROUP = "设备"

# 打印失败通知冷却(秒),避免自动化重复触发时刷屏
BARK_FAIL_COOLDOWN = 300

# --- Web 服务配置 ---
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False

# --- 天气配置 ---
# 天气数据源选择: "caiyun"(彩云天气), "qweather"(和风天气), "openmeteo"(免费)
# 可通过环境变量 WEATHER_PROVIDER 覆盖，无需改代码
WEATHER_PROVIDER = os.environ.get('WEATHER_PROVIDER', 'openmeteo')

# 彩云天气 API Key (免费注册: https://www.caiyunapp.com/)
# 通过环境变量 CAIYUN_API_KEY 提供，避免密钥写进代码仓库
CAIYUN_API_KEY = os.environ.get('CAIYUN_API_KEY', '')

# 和风天气 API Key (免费注册: https://dev.qweather.com/)
WEATHER_API_KEY = ""

# 城市名称或ID (和风天气用)
WEATHER_CITY = "your_city"

# Open-Meteo / 彩云天气 经纬度
WEATHER_LATITUDE = 39.9042    # 示例(北京),改成你的位置
WEATHER_LONGITUDE = 116.4074
WEATHER_LOCATION_NAME = "深圳"

# 天气数据缓存时长（秒）。所有刷新（定时打印/页面访问/预览/手动打印）
# 都共用这份缓存，实际 API 请求频率不会高于 1/缓存时长
WEATHER_CACHE_TTL = int(os.environ.get('WEATHER_CACHE_TTL', '1800'))

# --- 定时任务配置 ---
# 每日打印时间 (24小时制, 如 "08:00")
DAILY_PRINT_TIME = "08:00"

# 是否启用每日天气打印
ENABLE_DAILY_WEATHER = True

# --- 温度曲线配置 (Home Assistant 传感器历史) ---
# 令牌不进仓库:写入同目录 config_local.py(已被 .gitignore 忽略),见文件末尾说明
TEMP_HA_URL = "http://homeassistant.local:8123"
TEMP_HA_TOKEN = ""

# 温度实体 ID
TEMP_ENTITY_ID = "sensor.your_temperature_sensor"

# 每日温度曲线打印时间与开关(0 点后跑即打印"刚结束那天"的曲线)
TEMP_PRINT_TIME = "00:05"
ENABLE_DAILY_TEMP_CHART = True

# --- 本地私有配置覆盖(不入库) ---
# 同目录创建 config_local.py(已被 .gitignore 忽略),其中定义的同名变量会覆盖
# 本文件的值,例如:
#   TEMP_HA_TOKEN = "eyJ..."   # HA 网页端: 用户头像 → 安全 → 长期访问令牌
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
