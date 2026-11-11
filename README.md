# Paperang P1 网页打印控制台

基于 Flask + React 的喵喵机 P1 网页控制台，支持文本 / 图片 / 天气 / 温度曲线打印与定时自动打印，可部署在 Windows / 树莓派上通过浏览器远程控制打印机。

## 功能特性

- **文本打印** - 自定义字号、行距，384px 热敏纸实时预览（与实际打印同宽同折行）
- **图片打印** - 拖拽上传，抖动（Atkinson）/ 阈值二值化可选，处理效果实时预览
- **天气打印** - 彩云天气 / 和风天气 / Open-Meteo 三种数据源，Twemoji 图标，含未来 13 小时降水概率与气温折线、高温提醒，网页可预览
- **温度曲线打印** - 从 Home Assistant 拉取传感器历史数据，按热敏头原生 384px 竖版直出（零缩放）
- **定时打印** - 天气 / 温度曲线每日定时自动打印，显示下次执行时间
- **设置页** - 打印机、天气数据源、HA 数据源、定时、Bark 通知全部在线修改，保存即持久化（重启不丢），打印机离线可查电池 / SN / 硬件信息
- **界面** - HeroUI v3 单页应用，暗色模式，桌面 / 移动端自适应，全部打印操作有 loading 与失败重试
- **可靠性** - 断线自动重连（3 次递增），打印失败自动重连并推送 Bark 通知

## 快速开始

### Windows

1. 安装 Python 3.8+，安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 配置 `config.py` 中的串口号（默认 COM4）
3. 启动服务：`python app.py`（或双击 `deploy/run_windows.bat`），浏览器访问 http://localhost:5000
4. 天气等 API Key 首次可在网页设置页直接填写并保存；也可用环境变量（见「配置说明」）

> 前端已预构建（`frontend/dist` 入库），需要改前端时才重新构建，见下文「前端构建」。

### 树莓派 3B

#### 方法一：自动部署脚本

```bash
sudo bash deploy/setup_raspberrypi.sh
```

#### 方法二：手动安装

1. 安装系统依赖：
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-venv bluez bluetooth fonts-wqy-microhei
   sudo apt-get install -y python3-numpy python3-pil   # 用 apt 装 numpy/Pillow 更快
   ```
2. 安装霞鹜文楷字体（推荐，打印效果最佳）：
   ```bash
   sudo mkdir -p /usr/share/fonts/truetype/lxgw
   sudo wget -O /usr/share/fonts/truetype/lxgw/LXGWWenKai-Medium.ttf \
     https://cdn.jsdelivr.net/gh/lxgw/LxgwWenKai/fonts/TTF/LXGWWenKai-Medium.ttf
   sudo fc-cache -fv
   ```
3. 安装 Python 依赖（建议用 piwheels 镜像加速）：
   ```bash
   pip3 install --index-url https://www.piwheels.org/simple/ -r requirements.txt
   ```
4. 配对打印机并绑定串口：
   ```bash
   bluetoothctl   # scan on → pair <MAC> → trust <MAC> → exit
   sudo rfcomm bind /dev/rfcomm0 <MAC> 1
   ```
5. 修改 `config.py` 的 `SERIAL_PORT = "/dev/rfcomm0"`，启动 `python3 app.py`

#### 设置开机自启

```bash
sudo cp deploy/paperang-rfcomm.service deploy/paperang-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now paperang-rfcomm.service paperang-web.service
```

- `paperang-rfcomm.service`：开机执行 `rfcomm bind`（root）
- `paperang-web.service`：Flask Web 服务（pi 用户），依赖 rfcomm

#### 日常运维

```bash
# 仅重启（蓝牙正常时不需要动 paperang-rfcomm）
sudo systemctl restart paperang-web.service

# 状态与实时日志
sudo systemctl status paperang-web.service
journalctl -u paperang-web.service -f     # Ctrl+C 退出

# 仅更新代码并重启（前端 dist 已入库，树莓派无需 Node）
cd /home/pi/paperang-p1 && git pull
sudo systemctl restart paperang-web.service

