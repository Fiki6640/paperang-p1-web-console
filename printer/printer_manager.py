#!/usr/bin/env python3
import logging
import time
from .serial_comm import PaperangSerial
from .image_processor import ImageProcessor
from . import bt_link
from utils import bark


class PrinterManager:
    def __init__(self, port, baudrate=9600, width=384, density=100, auto_reconnect=True):
        self.port = port
        self.baudrate = baudrate
        self.width = width
        self.density = density
        self.auto_reconnect = auto_reconnect
        self.serial = None
        self.image_processor = ImageProcessor(width)
        self._connect()

    def _connect(self):
        try:
            self.serial = PaperangSerial(self.port, self.baudrate, density=self.density)
            return self.serial.connected
        except Exception as e:
            logging.error("Failed to connect printer: %s" % str(e))
            return False

    def _ensure_connected(self):
        if self.is_connected():
            return True
        if self.auto_reconnect:
            logging.info("Reconnecting to printer...")
            return self._connect()
        return False

    def _safe_reconnect(self, max_attempts=3):
        """带延迟重试的安全重连"""
        for attempt in range(max_attempts):
            logging.info("Reconnect attempt %d/%d..." % (attempt + 1, max_attempts))
            if self._connect():
                return True
            if attempt < max_attempts - 1:
                time.sleep(1 + attempt * 1)
        return False

    def is_connected(self):
        return self.serial is not None and self.serial.connected

    def reconnect(self):
        self.disconnect()
        return self._connect()

    def disconnect(self):
        if self.serial:
            self.serial.disconnect()

    @staticmethod
    def _friendly_error(error_msg):
        """底层串口报错翻译成可操作的提示(Errno 5 = 蓝牙链路不通)"""
        msg = error_msg.lower()
        if "errno 5" in msg or "input/output error" in msg:
            return "打印机不在线(蓝牙连接中断)，请检查打印机电源后重试"
        if "no such file or directory" in msg:
            return "串口设备不存在(rfcomm 未绑定)，请检查 paperang-rfcomm 服务"
        return error_msg

    def _push_failure(self, error_msg):
        """打印失败推送到 Bark(未配置 BARK_URL 时静默跳过)"""
        try:
            bt = bt_link.get_state()
            state_text = {
                "online": "蓝牙在线",
                "offline": "蓝牙不在线(%s)" % bt["detail"],
                "unknown": "蓝牙状态未知",
            }.get(bt["state"], "蓝牙状态未知")
            bark.notify_print_failure("%s\n蓝牙状态: %s" % (error_msg, state_text))
        except Exception as e:
            logging.warning("Bark push hook error: %s" % str(e))

    def _safe_print(self, print_func, *args, **kwargs):
        """安全打印：带自动重连和重试"""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if not self._ensure_connected():
                    if attempt == max_retries:
                        self._push_failure("打印机未连接")
                        return {"success": False, "error": "打印机未连接", "attempts": attempt + 1}
                    if not self._safe_reconnect():
                        self._push_failure("重连失败，请检查打印机")
                        return {"success": False, "error": "重连失败，请检查打印机", "attempts": attempt + 1}
                print_func(*args, **kwargs)
                return {"success": True, "attempts": attempt + 1}
            except Exception as e:
                error_msg = str(e)
                logging.error("Print attempt %d failed: %s" % (attempt + 1, error_msg))
                if attempt < max_retries:
                    self.disconnect()
                    time.sleep(0.5)
                    continue
                friendly = self._friendly_error(error_msg)
                self._push_failure(friendly)
                return {"success": False, "error": friendly,
                        "attempts": attempt + 1}

    def print_self_test(self):
        return self._safe_print(self._print_self_test)

    def _print_self_test(self):
        self.serial.sendSelfTestToBt()

    def print_image_file(self, image_path, method="dither"):
        return self._safe_print(self._print_image_file, image_path, method)

    def _print_image_file(self, image_path, method):
        bitstream = self.image_processor.image_file_to_bitstream(image_path, method)
        self.serial.sendImageToBt(bitstream)

    def print_text(self, text, font_size=24, line_spacing=8):
        return self._safe_print(self._print_text, text, font_size, line_spacing)

    def _print_text(self, text, font_size, line_spacing):
        bitstream = self.image_processor.text_to_bitstream(text, font_size, line_spacing)
        self.serial.sendImageToBt(bitstream)

    def print_image_from_image(self, img, method="threshold"):
        return self._safe_print(self._print_image_from_image, img, method)

    def _print_image_from_image(self, img, method):
        import numpy as np
        from .image_processor import im2binimage_threshold, binimage2bitstream
        img_array = np.array(img)
        bin_img = im2binimage_threshold(img_array, self.width)
        bitstream = binimage2bitstream(bin_img)
        self.serial.sendImageToBt(bitstream)

    def feed_line(self, length=100):
        return self._safe_print(self._feed_line, length)

    def _feed_line(self, length):
        self.serial.sendFeedLineToBt(length)

    def set_density(self, density):
        return self._safe_print(self._set_density, density)

    def _set_density(self, density):
        density = max(0, min(255, density))
        self.density = density
        self.serial.sendDensityToBt(density)

    def set_power_off_time(self, minutes):
        return self._safe_print(self._set_power_off_time, minutes)

    def _set_power_off_time(self, minutes):
        self.serial.sendPowerOffTimeToBt(minutes)

    def set_paper_type(self, paper_type=0):
        return self._safe_print(self._set_paper_type, paper_type)

    def _set_paper_type(self, paper_type):
        self.serial.sendPaperTypeToBt(paper_type)

    def get_battery_status(self):
        result = self._safe_print(self._get_battery_status)
        if result["success"]:
            result["data"] = self.serial.queryBatteryStatus()
        return result

    def _get_battery_status(self):
        pass

    def get_density(self):
        result = self._safe_print(self._get_density)
        if result["success"]:
            result["data"] = self.serial.queryDensity()
        return result

    def _get_density(self):
        pass

    def get_sn(self):
        result = self._safe_print(self._get_sn)
        if result["success"]:
            result["data"] = self.serial.querySNFromBt()
        return result

    def _get_sn(self):
        pass

    def get_hardware_info(self):
        result = self._safe_print(self._get_hardware_info)
        if result["success"]:
            result["data"] = self.serial.queryHardwareInfo()
        return result

    def _get_hardware_info(self):
        pass

    def get_status(self):
        return {
            "connected": self.is_connected(),
            "port": self.port,
            "baudrate": self.baudrate,
            "width": self.width,
            # connected 只代表串口节点打开了,真实蓝牙在线状态看这里
            "bt": bt_link.get_state(),
        }
