import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useBlocker } from "react-router";
import {
  Button,
  Chip,
  Input,
  Label,
  ListBox,
  Modal,
  Select,
  Switch,
  TextField,
  useOverlayState,
} from "@heroui/react";
import {
  BatteryCharging,
  Bell,
  Clock3,
  CloudSun,
  Database,
  Printer as PrinterIcon,
  RefreshCw,
  ScrollText,
  Trash2,
} from "lucide-react";
import SaveBar from "../components/SaveBar";
import { api, showError, showToast, type ApiEnvelope, type DeviceInfo, type SettingsSnapshot } from "../lib/api";

/** 波特率固定选项(串口速率没有任意值的意义);当前值不在列表时动态并入 */
const BAUDRATE_OPTIONS = [9600, 19200, 38400, 57600, 115200];

/**
 * 设置页:打印机 / 天气 / 温度数据源 / 定时任务 / 通知 / 设备信息 六组卡片。
 * - 统一草稿态,SaveBar 吸底:一次保存把每组改动提交到各自端点
 * - 密钥类输入留空 = 保留原值(页面不回显明文),带「已配置」标记
 * - 有未保存修改时切换页面弹出确认,放弃修改才放行
 */
export default function Settings() {
  const [snap, setSnap] = useState<SettingsSnapshot | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [device, setDevice] = useState<DeviceInfo | null>(null);
  const [deviceLoading, setDeviceLoading] = useState(false);

  const load = useCallback(async () => {
    const s = await api.settings();
    setSnap(s);
    setDraft(toDraft(s));
  }, []);

  useEffect(() => {
    load().catch((e) => showError(e));
  }, [load]);

  const refreshDevice = useCallback(() => {
    setDeviceLoading(true);
    api
      .deviceInfo()
      .then(setDevice)
      .catch((e) => showError(e))
      .finally(() => setDeviceLoading(false));
  }, []);
  useEffect(refreshDevice, [refreshDevice]);

  const dirty = useMemo(() => {
    if (!snap || !draft) return false;
    return JSON.stringify(draft) !== JSON.stringify(toDraft(snap));
  }, [snap, draft]);

  // ---- 未保存修改拦截:路由内切换用 useBlocker,刷新/关标签用 beforeunload ----
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const guardState = useOverlayState();

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirtyRef.current && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    if (blocker.state === "blocked") guardState.open();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocker.state]);
  // 保存完成(dirty 变 false)时若仍在拦截,自动放行
  useEffect(() => {
    if (blocker && blocker.state === "blocked" && !dirty) blocker.proceed();
  }, [blocker, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = ""; // 浏览器原生确认
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  if (!snap || !draft) {
    return (
      <>
        
        <div className="h-40 animate-pulse rounded-large bg-default-100" />
      </>
    );
  }

  const baudOptions = [...new Set([...BAUDRATE_OPTIONS, num(draft.printer.baudrate)])];

  const set = <K extends keyof Draft>(group: K, patch: Partial<Draft[K]>) =>
    setDraft((d) => (d ? { ...d, [group]: { ...d[group], ...patch } } : d));

  const saveAll = async () => {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      const base = toDraft(snap);
      const jobs: Promise<ApiEnvelope>[] = [];
      if (JSON.stringify(draft.printer) !== JSON.stringify(base.printer)) {
        const p = draft.printer;
        jobs.push(api.savePrinter({
          serial_port: p.serial_port,
          baudrate: num(p.baudrate),
          width: num(p.width),
          density: num(p.density),
          bt_mac: p.bt_mac,
          auto_reconnect: p.auto_reconnect,
        }));
      }
      if (JSON.stringify(draft.weather) !== JSON.stringify(base.weather)) {
        const w = draft.weather;
        jobs.push(api.saveWeather({
          weather_provider: w.provider,
          caiyun_api_key: w.caiyun_api_key, // 空串 = 保留
          weather_api_key: w.weather_api_key,
          weather_city: w.weather_city,
          weather_latitude: w.weather_latitude,
          weather_longitude: w.weather_longitude,
          weather_location_name: w.weather_location_name,
        }));
      }
      if (JSON.stringify(draft.temp) !== JSON.stringify(base.temp)) {
        const t = draft.temp;
        jobs.push(api.saveTemp({ ha_url: t.ha_url, ha_token: t.ha_token, entity_id: t.entity_id }));
      }
      if (JSON.stringify(draft.schedule) !== JSON.stringify(base.schedule)) {
        jobs.push(api.saveSchedule({
          weather: { enabled: draft.schedule.weatherEnabled, print_time: draft.schedule.weatherTime },
          temp: { enabled: draft.schedule.tempEnabled, print_time: draft.schedule.tempTime },
        }));
      }
      if (JSON.stringify(draft.notify) !== JSON.stringify(base.notify)) {
        // bark_url: null = 清除,字符串 = 设置/保留
        jobs.push(api.saveNotify({
          bark_url: draft.notify.barkCleared ? null : draft.notify.barkUrl,
          bark_group: draft.notify.barkGroup,
        }));
      }
      const results = await Promise.allSettled(jobs);
      for (const r of results) {
        if (r.status === "fulfilled") showToast(r.value);
        else showError(r.reason);
      }
      await load();
    } catch (e) {
      showError(e);
    } finally {
      setSaving(false);
    }
  };

  const reset = () => setDraft(toDraft(snap));

  const testPrint = async () => {
    try {
      showToast(await api.setDensity(num(draft.printer.density)));
      showToast(await api.selfTest());
    } catch (e) {
      showError(e);
    }
  };

  return (
    <>
      

      <div className="flex flex-col gap-5">
        {/* 打印机 */}
        <Section icon={PrinterIcon} title="打印机">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="串口名称" hint="Linux: /dev/rfcomm0 · Windows: COM4">
              <Input value={draft.printer.serial_port} onChange={(e) => set("printer", { serial_port: e.target.value })} />
            </Field>
            <Field label="蓝牙 MAC">
              <Input value={draft.printer.bt_mac} onChange={(e) => set("printer", { bt_mac: e.target.value })} spellCheck={false} />
            </Field>
            <div className="flex flex-col gap-1.5">
              <Label>波特率</Label>
              <Select
                fullWidth
                selectedKey={String(draft.printer.baudrate)}
                onSelectionChange={(k) => set("printer", { baudrate: String(k) })}
                aria-label="波特率"
              >
                <Select.Trigger>
                  <Select.Value />
                  <Select.Indicator />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {baudOptions.map((b) => (
                      <ListBox.Item key={String(b)} id={String(b)} textValue={String(b)}>
                        {b}
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
              <span className="text-xs text-foreground/45">P1 使用 9600</span>
            </div>
            <Field label="打印宽度 (点)">
              <Input type="number" value={draft.printer.width} onChange={(e) => set("printer", { width: e.target.value })} />
            </Field>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-6">
            <div className="min-w-56 flex-1">
              <div className="mb-1.5 flex items-baseline justify-between">
                <Label>打印密度（0-255，越高越黑）</Label>
                <span className="text-sm font-medium text-primary">{draft.printer.density}</span>
              </div>
              <input
                type="range"
                min={0}
                max={255}
                value={num(draft.printer.density)}
                onChange={(e) => set("printer", { density: e.target.value })}
                className="w-full accent-[var(--heroui-primary)]"
                aria-label="打印密度"
              />
            </div>
            <Button variant="ghost" size="sm" onPress={testPrint} aria-label="以当前密度试打测试条">
              <ScrollText size={15} aria-hidden />
              试打测试条
            </Button>
          </div>
          <SwitchLine
            label="断线自动重连"
            checked={draft.printer.auto_reconnect}
            onChange={(v) => set("printer", { auto_reconnect: v })}
          />
        </Section>

        {/* 天气 */}
        <Section icon={CloudSun} title="天气">
          <div className="mb-1.5">
            <Label>数据源</Label>
          </div>
          <div className="mb-4 flex gap-2" role="radiogroup" aria-label="天气数据源">
            {([["caiyun", "彩云天气"], ["qweather", "和风天气"], ["openmeteo", "Open-Meteo"]] as const).map(([v, label]) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={draft.weather.provider === v}
                onClick={() => set("weather", { provider: v })}
                className={[
                  "rounded-full border px-4 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary",
                  draft.weather.provider === v
                    ? "border-primary bg-primary/10 font-medium text-primary"
                    : "border-default-300 text-foreground/70 hover:bg-default-100",
                ].join(" ")}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {draft.weather.provider === "caiyun" && (
              <Field
                label="彩云天气 API Key"
                hint="免费注册: caiyunapp.com"
                extra={<Configured flag={snap.weather.has_caiyun_key} />}
              >
                <Input type="password" value={draft.weather.caiyun_api_key} onChange={(e) => set("weather", { caiyun_api_key: e.target.value })}
                  placeholder={snap.weather.has_caiyun_key ? "已配置，留空保持不变" : "输入彩云天气 API Key"} autoComplete="off" />
              </Field>
            )}
            {draft.weather.provider === "qweather" && (
              <>
                <Field label="和风天气 API Key" hint="免费注册: dev.qweather.com" extra={<Configured flag={snap.weather.has_weather_key} />}>
                  <Input type="password" value={draft.weather.weather_api_key} onChange={(e) => set("weather", { weather_api_key: e.target.value })}
                    placeholder={snap.weather.has_weather_key ? "已配置，留空保持不变" : "输入和风天气 Key"} autoComplete="off" />
                </Field>
                <Field label="和风天气城市 ID" hint="如 beijing 或 101010100">
                  <Input value={draft.weather.weather_city} onChange={(e) => set("weather", { weather_city: e.target.value })} />
                </Field>
              </>
            )}
            <Field label="纬度" hint="如 22.5000">
              <Input value={draft.weather.weather_latitude} onChange={(e) => set("weather", { weather_latitude: e.target.value })}
                placeholder={snap.weather.latitude != null ? String(snap.weather.latitude) : "22.5000"} />
            </Field>
            <Field label="经度" hint="如 114.0000">
              <Input value={draft.weather.weather_longitude} onChange={(e) => set("weather", { weather_longitude: e.target.value })}
                placeholder={snap.weather.longitude != null ? String(snap.weather.longitude) : "114.0000"} />
            </Field>
            <Field label="显示地名">
              <Input value={draft.weather.weather_location_name} onChange={(e) => set("weather", { weather_location_name: e.target.value })} />
            </Field>
          </div>
        </Section>

        {/* 温度曲线数据源 */}
        <Section icon={Database} title="温度曲线数据源">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="HA 地址" hint="如 http://homeassistant.local:8123">
              <Input value={draft.temp.ha_url} onChange={(e) => set("temp", { ha_url: e.target.value })} spellCheck={false} />
            </Field>
            <Field label="长期访问令牌" extra={<Configured flag={snap.temp.has_token} />}>
              <Input type="password" value={draft.temp.ha_token} onChange={(e) => set("temp", { ha_token: e.target.value })}
                placeholder={snap.temp.has_token ? "已配置，留空保持不变" : "粘贴长期访问令牌"} autoComplete="off" />
            </Field>
            <Field label="温度实体 ID" hint="如 sensor.xxx_temperature">
              <Input value={draft.temp.entity_id} onChange={(e) => set("temp", { entity_id: e.target.value })} spellCheck={false} />
            </Field>
          </div>
        </Section>

        {/* 定时任务 */}
        <Section icon={Clock3} title="定时任务">
          <ScheduleRow
            title="每日天气"
            enabled={draft.schedule.weatherEnabled}
            time={draft.schedule.weatherTime}
            next={snap.schedule.weather.next_run_time}
            onEnabled={(v) => set("schedule", { weatherEnabled: v })}
            onTime={(v) => set("schedule", { weatherTime: v })}
          />
          <ScheduleRow
            title="每日温度曲线"
            enabled={draft.schedule.tempEnabled}
            time={draft.schedule.tempTime}
            next={snap.schedule.temp.next_run_time}
            onEnabled={(v) => set("schedule", { tempEnabled: v })}
            onTime={(v) => set("schedule", { tempTime: v })}
          />
        </Section>

        {/* 通知 */}
        <Section icon={Bell} title="通知" desc="打印失败时推送到 Bark">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Bark 推送 URL" hint="从 Bark App 首页复制" extra={<Configured flag={snap.notify.has_bark_url} />}>
              <div className="flex gap-2">
                <Input type="password" value={draft.notify.barkUrl} onChange={(e) => set("notify", { barkUrl: e.target.value, barkCleared: false })}
                  placeholder={snap.notify.has_bark_url ? "已配置，留空保持不变" : "https://api.day.app/你的Key"} autoComplete="off" />
                {snap.notify.has_bark_url && (
                  <Button variant="ghost" isIconOnly size="sm" aria-label="清除 Bark URL"
                    onPress={() => set("notify", { barkCleared: true, barkUrl: "" })}>
                    <Trash2 size={15} aria-hidden />
                  </Button>
                )}
              </div>
            </Field>
            <Field label="推送分组">
              <Input value={draft.notify.barkGroup} onChange={(e) => set("notify", { barkGroup: e.target.value })} />
            </Field>
          </div>
        </Section>

        {/* 设备信息 */}
        <Section
          icon={BatteryCharging}
          title="设备信息"
          extra={
            <Button variant="ghost" size="sm" onPress={refreshDevice} isPending={deviceLoading} aria-label="刷新设备信息">
              {!deviceLoading && <RefreshCw size={15} aria-hidden />}
              刷新
            </Button>
          }
        >
          <div className="grid gap-4 sm:grid-cols-4">
            <InfoTile title="连接状态" value={device?.connected ? "已连接" : device ? "未连接" : "查询中…"} />
            <InfoTile title="电池" value={pick(device?.battery, "battery") || (device?.connected ? "未获取" : "—")} />
            <InfoTile title="SN" value={pick(device?.sn, "sn") || (device?.connected ? "未获取" : "—")} />
            <InfoTile title="硬件信息" value={pick(device?.hardware, "hardware") || (device?.connected ? "未获取" : "—")} />
          </div>
        </Section>
      </div>

      <SaveBar visible={dirty} saving={saving} onSave={saveAll} onReset={reset} />

      {/* 未保存修改拦截确认 */}
      <Modal state={guardState}>
        <Modal.Backdrop />
        <Modal.Container>
          <Modal.Dialog>
            <Modal.Header>
              <Modal.Heading>有未保存的修改</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <p className="text-sm text-foreground/70">
                离开当前页面将丢失未保存的设置修改，确定离开吗？
              </p>
            </Modal.Body>
            <Modal.Footer>
              <Button
                variant="ghost"
                onPress={() => {
                  guardState.close();
                  if (blocker && blocker.state === "blocked") blocker.reset();
                }}
              >
                留下继续编辑
              </Button>
              <Button
                variant="danger-soft"
                onPress={() => {
                  guardState.close();
                  if (snap) setDraft(toDraft(snap)); // 放弃修改,恢复为已保存状态
                  if (blocker && blocker.state === "blocked") blocker.proceed();
                }}
              >
                放弃修改并离开
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal>
    </>
  );
}

// ---------- 草稿模型 ----------

interface Draft {
  printer: { serial_port: string; baudrate: string; width: string; density: string; bt_mac: string; auto_reconnect: boolean };
  weather: {
    provider: SettingsSnapshot["weather"]["provider"];
    caiyun_api_key: string;
    weather_api_key: string;
    weather_city: string;
    weather_latitude: string;
    weather_longitude: string;
    weather_location_name: string;
  };
  temp: { ha_url: string; ha_token: string; entity_id: string };
  schedule: { weatherEnabled: boolean; weatherTime: string; tempEnabled: boolean; tempTime: string };
  notify: { barkUrl: string; barkGroup: string; barkCleared: boolean };
}

function toDraft(s: SettingsSnapshot): Draft {
  return {
    printer: {
      serial_port: s.printer.serial_port,
      baudrate: String(s.printer.baudrate),
      width: String(s.printer.width),
      density: String(s.printer.density),
      bt_mac: s.printer.bt_mac,
      auto_reconnect: s.printer.auto_reconnect,
    },
    weather: {
      provider: s.weather.provider,
      caiyun_api_key: "",
      weather_api_key: "",
      weather_city: s.weather.city,
      weather_latitude: s.weather.latitude != null ? String(s.weather.latitude) : "",
      weather_longitude: s.weather.longitude != null ? String(s.weather.longitude) : "",
      weather_location_name: s.weather.location_name,
    },
    temp: { ha_url: s.temp.ha_url, ha_token: "", entity_id: s.temp.entity_id },
    schedule: {
      weatherEnabled: s.schedule.weather.enabled,
      weatherTime: s.schedule.weather.print_time,
      tempEnabled: s.schedule.temp.enabled,
      tempTime: s.schedule.temp.print_time,
    },
    notify: { barkUrl: "", barkGroup: s.notify.bark_group, barkCleared: false },
  };
}

function num(v: string): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

// ---------- 展示组件 ----------

function Section({ icon: Icon, title, desc, extra, children }: {
  icon: typeof PrinterIcon;
  title: string;
  desc?: string;
  extra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-large border border-default-200 bg-content1 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-medium bg-primary/10 text-primary">
            <Icon size={17} aria-hidden />
          </div>
          <h2 className="shrink-0 text-[15px] font-semibold">{title}</h2>
          {desc ? (
            <p className="truncate text-xs text-foreground/55">{desc}</p>
          ) : null}
        </div>
        {extra}
      </div>
      {children}
    </section>
  );
}

function Field({ label, hint, extra, children }: {
  label: string;
  hint?: string;
  extra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <TextField fullWidth className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        {extra}
      </div>
      {children}
      {hint ? <span className="text-xs text-foreground/45">{hint}</span> : null}
    </TextField>
  );
}

function Configured({ flag }: { flag: boolean }) {
  if (!flag) return null;
  return (
    <Chip color="success" variant="soft" size="sm">
      已配置
    </Chip>
  );
}

function SwitchLine({ label, checked, onChange }: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between border-t border-default-100 pt-4">
      <span className="text-sm">{label}</span>
      <Switch isSelected={checked} onChange={onChange} aria-label={label}>
        <Switch.Content>
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch.Content>
      </Switch>
    </div>
  );
}

function ScheduleRow({ title, enabled, time, next, onEnabled, onTime }: {
  title: string;
  enabled: boolean;
  time: string;
  next: string | null;
  onEnabled: (v: boolean) => void;
  onTime: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-default-100 py-4 first:border-t-0 first:pt-0">
      <Switch isSelected={enabled} onChange={onEnabled} aria-label={`${title}开关`}>
        <Switch.Content>
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
          <span className="text-sm">{title}</span>
        </Switch.Content>
      </Switch>
      <input
        type="time"
        value={time}
        onChange={(e) => onTime(e.target.value)}
        disabled={!enabled}
        className="h-9 rounded-medium border border-default-300 bg-content1 px-2.5 text-sm disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-primary"
        aria-label={`${title}打印时间`}
      />
      <span className="text-xs text-foreground/50">
        {enabled
          ? next
            ? `下次执行: ${new Date(next).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}`
            : "保存后生效"
          : "已暂停"}
      </span>
    </div>
  );
}

function InfoTile({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-medium bg-default-100/60 p-3.5">
      <div className="text-xs text-foreground/50">{title}</div>
      <div className="mt-1 text-sm font-medium break-all">{value}</div>
    </div>
  );
}

function pick(d: Record<string, unknown> | null | undefined, key: string): string {
  const v = d?.[key];
  return v == null ? "" : String(v);
}