# 一键更新（同步依赖 + 重启 + 失败自动回滚）
bash deploy/update_raspberrypi.sh
```

## 前端构建（仅改前端时需要）

前端是 Vite + React 19 + HeroUI v3 + Tailwind v4 的单页应用，Flask 托管 `frontend/dist/` 并提供 `/api/v1/*` JSON 接口。

```bash
cd frontend
npm install        # 首次
npm run build      # 产物写入 frontend/dist，随仓库提交
npm run dev        # 本地开发，代理 /api 到本机 Flask（默认 localhost:5000）
```

连树莓派真机调试：`VITE_API_TARGET=http://<pi-ip>:5000 npm run dev`

## 配置说明

**所有配置都可在网页「设置」页在线修改，保存后持久化到 `schedule_state.json`（已 gitignore），重启不丢**；未在页面保存过的项继续跟随 `config.py` / 环境变量默认值。以下仅列默认值：

```python
# 打印机
SERIAL_PORT = "COM4"          # Linux: /dev/rfcomm0
SERIAL_BAUDRATE = 9600
PRINTER_WIDTH = 384
PRINT_DENSITY = 255           # 0-255
PRINTER_BT_MAC = "..."        # 蓝牙 MAC，用于在线探测

# 天气（数据源三选一）
WEATHER_PROVIDER = "caiyun"   # caiyun / qweather / openmeteo（openmeteo 免费无需 Key）
CAIYUN_API_KEY = ""           # https://www.caiyunapp.com/
WEATHER_API_KEY = ""          # 和风: https://dev.qweather.com/
WEATHER_CITY = "your_city"    # 和风城市 ID
WEATHER_LATITUDE = 39.9042    # 经纬度（openmeteo 必填，示例为北京）
WEATHER_LONGITUDE = 116.4074
WEATHER_LOCATION_NAME = "深圳"

# 定时（也受 schedule_state.json 持久化覆盖）
ENABLE_DAILY_WEATHER = True
DAILY_PRINT_TIME = "07:00"
ENABLE_DAILY_TEMP_CHART = True
TEMP_PRINT_TIME = "00:05"

# 温度曲线数据源
TEMP_HA_URL = ""              # HA 地址，如 http://192.168.1.10:8123
TEMP_HA_TOKEN = ""            # HA 长期访问令牌
TEMP_ENTITY_ID = "sensor.xxx"
```

- **凭据不入仓库**：API Key / 令牌可写同目录 `config_local.py`（已 gitignore，同名变量覆盖 config.py），或通过环境变量提供——Windows `setx CAIYUN_API_KEY "..."`；树莓派 `sudo systemctl edit paperang-web.service` 加 `Environment="CAIYUN_API_KEY=..."`
- `WEATHER_PROVIDER`、`CAIYUN_API_KEY`、`WEATHER_CACHE_TTL`（天气缓存秒数，默认 1800）支持环境变量覆盖
- 温度曲线两种渲染：屏幕版（1000×384 抗锯齿，页面预览用）与打印版（384×1000 竖版 1-bit，与打印头逐点对应）

## 项目结构

```
paperang-p1/
├── app.py                   # Flask 主应用（SPA 托管 + 页面路由）
├── paperang_api.py          # /api/v1 JSON 接口
├── config.py                # 配置默认值（config_local.py 覆盖，不入库）
├── printer/                 # 串口通信 / 打印机管理 / 图像处理
├── services/                # weather / temp_chart / scheduler / settings 服务
├── utils/                   # bark 推送 / schedule_state.json 持久化
├── frontend/                # Vite + React 19 + HeroUI v3 + Tailwind v4
│   ├── src/                 #   源码
│   └── dist/                #   构建产物（入库，Flask 直接托管）
├── static/weather_icons/    # 天气图标（Twemoji PNG）
└── deploy/                  # systemd 服务 / 部署与更新脚本 / Windows 启动脚本
```

## 技术栈

- **后端**：Python + Flask、pyserial（蓝牙 SPP/RFCOMM）、Pillow + NumPy、APScheduler
- **前端**：Vite + React 19 + HeroUI v3 + Tailwind CSS v4

## 协议说明

喵喵机 P1 使用经典蓝牙 SPP (RFCOMM) 串口通信，协议帧格式：

```
[0x02] [cmd] [idx] [len:u16] [payload] [crc32:u32] [0x03]
```

- 连接后先发送 `PRT_SET_CRC_KEY (24)` 协商 CRC 密钥
- 图像数据：每行 384 点（48 字节）二值流，1=黑 0=白
- 打印图像生成位流时旋转 180 度，适配打印机出纸方向

## 常见问题

### 打印机连不上？

依次检查：打印机开机 → 蓝牙已配对 → 串口号正确（设备管理器查看）→ 波特率 9600。

### 树莓派打印报 `[Errno 5] Input/output error`？

蓝牙 HCI 异常，重启蓝牙模块：

```bash
sudo hciconfig hci0 down && sleep 3 && sudo hciconfig hci0 up
sudo rfcomm bind rfcomm0 <MAC> 1
```

### 打印乱码 / 中文方框？

- 乱码：确认波特率 9600
- 方框：树莓派安装 LXGW WenKai Medium（见手动安装）或 `sudo apt install fonts-wqy-microhei`；Windows 自带微软雅黑

### Windows 提示 `access denied`？

不要对蓝牙虚拟串口设置 DTR/RTS 信号，本项目已规避，确保使用最新代码。

### 定时打印不工作？

1. 设置页「定时任务」是否开启（显示下次执行时间即为生效）
2. 打印机是否开机且在范围内
3. 天气 / HA 数据源是否配置正确

## 致谢

- [tinyprinter/python-paperang](https://github.com/tinyprinter/python-paperang) — 本项目的前身：打印机协议层（命令常量、通信流程、图像打包）移植自该项目，并以 pyserial 替代其 pybluez 依赖，使其可跨 Windows / Linux 部署。本项目在其基础上增加了 Web 控制台、天气 / 温度曲线打印、定时任务与设置持久化。
- [ihciah/miaomiaoji-tool](https://github.com/ihciah/miaomiaoji-tool) — 喵喵机协议与工具实现的重要参考
- [Finb/Bark](https://github.com/Finb/Bark) — iOS 推送，打印失败通知依赖它
- [LXGW WenKai](https://github.com/lxgw/LxgwWenKai) — 霞鹜文楷字体，热敏打印效果出色
- [HeroUI](https://heroui.com/)、[Twemoji](https://github.com/jdecked/twemoji) — 前端组件库与天气图标

感谢以上项目的作者们。

## License

MIT
