#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立运行入口(备选方案)。
实现已合并至主体程序 services/temp_chart.py,本文件只是转发的薄壳,
保证原有命令行用法不变:
  python ha_temp_chart/temp_chart.py --demo
  python ha_temp_chart/temp_chart.py --ha-url http://<HA>:8123 --token <令牌> [--print-url ...]

合并部署(推荐): 直接用主体程序的 /temp-chart 页面与 daily_temp_chart 定时任务,
见仓库根 README.md。真正独立部署时只需复制 services/temp_chart.py 单个文件。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.temp_chart import (  # noqa: F401
    DEFAULT_ENTITY, PRINTER_NATIVE_WIDTH, PRINT_LENGTH,
    build_chart, draw_chart, fetch_day, fetch_history, fetch_meta,
    find_font, main, print_image, render_dashboard, render_print, rotate_image,
)

if __name__ == '__main__':
    sys.exit(main())
