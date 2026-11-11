import { useState } from "react";
import { Link } from "react-router";
import { Button, Card } from "@heroui/react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  CloudSun,
  FileText,
  Image as ImageIcon,
  Thermometer,
  ScrollText,
  RefreshCw,
} from "lucide-react";
import { api, showError, showToast } from "../lib/api";
import { useStatus } from "../lib/status";
import type { LucideIcon } from "lucide-react";

const FEATURES: { to: string; title: string; desc: string; icon: LucideIcon }[] = [
  { to: "/text-print", title: "文本打印", desc: "输入文字，实时预览热敏排版后打印", icon: FileText },
  { to: "/image-print", title: "图片打印", desc: "拖拽上传，支持抖动 / 阈值二值化", icon: ImageIcon },
  { to: "/weather", title: "今日天气", desc: "生成天气卡片并打印，可定时推送", icon: CloudSun },
  { to: "/temp-chart", title: "温度曲线", desc: "Home Assistant 历史温度一日一图", icon: Thermometer },
];

export default function Home() {
  const { status, btOnline, refresh } = useStatus();
  const [pending, setPending] = useState<string | null>(null);

  const run = async (key: string, fn: () => Promise<Parameters<typeof showToast>[0]>) => {
    setPending(key);
    try {
      showToast(await fn());
    } catch (e) {
      showError(e);
    } finally {
      setPending(null);
      refresh();
    }
  };

  const disabled = !btOnline;
  const hint = (key: string) => (pending === key ? true : disabled);

  return (
    <>
      

      <div className="grid gap-4 sm:grid-cols-2">
        {FEATURES.map(({ to, title, desc, icon: Icon }) => (
          <Link key={to} to={to} className="group focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary" aria-label={title}>
            <Card className="transition-transform duration-200 group-hover:-translate-y-0.5">
              <div className="flex items-start gap-3.5 p-5">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-medium bg-primary/10 text-primary">
                  <Icon size={20} aria-hidden />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="text-[15px] font-semibold">{title}</h2>
                  <p className="mt-1 text-sm text-foreground/60">{desc}</p>
                </div>
                <ArrowRight size={17} className="mt-1 shrink-0 text-foreground/30 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" aria-hidden />
              </div>
            </Card>
          </Link>
        ))}
      </div>

      <h2 className="mb-3 mt-7 text-sm font-semibold text-foreground/70">快捷操作</h2>
      <div className="flex flex-wrap gap-2">
        <Button variant="ghost" isDisabled={hint("self-test")} onPress={() => run("self-test", api.selfTest)}>
          {pending === "self-test" ? <Activity className="animate-spin" size={15} aria-hidden /> : <ScrollText size={15} aria-hidden />}
          自检
        </Button>
        <Button variant="ghost" isDisabled={hint("feed")} onPress={() => run("feed", api.feed)}>
          {pending === "feed" ? <Activity className="animate-spin" size={15} aria-hidden /> : <ArrowDownToLine size={15} aria-hidden />}
          走纸
        </Button>
        <Button variant="ghost" isDisabled={pending !== null} onPress={() => run("reconnect", api.reconnect)}>
          <RefreshCw size={15} className={pending === "reconnect" ? "animate-spin" : ""} aria-hidden />
          重连
        </Button>
        <Button
          variant="ghost"
          isDisabled={pending !== null}
          onPress={() =>
            run("status", async () => {
              const s = await api.status();
              const btText = s.bt.state === "online" ? "在线" : s.bt.state === "offline" ? "离线" : "未知";
              return {
                success: true,
                severity: s.bt.state === "offline" ? "warning" : "info",
                message: `串口 ${s.port} 已${s.connected ? "打开" : "未连接"}，蓝牙${btText}${s.bt.detail ? `（${s.bt.detail}）` : ""}`,
              };
            })
          }
        >
          <Activity size={15} aria-hidden />
          状态
        </Button>
      </div>
      <p className="mt-3 text-xs text-foreground/50">
        {disabled
          ? "打印机蓝牙不在线，打印操作已禁用"
          : `串口 ${status?.port ?? "-"} · ${status?.baudrate ?? "-"} 波特 · 宽度 ${status?.width ?? "-"}px`}
      </p>
    </>
  );
}
