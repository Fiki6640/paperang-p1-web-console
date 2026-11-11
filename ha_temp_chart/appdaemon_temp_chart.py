#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AppDaemon 应用: 每天 0 点用 HA 历史数据生成前一天温度曲线图,存到 HA 前端可见的 www 目录。
绘图与取数逻辑全部在 temp_chart.py,本文件只是调度薄封装。

配合 apps.yaml 使用,部署说明见同目录 README.md。
"""
import hassapi as hass

import temp_chart


class TempChartDaily(hass.Hass):
    def initialize(self):
        run_time = self.args.get('run_time', '00:00:00')
        self.run_daily(self._generate, run_time)
        if self.args.get('run_on_start'):
            # 启动即生成一次,便于部署后立刻验证效果
            self._generate({})

    def _generate(self, kwargs):
        cfg = self.args
        try:
            result = temp_chart.build_chart(
                ha_url=cfg.get('ha_url'),
                token=cfg.get('ha_token'),
                entity_id=cfg.get('entity_id', temp_chart.DEFAULT_ENTITY),
                days_ago=int(cfg.get('days_ago', 1)),
                out_path=cfg.get('output_path', '/homeassistant/www/temperature_chart.png'),
                width=int(cfg.get('width', 1000)),
                font_path=cfg.get('font_path') or None,
                rotate=int(cfg.get('rotate', 0)),
                print_url=cfg.get('print_url') or None,
                print_rotate=int(cfg.get('print_rotate', 90)),
                print_method=cfg.get('print_method', 'threshold'),
            )
        except Exception as e:  # AppDaemon 日志里留完整上下文
            self.error(f"[温度图] 生成失败: {e}", level='WARNING')
            return
        self.log(f"[温度图] 已生成 {result['path']} [{result['day']}] "
                 f"最高 {result['max']:.1f}{result['unit']} 最低 {result['min']:.1f}{result['unit']} "
                 f"平均 {result['avg']:.1f}{result['unit']} 样本 {result['samples']} 条")
        if result.get('printed'):
            if result['printed']['ok']:
                self.log(f"[温度图] 打印: {result['printed']['message']}")
            else:
                self.error(f"[温度图] 打印: {result['printed']['message']}", level='WARNING')
