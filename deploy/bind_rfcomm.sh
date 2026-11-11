#!/bin/bash
# Paperang P1 打印机 rfcomm 绑定脚本
# 在 systemd 服务启动前执行，确保 /dev/rfcomm0 可用

PRINTER_MAC="AA:BB:CC:DD:EE:FF"   # 改成你的打印机 MAC
RFCOMM_DEV="/dev/rfcomm0"

# 检查是否已经绑定
if rfcomm show rfcomm0 2>/dev/null | grep -q "$PRINTER_MAC"; then
    echo "rfcomm0 already bound to $PRINTER_MAC"
    exit 0
fi

# 先释放（如果被占用）
rfcomm release rfcomm0 2>/dev/null
sleep 1

# 重新绑定
echo "Binding rfcomm0 to $PRINTER_MAC..."
rfcomm bind rfcomm0 "$PRINTER_MAC" 1
sleep 2

# 检查是否成功
if [ -e "$RFCOMM_DEV" ]; then
    echo "Success: $RFCOMM_DEV is ready"
    exit 0
else
    echo "Error: Failed to bind $RFCOMM_DEV"
    exit 1
fi
