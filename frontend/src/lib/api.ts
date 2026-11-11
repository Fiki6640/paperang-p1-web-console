/**
 * 类型化 API 客户端。
 * 后端包络: {success, error?, message?, severity?, field?} + 合理 HTTP 状态码。
 * 所有请求同源(Flask 或 Vite dev proxy),无外部依赖。
 */
import { toast } from "@heroui/react";

export type Severity = "success" | "error" | "warning" | "info";

export interface ApiEnvelope {
  success: boolean;
  error?: string;
  message?: string;
  severity?: Severity;
  field?: string;
}

export class ApiError extends Error {
  field?: string;
  status: number;
  constructor(message: string, status: number, field?: string) {
    super(message);
    this.status = status;
    this.field = field;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, init);
  } catch {
    throw new ApiError("网络请求失败，请检查服务是否在线", 0);
  }
  // 204/空响应;非 JSON 响应(如 Flask 的 HTML 错误页)不炸解析,给出可读错误
  const text = await resp.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      if (!resp.ok) {
        throw new ApiError(`请求失败 (HTTP ${resp.status})`, resp.status);
      }
      throw new ApiError("服务返回了无法解析的响应", resp.status);
    }
  }
  if (!resp.ok) {
    throw new ApiError(
      (data.error as string) ?? `请求失败 (HTTP ${resp.status})`,
      resp.status,
      data.field as string | undefined,
    );
  }
  return data as T;
}

function post(path: string, body?: unknown): Promise<ApiEnvelope> {
  return request(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// ---------- 类型 ----------

export type BtState = "online" | "offline" | "unknown";

export interface PrinterStatus {
  connected: boolean;
  port: string;
  baudrate: number;
  width: number;
  density?: number;
  bt: { state: BtState; name?: string; detail?: string; checked_at?: string };
}

export interface JobSnapshot {
  enabled: boolean;
  print_time: string;
  next_run_time: string | null;
}

export interface SettingsSnapshot {
  printer: {
    serial_port: string;
    baudrate: number;
    width: number;
    density: number;
    bt_mac: string;
    auto_reconnect: boolean;
  };
  weather: {
    provider: "caiyun" | "qweather" | "openmeteo";
    has_caiyun_key: boolean;
    has_weather_key: boolean;
    city: string;
    latitude: number | null;
    longitude: number | null;
    location_name: string;
  };
  temp: { ha_url: string; has_token: boolean; entity_id: string };
  schedule: { weather: JobSnapshot; temp: JobSnapshot };
  notify: { has_bark_url: boolean; bark_group: string };
}

export interface WeatherData {
  city?: string;
  temp?: number | string;
  text?: string;
  feelsLike?: number | string;
  temp_max?: number | string;
  temp_min?: number | string;
  humidity?: number | string;
  windScale?: number | string;
  windDir?: string;
  pressure?: number | string;
  sunrise?: string;
  sunset?: string;
}

export interface DeviceInfo {
  connected: boolean;
  battery: Record<string, unknown> | null;
  sn: Record<string, unknown> | null;
  hardware: Record<string, unknown> | null;
}

// ---------- 接口 ----------

export const api = {
  status: (): Promise<PrinterStatus> => request("/api/v1/status"),
  deviceInfo: (): Promise<DeviceInfo> => request("/api/v1/device-info"),

  settings: (): Promise<SettingsSnapshot> => request("/api/v1/settings"),
  savePrinter: (d: Partial<SettingsSnapshot["printer"]>) => post("/api/v1/settings/printer", d),
  saveWeather: (d: Record<string, unknown>) => post("/api/v1/settings/weather", d),
  saveTemp: (d: Record<string, unknown>) => post("/api/v1/settings/temp", d),
  saveSchedule: (d: Record<string, unknown>) => post("/api/v1/settings/schedule", d),
  saveNotify: (d: Record<string, unknown>) => post("/api/v1/settings/notify", d),

  printText: (text: string, fontSize: number, lineSpacing: number) =>
    post("/api/v1/print/text", { text, font_size: fontSize, line_spacing: lineSpacing }),
  printImage: (file: File, method: "dither" | "threshold") => {
    const form = new FormData();
    form.append("image", file);
    form.append("method", method);
    return request<ApiEnvelope>("/api/v1/print/image", { method: "POST", body: form });
  },
  printWeather: () => post("/api/v1/print/weather"),
  weatherData: (): Promise<WeatherData> => request("/api/v1/weather/data"),

  feed: () => post("/api/v1/feed", { length: 100 }),
  selfTest: () => post("/api/v1/self-test"),
  reconnect: () => post("/api/v1/reconnect"),
  setDensity: (density: number) => post("/api/v1/density", { density }),

  tempPrint: (daysAgo: number) => post("/api/v1/temp-chart/print", { days_ago: daysAgo }),
};

export const weatherPreviewUrl = "/api/v1/weather/preview";
export const tempPreviewUrl = (daysAgo: number) =>
  `/api/v1/temp-chart/preview?days_ago=${daysAgo}`;

// ---------- Toast / 动作助手 ----------

export function showToast(env: ApiEnvelope) {
  const msg = env.message ?? env.error ?? (env.success ? "操作成功" : "操作失败");
  const sev = env.severity ?? (env.success ? "success" : "error");
  switch (sev) {
    case "success":
      toast.success(msg, { timeout: 3000 });
      break;
    case "info":
      toast.info(msg, { timeout: 5000 });
      break;
    case "warning":
      toast.warning(msg, { timeout: 8000 });
      break;
    default:
      // 常驻(timeout 0 = 不自动消失,右上角自带关闭按钮)
      toast.danger(msg, { timeout: 0 });
  }
}

/** API 错误(网络/4xx/5xx) → 错误 Toast;返回 false 便于调用方短路 */
export function showError(e: unknown): false {
  toast.danger(e instanceof Error ? e.message : String(e), { timeout: 0 });
  return false;
}
