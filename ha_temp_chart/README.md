# HA 温度曲线图生成器

> **推荐部署方式已变更**:本功能已合并进主体程序(app.py 的 `/temp-chart` 页面 +
> `daily_temp_chart` 定时任务),实现移至 `services/temp_chart.py`,在树莓派上直接运行、
> 无需 HA 侧任何部署,打印版还升级为原生 384px 零缩放渲染。详见仓库根 README.md。
> 本目录保留为**独立备选方案**(HA 侧单独跑、不经主体程序时使用)。

从本项目 `services/weather_service.py` 的"逐时气温"折线图提取出来的独立小组件,改为:

- **数据源**:Home Assistant 传感器的真实历史数据(REST API),不再是天气预报
- **内容**:一天(00:00–24:00)的温度曲线,含最高/最低/平均统计、峰值谷值标注、逐 2 小时刻度
- **清晰度**:屏幕版默认 1000px 宽、3 倍超采样抗锯齿;打印版(`--print-url`)为原生 384px 竖版无抗锯齿渲染
- **调度**:每天 0 点自动生成"刚结束那天"的曲线

## 文件

| 文件 | 用途 |
|---|---|
| `temp_chart.py` | 薄壳入口,转发到 `services/temp_chart.py`(独立部署只需复制那一个文件) |
| `appdaemon_temp_chart.py` | AppDaemon 调度封装(备选方案 A) |
| `apps.yaml` | AppDaemon 应用配置样例 |
| `example.png` | 横版渲染效果(HA 仪表盘用) |
| `example_print.png` | 旋转 90° 后的打印版效果 |

依赖仅 `requests` + `Pillow`。中文字体优先用本仓库的 `fonts/LXGWWenKai-Medium.ttf`(找不到时自动退化到系统字体)。

## 本地快速测试

```bash
# 演示数据,不连 HA(验证绘图效果)
python temp_chart.py --demo --out demo.png

# 真实数据:昨天全天(0 点跑的就是这条)
python temp_chart.py --ha-url http://192.168.1.10:8123 --token <长期访问令牌> \
    --entity sensor.your_temperature_sensor \
    --out temperature_chart.png

# 今天截至目前(--days-ago 0)
python temp_chart.py --ha-url ... --token ... --days-ago 0 --out today.png
```

长期访问令牌:HA 网页端 → 左下角用户头像 → **安全** → 最下方 **长期访问令牌** → 创建令牌。也可用环境变量 `HA_URL` / `HA_TOKEN` 代替这两个参数。

## 方案 A:AppDaemon 插件(推荐,适合 HAOS / Supervised)

1. **安装 AppDaemon**:`设置 → 加载项 → 加载项商店` 搜索 "AppDaemon"(社区版),安装。
2. **配置插件**:在插件"配置"页加入 Pillow 依赖,保存:
   ```yaml
   python_packages:
     - Pillow
   ```
3. **创建长期访问令牌**(见上文)。
4. **放置文件**:把 `temp_chart.py`、`appdaemon_temp_chart.py`、`LXGWWenKai-Medium.ttf` 三个文件
   复制到 AppDaemon 的应用目录:
   ```
   /addon_configs/a0d7b954_appdaemon/apps/temp_chart/
   ```
   访问方式任选:Samba 加载项(新版本里 addon 配置目录直接可见)、Studio Code Server、File Editor,
   或"Advanced SSH & Web Terminal"。
5. **注册应用**:编辑 `/addon_configs/a0d7b954_appdaemon/apps/apps.yaml`,追加本目录 `apps.yaml` 的内容
   (建议把令牌写进同目录 `secrets.yaml`)。
6. **启动并验证**:启动 AppDaemon,日志里应出现 `[温度图] 已生成 /homeassistant/www/temperature_chart.png ...`。

> 关键点:AppDaemon 容器里 HA 的 `www` 目录映射为 **`/homeassistant/www`**(不是 `/config/www`),
> 所以配置里 `output_path` 写 `/homeassistant/www/temperature_chart.png`。

