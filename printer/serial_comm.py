#!/usr/bin/python3
# -*-coding:utf-8 -*-
import struct
import zlib
import logging
import time
import serial
from .const import BtCommandByte


class PaperangSerial:
    standardKey = 0x35769521
    padding_line = 300
    max_send_msg_length = 1536
    max_recv_msg_length = 1024

    def __init__(self, port, baudrate=9600, timeout=5, density=100):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.density = density
        self.crckeyset = False
        self.connected = False
        self.sock = None
        if self.connect():
            self.connected = True

    def connect(self):
        try:
            logging.info("Connecting to %s at %d baud..." % (self.port, self.baudrate))
            self.sock = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            if not self.sock.is_open:
                self.sock.open()
            logging.info("Connected to %s" % self.port)
            
            time.sleep(1.0)
            self.sock.reset_input_buffer()
            self.sock.reset_output_buffer()
            
            try:
                self.registerCrcKeyToBt()
            except Exception as e:
                logging.warning("CRC key set failed (non-critical): %s" % str(e))
            
            try:
                self.sendDensityToBt(self.density)
                logging.info("Print density set to %d" % self.density)
            except Exception as e:
                logging.warning("Density set failed (non-critical): %s" % str(e))
            
            return True
        except Exception as e:
            logging.error("Failed to connect: %s" % str(e))
            return False

    def disconnect(self):
        try:
            if self.sock and self.sock.is_open:
                self.sock.close()
            logging.info("Disconnected.")
        except Exception as e:
            logging.error("Error disconnecting: %s" % str(e))
        self.connected = False

    def sendMsgAllPackage(self, msg):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                sent_len = self.sock.write(msg)
                self.sock.flush()
                logging.info("Sending msg with length = %d..." % sent_len)
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning("Send attempt %d failed, retrying...: %s" % (attempt + 1, str(e)))
                    try:
                        if self.sock.in_waiting > 0:
                            self.sock.read(self.sock.in_waiting)
                    except Exception:
                        pass
                    time.sleep(0.5 + attempt * 0.5)
                else:
                    raise

    def crc32(self, content):
        return zlib.crc32(content, self.crcKey if self.crckeyset else self.standardKey) & 0xffffffff

    def packPerBytes(self, bytes_data, control_command, i):
        result = struct.pack('<BBB', 2, control_command, i)
        result += struct.pack('<H', len(bytes_data))
        result += bytes_data
        result += struct.pack('<I', self.crc32(bytes_data))
        result += struct.pack('<B', 3)
        return result

    def addBytesToList(self, bytes_data):
        length = self.max_send_msg_length
        result = [bytes_data[i:i + length] for i in range(0, len(bytes_data), length)]
        return result

    def sendToBt(self, data_bytes, control_command, need_reply=True):
        bytes_list = self.addBytesToList(data_bytes)
        for i, bytes_chunk in enumerate(bytes_list):
            tmp = self.packPerBytes(bytes_chunk, control_command, i)
            self.sendMsgAllPackage(tmp)
        if need_reply:
            return self.recv()
        return None

    def recv(self):
        try:
            raw_msg = self.sock.read(self.max_recv_msg_length)
            if not raw_msg:
                logging.warning("No data received from serial port.")
                return None, []
            parsed = self.resultParser(raw_msg)
            logging.info("Recv: " + raw_msg.hex())
            logging.info("Received %d packets: " % len(parsed) + "".join([str(p) for p in parsed]))
            return raw_msg, parsed
        except Exception as e:
            logging.error("Error receiving data: %s" % str(e))
            return None, []

    def resultParser(self, data):
        base = 0
        res = []
        while base < len(data) and data[base] == 0x02:
            class Info(object):
                def __str__(self):
                    return "\nControl command: %s(%s)\nPayload length: %d\nPayload(hex): %s" % (
                        self.command, BtCommandByte.findCommand(self.command),
                        self.payload_length, self.payload.hex()
                    )
            info = Info()
            _, info.command, _, info.payload_length = struct.unpack('<BBBH', data[base:base + 5])
            info.payload = data[base + 5: base + 5 + info.payload_length]
            info.crc32 = data[base + 5 + info.payload_length: base + 9 + info.payload_length]
            base += 10 + info.payload_length
            res.append(info)
        return res

    def registerCrcKeyToBt(self, key=0x6968634 ^ 0x2e696d):
        logging.info("Setting CRC32 key...")
        msg = struct.pack('<I', int(key ^ self.standardKey))
        self.sendToBt(msg, BtCommandByte.PRT_SET_CRC_KEY)
        self.crcKey = key
        self.crckeyset = True
        logging.info("CRC32 key set.")

    def sendPaperTypeToBt(self, paperType=0):
        msg = struct.pack('<B', paperType)
        self.sendToBt(msg, BtCommandByte.PRT_SET_PAPER_TYPE)

    def sendPowerOffTimeToBt(self, poweroff_time=0):
        msg = struct.pack('<H', poweroff_time)
        self.sendToBt(msg, BtCommandByte.PRT_SET_POWER_DOWN_TIME)

    def sendImageToBt(self, binary_img):
        self.sendPaperTypeToBt()
        msg = bytes(binary_img)
        self.sendToBt(msg, BtCommandByte.PRT_PRINT_DATA, need_reply=False)
        self.sendFeedLineToBt(self.padding_line)

    def sendSelfTestToBt(self):
        msg = struct.pack('<B', 0)
        self.sendToBt(msg, BtCommandByte.PRT_PRINT_TEST_PAGE)

    def sendDensityToBt(self, density):
        msg = struct.pack('<B', density)
        self.sendToBt(msg, BtCommandByte.PRT_SET_HEAT_DENSITY)

    def sendFeedLineToBt(self, length):
        msg = struct.pack('<H', length)
        self.sendToBt(msg, BtCommandByte.PRT_FEED_LINE)

    def queryBatteryStatus(self):
        msg = struct.pack('<B', 1)
        return self.sendToBt(msg, BtCommandByte.PRT_GET_BAT_STATUS)

    def queryDensity(self):
        msg = struct.pack('<B', 1)
        return self.sendToBt(msg, BtCommandByte.PRT_GET_HEAT_DENSITY)

    def sendFeedToHeadLineToBt(self, length):
        msg = struct.pack('<H', length)
        self.sendToBt(msg, BtCommandByte.PRT_FEED_TO_HEAD_LINE)

    def queryPowerOffTime(self):
        msg = struct.pack('<B', 1)
        return self.sendToBt(msg, BtCommandByte.PRT_GET_POWER_DOWN_TIME)

    def querySNFromBt(self):
        msg = struct.pack('<B', 1)
        return self.sendToBt(msg, BtCommandByte.PRT_GET_SN)

    def queryHardwareInfo(self):
        msg = struct.pack('<B', 1)
        return self.sendToBt(msg, BtCommandByte.PRT_GET_HW_INFO)
