#!/bin/bash
# Paperang P1 树莓派部署脚本
# 使用方法: sudo bash setup_raspberrypi.sh

set -e

echo "======================================"
echo "Paperang P1 树莓派部署"
echo "======================================"

# 1. 系统依赖
echo "[1/6] 安装系统依赖..."
apt-get update
apt-get install -y python3 python3-pip python3-venv bluez bluetooth libbluetooth-dev \
    wqy-microhei fonts-wqy-microhei

# 2. 创建工作目录
echo "[2/6] 设置工作目录..."
INSTALL_DIR="/home/pi/paperang-p1"
mkdir -p $INSTALL_DIR

# 3. Python 虚拟环境
echo "[3/6] 创建 Python 虚拟环境..."
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate

# 4. 安装 Python 依赖
echo "[4/6] 安装 Python 依赖..."
pip install --upgrade pip
pip install pyserial Pillow numpy Flask APScheduler requests

# 5. 配置蓝牙串口
echo "[5/6] 配置蓝牙串口..."
if ! grep -q "Enable=Source,Sink,Media,Socket" /etc/bluetooth/main.conf; then
    echo "  修改蓝牙配置..."
    cp /etc/bluetooth/main.conf /etc/bluetooth/main.conf.bak
    sed -i 's/^#DisablePlugins = network,input/DisablePlugins = network,input/' /etc/bluetooth/main.conf
    sed -i 's/^#AutoEnable=true/AutoEnable=true/' /etc/bluetooth/main.conf
fi

# 启用蓝牙
systemctl enable bluetooth
systemctl start bluetooth

echo ""
echo "======================================"
echo "安装完成!"
echo "======================================"
echo ""
echo "下一步操作:"
echo "1. 将项目文件复制到 $INSTALL_DIR"
echo "2. 配置 config.py 中的打印机串口和天气设置"
echo "3. 配对打印机:"
echo "   bluetoothctl scan on"
echo "   bluetoothctl pair <MAC地址>"
echo "   bluetoothctl trust <MAC地址>"
echo "4. 绑定串口: sudo rfcomm bind /dev/rfcomm0 <MAC地址> 1"
echo "5. 启动服务:"
echo "   sudo cp deploy/paperang-web.service /etc/systemd/system/"
echo "   sudo systemctl enable paperang-web"
echo "   sudo systemctl start paperang-web"
echo ""
echo "访问 Web 界面: http://<树莓派IP>:5000"