## 方案 B:任意主机 + cron(适合 HA Container / Supervised / 树莓派等有宿主机权限的场景)

```bash
pip install requests Pillow
# 先手动跑一次确认输出
python temp_chart.py --ha-url http://<HA地址>:8123 --token <令牌> \
    --entity sensor.your_temperature_sensor \
    --out /path/to/homeassistant/config/www/temperature_chart.png
```

`crontab -e` 加入(每天 0:05,错开整点;HA_URL/HA_TOKEN 也可放环境变量):

```cron
5 0 * * * cd /opt/ha_temp_chart && HA_URL=http://<HA地址>:8123 HA_TOKEN=<令牌> /usr/bin/python3 temp_chart.py --out /path/to/homeassistant/config/www/temperature_chart.png >> /var/log/temp_chart.log 2>&1
```

`--out` 直接写 HA 配置目录下的 `www/`(容器部署即宿主机挂载的 config 目录;Supervised 为 `/usr/share/hassio/homeassistant/www`)。若无文件系统访问权限,可输出到本地目录再经 Samba 同步,或改走 MQTT 相机方案。

## 打印到 paperang(旋转 90°)

横版图(1000×436)直接打印会被缩到 384×167,完全看不清;**顺时针旋转 90°** 后变
436×1000,缩放到打印机 384px 宽时是 384×881,时间轴竖排(00 在上、23 在下),把纸逆时针
转 90° 即可正常阅读。效果见 `example_print.png`。

前提:树莓派上 `paperang-web.service` 已运行(本项目 Flask 服务,默认端口 5000)。

```bash
# 生成 + 打印(打印副本旋转 90°,保存的 --out 文件保持横版)
python temp_chart.py --ha-url ... --token ... \
    --print-url http://<树莓派IP>:5000 --out temperature_chart.png

# 打印参数:--print-rotate {0,90,180,270} 旋转角度(默认 90)
#          --print-method threshold|dither 二值化方式(线图用 threshold,照片用 dither)

# 只要竖版文件、不打印:
python temp_chart.py --demo --rotate 90 --out portrait.png
```

AppDaemon 方式在 `apps.yaml` 里加三项即可(样例已含):

```yaml
  print_url: "http://192.168.1.20:5000"   # 树莓派 paperang Web 服务
  print_rotate: 90
  print_method: "threshold"
```

每天 0 点的完整流程变成:拉历史 → 生成横版图存 HA www(仪表盘更新)→ 打印副本旋转
90° POST 给树莓派 → 出纸。打印失败只记日志,不影响图片生成。

## 前端展示(两种方案通用)

推荐"本地文件相机",每次刷新自动读新图,无浏览器缓存问题。`configuration.yaml`:

```yaml
camera:
  - platform: local_file
    name: 温度曲线
    file_path: /config/www/temperature_chart.png
    scan_interval: 3600
```

仪表盘卡片:

```yaml
type: picture-entity
entity: camera.wen_du_qu_xian
camera_image: camera.wen_du_qu_xian
show_state: false
```

或者最简单的图片卡片(HA 的 `/local` 静态服务带 Last-Modified,普通刷新即可更新):

```yaml
type: picture
image: /local/temperature_chart.png
```

## 常见问题

- **401 / 403**:令牌错误或被撤销,重新创建;注意 `--token` 不要带引号或空格。
- **"该时间段没有有效数据"**:实体 ID 写错(在开发者工具 → 状态里核对);或该传感器没被 recorder 记录 / 保留期过短(默认 10 天,足够)。
- **中文显示成方块**:没有找到中文字体,把 `LXGWWenKai-Medium.ttf` 放到脚本同目录,或用 `--font` 指定。
- **曲线只有几个点**:蓝牙温度传感器上报间隔长属正常,折线按时间比例绘制,不影响读数。
- **手机 App 里图不更新**:改用上面的 `local_file` 相机方案。
