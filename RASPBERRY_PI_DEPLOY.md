# 树莓派 3B 部署指南

## 一、环境准备

### 1.1 系统要求
- Raspberry Pi OS (Bookworm/Bullseye) - 推荐使用 Lite 版
- Python 3.8+
- 蓝牙适配器（树莓派3B内置）

### 1.2 系统更新
```bash
sudo apt update
sudo apt upgrade -y
```

### 1.3 安装系统依赖
```bash
sudo apt install -y python3-pip python3-pil python3-numpy bluetooth bluez bluez-tools rfkill
```

## 二、蓝牙配置

### 2.1 启用蓝牙
```bash
sudo rfkill unblock bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
```

### 2.2 配对 Paperang P1

1. 打开打印机电源
2. 扫描附近蓝牙设备：
```bash
bluetoothctl
power on
agent on
default-agent
scan on
```

3. 找到名为 `MiaoMiaoJi` 或 `Paperang` 的设备，记录其 MAC 地址（格式如 `AA:BB:CC:DD:EE:FF`）

4. 配对并连接：
```bash
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
```

5. 退出 bluetoothctl：
```bash
quit
```

### 2.3 绑定虚拟串口

创建 rfcomm 绑定：
```bash
sudo rfcomm bind 0 AA:BB:CC:DD:EE:FF
```

测试是否绑定成功：
```bash
ls /dev/rfcomm0
```

### 2.4 设置开机自动绑定

创建 systemd 服务：
```bash
sudo nano /etc/systemd/system/rfcomm-bind.service
```

内容：
```ini
[Unit]
Description=RFCOMM bind for Paperang P1
After=bluetooth.target

[Service]
Type=oneshot
ExecStart=/usr/bin/rfcomm bind 0 AA:BB:CC:DD:EE:FF
ExecStop=/usr/bin/rfcomm release 0
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable rfcomm-bind.service
sudo systemctl start rfcomm-bind.service
```

## 三、部署应用

### 3.1 克隆项目
```bash
cd ~
git clone <your-repo-url> paperang-p1
cd paperang-p1
```

或者直接拷贝项目文件到树莓派。

### 3.2 安装 Python 依赖
```bash
pip3 install -r requirements.txt
```

> **注意**: 如果 numpy/scipy 安装太慢或失败，可以用系统包：
> ```bash
> sudo apt install -y python3-numpy python3-scipy python3-skimage
> ```

### 3.3 修改配置
```bash
nano config.py
```

修改以下配置：
```python
SERIAL_PORT = "/dev/rfcomm0"
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
```

### 3.4 测试运行
```bash
python3 app.py
```

访问 `http://<树莓派IP>:5000` 测试。

## 四、配置开机自启动

### 4.1 创建 systemd 服务
```bash
sudo nano /etc/systemd/system/paperang-web.service
```

内容：
```ini
[Unit]
Description=Paperang P1 Web Print Server
After=network.target rfcomm-bind.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/paperang-p1
ExecStart=/usr/bin/python3 /home/pi/paperang-p1/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

> 注意：将 `pi` 替换为你的用户名，将路径替换为实际路径。

### 4.2 启用并启动服务
```bash
sudo systemctl enable paperang-web.service
sudo systemctl start paperang-web.service
```

### 4.3 查看状态和日志
```bash
# 查看服务状态
sudo systemctl status paperang-web.service

# 查看日志
sudo journalctl -u paperang-web.service -f
```

## 五、天气 API 配置

### 5.1 注册和风天气
1. 访问 https://dev.qweather.com/
2. 注册账号
3. 创建应用，获取 API Key

### 5.2 配置 API Key
API Key 通过环境变量提供，不写入代码仓库。编辑服务配置：
```bash
sudo systemctl edit paperang-web.service
```
加入：
```ini
[Service]
Environment="CAIYUN_API_KEY=你的彩云Key"
Environment="WEATHER_API_KEY=你的和风Key"
```
然后 `sudo systemctl restart paperang-web.service` 生效。

## 六、常用操作

### 查看打印机是否连接
```bash
ls /dev/rfcomm0
```

### 重启打印服务
```bash
sudo systemctl restart paperang-web.service
```

### 查看服务日志
```bash
sudo journalctl -u paperang-web.service -n 50
```

### 手动绑定蓝牙
```bash
sudo rfcomm bind 0 AA:BB:CC:DD:EE:FF
```

### 解绑蓝牙
```bash
sudo rfcomm release 0
```

## 七、故障排除

### 问题1: /dev/rfcomm0 不存在
- 检查打印机是否开机
- 检查蓝牙是否配对成功
- 重新执行 `sudo rfcomm bind 0 <MAC地址>`

### 问题2: 打印无反应
- 确认打印机有纸
- 确认打印机电量充足
- 检查服务日志 `sudo journalctl -u paperang-web.service`
- 尝试重新连接

### 问题3: Web页面无法访问
- 检查树莓派网络连接
- 确认服务正在运行 `sudo systemctl status paperang-web.service`
- 检查防火墙设置

### 问题4: 定时任务不执行
- 检查是否配置了天气 API Key
- 检查 `ENABLE_DAILY_WEATHER` 是否为 `True`
- 查看服务日志确认调度器状态
