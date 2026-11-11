#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
温度曲线图服务
从 weather_service.py 的"逐时气温"折线图提取而来,数据源改为 Home Assistant
传感器的真实历史数据(REST API),双版渲染:

- 屏幕版 render_dashboard(): 3 倍超采样抗锯齿,适合网页/仪表盘展示
- 打印版 render_print():   按热敏打印头原生分辨率(宽 384)竖版直出、
                            文字 1-bit 硬边,从绘制到出纸全程零缩放,无插值模糊

独立运行(备选): python services/temp_chart.py --demo / --ha-url ... --token ...
合并部署(推荐): 由 app.py 的 /temp-chart 页面与 daily_temp_chart 定时任务调用
"""
import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

# 默认实体(可通过 --entity / config.TEMP_ENTITY_ID / 环境变量覆盖)
DEFAULT_ENTITY = 'sensor.your_temperature_sensor'

# 热敏打印头原生分辨率(点),与 config.PRINTER_WIDTH 默认值一致
PRINTER_NATIVE_WIDTH = 384

# 打印版竖图长度(点),203dpi 下 1000 点约 12.5cm
PRINT_LENGTH = 1000

WEEKDAY_CN = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

# 字体查找顺序: 优先霞鹜文楷(与天气卡片一致),其余为常见中文/西文字体兜底
_FONT_CANDIDATES = [
    os.path.join('..', 'fonts', 'LXGWWenKai-Medium.ttf'),   # 仓库根目录 fonts/
    os.path.join('fonts', 'LXGWWenKai-Medium.ttf'),         # 与脚本同目录
    'LXGWWenKai-Medium.ttf',
    '/usr/share/fonts/truetype/lxgw/LXGWWenKai-Medium.ttf',
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simhei.ttf',
]


def find_font(prefer=None):
    """定位中文字体,找不到返回 None(退化到 PIL 默认字体)"""
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if prefer:
        candidates.append(prefer)
    for rel in _FONT_CANDIDATES:
        p = rel if os.path.isabs(rel) else os.path.join(base, rel)
        candidates.append(p)
    for p in candidates:
        try:
            if p and os.path.exists(p):
                return p
        except OSError:
            continue
    return None


def _headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


# Pillow>=9.1 用 Image.Transpose 枚举,9.0 及更早退回模块级常量
_TRANSPOSE = getattr(Image, 'Transpose', Image)


def rotate_image(img, degrees_cw):
    """顺时针旋转 degrees_cw 度(0/90/180/270),纯像素搬运无插值"""
    degrees_cw = int(degrees_cw) % 360
    if degrees_cw == 90:
        return img.transpose(_TRANSPOSE.ROTATE_270)
    if degrees_cw == 180:
        return img.transpose(_TRANSPOSE.ROTATE_180)
    if degrees_cw == 270:
        return img.transpose(_TRANSPOSE.ROTATE_90)
    return img


def print_image(print_url, image_path, method='threshold', timeout=60):
    """
    把图片 POST 到 paperang Web 服务的 /image-print 接口打印(独立部署用;
    与主体程序同机时应直接调 printer_manager.print_image_from_image)。
    接口成功/失败都返回 200,需检查页面里的失败提示。
    返回 (ok: bool, message: str)
    """
    _check_url(print_url)
    url = f"{print_url.rstrip('/')}/image-print"
    with open(image_path, 'rb') as f:
        resp = requests.post(url, files={'image': (os.path.basename(image_path), f)},
                             data={'method': method}, timeout=timeout)
    resp.raise_for_status()
    text = resp.text
    for marker in ('打印失败', '处理失败', '打印机未初始化', '请选择图片文件'):
        if marker in text:
            return False, f"打印机服务返回失败提示: {marker}"
    return True, '打印任务已发送'


def _check_url(ha_url):
    """ha_url 由使用者自行配置(通常是内网 HA/打印机地址),仅做协议白名单"""
    if not str(ha_url).lower().startswith(('http://', 'https://')):
        raise ValueError(f"URL 必须以 http:// 或 https:// 开头: {ha_url}")


def fetch_meta(ha_url, token, entity_id, timeout=15):
    """获取实体的 friendly_name 与单位,实体不存在时抛错"""
    _check_url(ha_url)
    url = f"{ha_url.rstrip('/')}/api/states/{entity_id}"
    resp = requests.get(url, headers=_headers(token), timeout=timeout)
    resp.raise_for_status()
    state = resp.json()
    attrs = state.get('attributes', {})
    return {
        'name': attrs.get('friendly_name', entity_id.split('.')[-1]),
        'unit': attrs.get('unit_of_measurement', '°C'),
    }


def fetch_history(ha_url, token, entity_id, start, end, timeout=15):
    """拉取 [start, end) 的状态历史,返回按时间排序的 [(datetime, float)]"""
    _check_url(ha_url)
    base = ha_url.rstrip('/')
    start_iso = start.isoformat(timespec='seconds')
    end_iso = end.isoformat(timespec='seconds')
    # 路径里的 + 时区偏移必须编码为 %2B,否则会被当作空格
    url = f"{base}/api/history/period/{quote(start_iso, safe='')}"
    resp = requests.get(
        url,
        params={'filter_entity_id': entity_id, 'end_time': end_iso,
                'minimal_response': 1},
        headers=_headers(token), timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    local_tz = datetime.now().astimezone().tzinfo
    merged = {}
    for states in data or []:
        for s in states:
            try:
                val = float(s.get('state'))
            except (TypeError, ValueError):
                continue  # unavailable / unknown / 非数值
            raw = s.get('last_updated') or s.get('last_changed')
            try:
                ts = datetime.fromisoformat(raw)
            except (TypeError, ValueError):
                continue
            if ts.tzinfo is None:  # 无时区的响应按本地时间处理
                ts = ts.replace(tzinfo=local_tz)
            merged[ts.astimezone(local_tz)] = val
    return sorted(merged.items())


def fetch_day(ha_url, token, entity_id=DEFAULT_ENTITY, days_ago=1, timeout=15):
    """拉取一天历史并组装绘图信息;days_ago=1 即 0 点跑的"刚结束的那天" """
    local_tz = datetime.now().astimezone().tzinfo
    today = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    day_start = today - timedelta(days=days_ago)
    meta = fetch_meta(ha_url, token, entity_id, timeout=timeout)
    samples = fetch_history(ha_url, token, entity_id, day_start,
                            day_start + timedelta(days=1), timeout=timeout)
    if not samples:
        raise RuntimeError(
            f"该时间段没有 {entity_id} 的有效数据(检查实体 ID、recorder 是否记录、以及数据保留时长)")
    return {
        'entity_id': entity_id,
        'day_start': day_start,
        'days_ago': days_ago,
        'samples': samples,
        'name': meta['name'],
        'unit': meta['unit'],
        'title': f"{meta['name']} · {day_start:%Y-%m-%d} {WEEKDAY_CN[day_start.weekday()]}",
    }


# 固定布局(逻辑像素): 总高 = 各固定块 + 绘图区高度
_FIXED_LAYOUT = [
    ('pad_top', 14), ('title_h', 34), ('gap1', 6), ('stats_h', 26), ('gap2', 10),
    ('plot_h', 280), ('gap3', 8), ('xlab_h', 22), ('gap4', 6), ('foot_h', 20),
    ('pad_bottom', 10),
]


def draw_chart(samples, title, day_start, unit='°C', width=1000,
               font_path=None, supersample=3, footer_note='',
               target_height=None, crisp=False):
    """
    绘制全天温度曲线(samples: [(datetime, float)],day_start 为当天 0 点)
    返回 PIL Image(灰度 L 模式,白底黑线,与天气卡片同风格)

    target_height: 固定总高(逻辑像素),绘图区高度自动压缩;默认按 plot_h=280 自适应
    crisp: 打印模式 — 无超采样、文字 1-bit 硬边(fontmode='1'),
           输出尺寸与热敏打印机原生分辨率逐点对应
    """
    S = 1 if crisp else max(1, int(supersample))

    def u(v):
        """逻辑像素 → 设备像素(S 倍超采样),所有布局与绘制坐标必须经过它"""
        return int(round(v * S))

    vals = [v for _, v in samples]

    # ---- 布局(逻辑像素,统一经 u() 放大后再绘制) ----
    layout = dict(_FIXED_LAYOUT)
    if target_height:
        fixed = sum(h for k, h in _FIXED_LAYOUT if k != 'plot_h')
        layout['plot_h'] = max(60, target_height - fixed)
    pad_top, title_h, gap1, stats_h, gap2 = (u(layout[k]) for k in
                                             ('pad_top', 'title_h', 'gap1', 'stats_h', 'gap2'))
    plot_h, gap3, xlab_h, gap4, foot_h, pad_bottom = (
        u(layout[k]) for k in ('plot_h', 'gap3', 'xlab_h', 'gap4', 'foot_h', 'pad_bottom'))
    left_m, right_m = u(58), u(24)
    W = u(width)
    H = pad_top + title_h + gap1 + stats_h + gap2 + plot_h + gap3 + xlab_h + gap4 + foot_h + pad_bottom
    plot_l, plot_r = left_m, W - right_m
    plot_t = pad_top + title_h + gap1 + stats_h + gap2
    plot_b = plot_t + plot_h

    img = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(img)
    if crisp:
        try:
            d.fontmode = '1'  # 文字 1-bit 渲染,无抗锯齿灰边
        except Exception:
            pass

    def F(size):
        if font_path:
            return ImageFont.truetype(font_path, u(size))
        return ImageFont.load_default(u(size))

    f_title, f_stats = F(26), F(19)
    f_axis, f_note, f_foot = F(15), F(16), F(13)

    ink, lab, axis, grid, foot = 25, 45, 110, 205, 150

    def text_c(x, y, s, font, fill):  # 居中文本
        d.text((x - d.textlength(s, font=font) / 2, y), s, fill=fill, font=font)

    def dashed_h(y, x0, x1, color):
        x = x0
        while x < x1:
            d.line([(x, y), (min(x + u(6), x1), y)], fill=color, width=S)
            x += u(10)

    def dashed_v(x, y0, y1, color):
        y = y0
        while y < y1:
            d.line([(x, y), (x, min(y + u(6), y1))], fill=color, width=S)
            y += u(10)

    # ---- Y 轴范围: 数据外扩,温差过小时强制拉开 ----
    vmin, vmax = min(vals), max(vals)
    span = vmax - vmin
    pad = max(1.0, span * 0.12)
    t_top, t_bot = vmax + pad, vmin - pad
    if t_top - t_bot < 4:
        t_top, t_bot = t_bot + 4, t_bot

    def X(ts):
        frac = (ts - day_start).total_seconds() / 86400.0
        frac = max(0.0, min(1.0, frac))
        return plot_l + (plot_r - plot_l) * frac

    def Y(v):
        return plot_b - (v - t_bot) / (t_top - t_bot) * plot_h

    # ---- 网格: 1/4、1/2、3/4 处横虚线 + 6/12/18 点竖虚线 ----
    for frac in (0.25, 0.5, 0.75):
        dashed_h(plot_t + plot_h * frac, plot_l, plot_r, grid)
    for hh in (6, 12, 18):
        dashed_v(X(day_start + timedelta(hours=hh)), plot_t, plot_b, grid)

    # ---- 坐标轴 ----
    d.line([(plot_l, plot_b), (plot_r, plot_b)], fill=axis, width=u(2))   # X
    d.line([(plot_l, plot_t), (plot_l, plot_b)], fill=axis, width=u(2))   # Y

    # Y 轴标签: 顶/中/底,右对齐
    for frac, v in ((1.0, t_top), (0.5, (t_top + t_bot) / 2), (0.0, t_bot)):
        yy = Y(v)
        s = f"{v:.0f}°" if (t_top - t_bot) >= 20 else f"{v:.1f}°"
        d.text((plot_l - u(8) - d.textlength(s, font=f_axis), yy - u(9)),
               s, fill=lab, font=f_axis)

    # X 轴: 每 2 小时一个刻度
    for hh in range(0, 24, 2):
        xx = X(day_start + timedelta(hours=hh))
        d.line([(xx, plot_b), (xx, plot_b + u(4))], fill=axis, width=S)
        text_c(xx, plot_b + u(7), f"{hh:02d}", f_axis, lab)

    # ---- 折线(HA 历史数据密集,顶点不画圆点,走势由折线本身表达) ----
    pts = [(X(ts), Y(v)) for ts, v in samples]
    if len(pts) >= 2:
        d.line(pts, fill=ink, width=u(3), joint='curve')

    # ---- 峰值/谷值标注(实心小三角 + 数值,不依赖特殊字形) ----
    def annotate(i, prefer_up):
        px, py = pts[i]
        s = f"{vals[i]:.1f}"
        sw = d.textlength(s, font=f_note)
        cx = min(max(px, plot_l + sw / 2 + u(2)), plot_r - sw / 2 - u(2))
        # 标注块约占 三角6+文本18(逻辑px);贴近绘图区边缘时翻到点的另一侧,避免压轴压字
        room_up = py - u(34) >= plot_t
        room_down = py + u(34) <= plot_b
        up = (room_up or not room_down) if prefer_up else (not room_down and room_up)
        if up:
            tri_top = max(py - u(16), plot_t)
            d.polygon([(cx, tri_top + u(6)), (cx - u(4), tri_top),
                       (cx + u(4), tri_top)], fill=ink)
            d.text((cx - sw / 2, tri_top - u(18)), s, fill=ink, font=f_note)
        else:
            base = min(py + u(16), plot_b)
            d.polygon([(cx, base - u(6)), (cx - u(4), base),
                       (cx + u(4), base)], fill=ink)
            d.text((cx - sw / 2, base + u(3)), s, fill=ink, font=f_note)

    imax, imin = vals.index(vmax), vals.index(vmin)
    if len(pts) >= 2:
        annotate(imax, prefer_up=True)
        if imin != imax:
            annotate(imin, prefer_up=False)

    # ---- 标题 / 统计 / 页脚 ----
    d.text((left_m, pad_top), title, fill=ink, font=f_title)
    stats = (f"最高 {vmax:.1f}{unit}   最低 {vmin:.1f}{unit}   "
             f"平均 {sum(vals) / len(vals):.1f}{unit}   样本 {len(vals)} 条")
    d.text((left_m, pad_top + title_h + gap1), stats, fill=lab, font=f_stats)
    note = footer_note or f"生成于 {datetime.now().strftime('%m-%d %H:%M')} · 数据来源 Home Assistant"
    d.text((left_m, H - pad_bottom - foot_h), note, fill=foot, font=f_foot)

    # ---- 屏幕版缩小抗锯齿;打印版 S=1 原尺寸直出 ----
    return img if crisp else img.resize((width, H // S), Image.LANCZOS)


def render_dashboard(day, width=1000, font_path=None, footer_note=''):
    """屏幕版: 抗锯齿,横版 width × 384(高度与打印原生分辨率一致)"""
    return draw_chart(day['samples'], day['title'], day['day_start'], unit=day['unit'],
                      width=width, font_path=font_path or find_font(),
                      supersample=3, footer_note=footer_note, target_height=384)


def render_print(day, native_width=PRINTER_NATIVE_WIDTH, length=PRINT_LENGTH,
                 font_path=None, footer_note=''):
    """
    打印版: 宽 native_width(热敏头原生 384)的竖版图,长 length(默认 1000 点≈12.5cm)。
    无抗锯齿 + 文字 1-bit 硬边,旋转为纯像素搬运,
    与 printer 的 im2binimage_threshold(width=384) 链路对接时零缩放。
    """
    img = draw_chart(day['samples'], day['title'], day['day_start'], unit=day['unit'],
                     width=length, font_path=font_path or find_font(),
                     supersample=1, target_height=native_width, crisp=True,
                     footer_note=footer_note)
    return rotate_image(img, 90)


def build_chart(ha_url=None, token=None, entity_id=DEFAULT_ENTITY, days_ago=1,
                out_path='temperature_chart.png', width=1000, font_path=None,
                timeout=15, day=None,
                rotate=0, print_url=None, print_rotate=90, print_method='threshold'):
    """
    生成一天温度图(屏幕版)并保存,返回统计 dict。day 传入 fetch_day() 结果时跳过网络。
    rotate: 保存到 out_path 的图片顺时针旋转角度(0/90/180/270)。
    print_url: 树莓派 paperang Web 服务地址,非空则另存原生 384px 打印版(按 print_rotate
               旋转)POST 打印,不影响 out_path 保存的横版原图。
    """
    if day is None:
        day = fetch_day(ha_url, token, entity_id, days_ago=days_ago, timeout=timeout)

    img = render_dashboard(day, width=width, font_path=font_path)
    if rotate:
        img = rotate_image(img, rotate)
    img.save(out_path)

    printed = None
    if print_url:
        # 打印副本: 无抗锯齿原生渲染后按 print_rotate 旋转,POST 后即删
        base, ext = os.path.splitext(out_path)
        print_copy = f"{base}.print{ext or '.png'}"
        try:
            crisp = draw_chart(day['samples'], day['title'], day['day_start'],
                               unit=day['unit'], width=PRINT_LENGTH,
                               font_path=font_path or find_font(), supersample=1,
                               target_height=PRINTER_NATIVE_WIDTH, crisp=True)
            rotate_image(crisp, print_rotate).save(print_copy)
            ok, message = print_image(print_url, print_copy, method=print_method,
                                      timeout=timeout)
            printed = {'ok': ok, 'message': message, 'path': print_copy}
        finally:
            try:
                os.remove(print_copy)
            except OSError:
                pass

    vals = [v for _, v in day['samples']]
    return {'path': out_path, 'samples': len(vals), 'unit': day['unit'],
            'min': min(vals), 'max': max(vals),
            'avg': sum(vals) / len(vals),
            'day': day['day_start'].strftime('%Y-%m-%d'),
            'printed': printed}


def _demo_samples(days_ago=1):
    """演示数据: 单峰日变化曲线,偶发丢点,按日期固定随机种子保证可复现"""
    local_tz = datetime.now().astimezone().tzinfo
    day_start = datetime.now(local_tz).replace(
        hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    rng = random.Random(day_start.strftime('%Y%m%d'))
    samples = []
    minutes = 0.0
    while minutes < 24 * 60:
        if rng.random() > 0.06:
            temp = (22 + 7 * math.sin((minutes / 60 - 9.5) / 24 * 2 * math.pi)
                    + rng.uniform(-0.3, 0.3))
            samples.append((day_start + timedelta(minutes=minutes), round(temp, 1)))
        minutes += 10
    return samples


def _demo_day(days_ago=1):
    local_tz = datetime.now().astimezone().tzinfo
    day_start = datetime.now(local_tz).replace(
        hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return {'entity_id': 'demo', 'day_start': day_start, 'days_ago': days_ago,
            'samples': _demo_samples(days_ago), 'name': '演示温度', 'unit': '°C',
            'title': f"演示温度 · {day_start:%Y-%m-%d} {WEEKDAY_CN[day_start.weekday()]}"}


def main(argv=None):
    p = argparse.ArgumentParser(description='从 Home Assistant 历史数据生成全天温度曲线图')
    p.add_argument('--ha-url', default=os.environ.get('HA_URL'), help='HA 地址,如 http://192.168.1.10:8123')
    p.add_argument('--token', default=os.environ.get('HA_TOKEN'), help='长期访问令牌')
    p.add_argument('--entity', default=DEFAULT_ENTITY, help='温度实体 ID')
    p.add_argument('--days-ago', type=int, default=1, help='0=今天(截至目前) 1=昨天(默认)')
    p.add_argument('--out', default='temperature_chart.png', help='输出 PNG 路径')
    p.add_argument('--width', type=int, default=1000, help='图片宽度(默认 1000)')
    p.add_argument('--font', default=None, help='指定字体文件路径')
    p.add_argument('--rotate', type=int, default=0, choices=(0, 90, 180, 270),
                   help='保存的图片顺时针旋转角度(默认 0 不旋转)')
    p.add_argument('--print-url', default=os.environ.get('PRINT_URL'),
                   help='paperang Web 服务地址(如 http://192.168.1.20:5000),设置后生成即打印')
    p.add_argument('--print-rotate', type=int, default=90, choices=(0, 90, 180, 270),
                   help='打印副本顺时针旋转角度(默认 90;不影响 --out 保存的图)')
    p.add_argument('--print-method', default='threshold', choices=('threshold', 'dither'),
                   help='打印二值化方式: threshold 适合线图(默认), dither 适合照片')
    p.add_argument('--demo', action='store_true', help='用演示数据绘图,不访问 HA')
    args = p.parse_args(argv)

    if args.demo:
        try:
            result = build_chart(entity_id=args.entity, out_path=args.out,
                                 width=args.width, font_path=args.font,
                                 day=_demo_day(args.days_ago),
                                 rotate=args.rotate, print_url=args.print_url,
                                 print_rotate=args.print_rotate,
                                 print_method=args.print_method)
        except RuntimeError as e:
            print(f"错误: {e}", file=sys.stderr)
            return 2
    else:
        if not args.ha_url or not args.token:
            p.error('需要 --ha-url 与 --token(或环境变量 HA_URL / HA_TOKEN);'
                    '令牌在 HA 网页端 用户头像 → 安全 → 长期访问令牌 创建')
        try:
            result = build_chart(ha_url=args.ha_url, token=args.token,
                                 entity_id=args.entity, days_ago=args.days_ago,
                                 out_path=args.out, width=args.width,
                                 font_path=args.font, rotate=args.rotate,
                                 print_url=args.print_url,
                                 print_rotate=args.print_rotate,
                                 print_method=args.print_method)
        except (requests.RequestException, RuntimeError, ValueError) as e:
            print(f"生成失败: {e}", file=sys.stderr)
            return 2

    msg = (f"已生成 {result['path']}  [{result['day']}]  "
           f"最高 {result['max']:.1f}°  最低 {result['min']:.1f}°  "
           f"平均 {result['avg']:.1f}°  样本 {result['samples']} 条")
    if result.get('printed'):
        tag = '成功' if result['printed']['ok'] else '失败'
        msg += f"\n打印: {tag}, {result['printed']['message']}"
        if not result['printed']['ok']:
            print(msg)
            return 3
    print(msg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
