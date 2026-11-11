import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Button, ToggleButton, ToggleButtonGroup } from "@heroui/react";
import { Database, Printer } from "lucide-react";
import PageHeader from "../components/PageHeader";
import { api, showError, showToast, tempPreviewUrl, type SettingsSnapshot } from "../lib/api";
import { useStatus } from "../lib/status";

/** 温度曲线:HA 历史温度一日一图(服务端渲染 PNG);数据源与定时在「设置」页配置 */
export default function TempChart() {
  const { btOnline } = useStatus();
  const navigate = useNavigate();
  const [daysAgo, setDaysAgo] = useState(1);
  const [sending, setSending] = useState(false);
  const [bust, setBust] = useState(() => Date.now());
  const [settings, setSettings] = useState<SettingsSnapshot | null>(null);

  useEffect(() => {
    api.settings().then(setSettings).catch(() => {});
  }, []);

  const configured = !!(settings?.temp.ha_url && settings?.temp.has_token);

  const print = async () => {
    if (sending) return;
    setSending(true);
    try {
      showToast(await api.tempPrint(daysAgo));
    } catch (e) {
      showError(e);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <PageHeader
        actions={
          <Button variant="ghost" size="sm" onPress={() => navigate("/settings")}>
            <Database size={15} aria-hidden />
            设置
          </Button>
        }
      />

      {!settings ? null : !configured ? (
        <div className="rounded-large border border-default-200 bg-content1 p-8 text-center">
          <Database size={28} className="mx-auto text-foreground/30" aria-hidden />
          <p className="mt-3 text-sm font-medium">尚未配置 Home Assistant 数据源</p>
          <p className="mt-1 text-sm text-foreground/60">需要 HA 地址、长期访问令牌与温度实体 ID。</p>
          <Button size="sm" className="mt-4" onPress={() => navigate("/settings")}>
            去设置
          </Button>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <ToggleButtonGroup
              disallowEmptySelection
              selectedKeys={new Set([String(daysAgo)])}
              onSelectionChange={(keys) => {
                const v = Number([...keys][0]);
                if (!Number.isNaN(v)) setDaysAgo(v);
              }}
              aria-label="选择日期"
            >
              <ToggleButton key="1" id="1">昨天</ToggleButton>
              <ToggleButton key="0" id="0">今天</ToggleButton>
            </ToggleButtonGroup>
            <span className="text-xs text-foreground/50">
              定时打印{settings.schedule.temp.enabled ? `已开启，每日 ${settings.schedule.temp.print_time}` : "未开启"}
              {settings.schedule.temp.next_run_time
                ? ` · 下次 ${new Date(settings.schedule.temp.next_run_time).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}`
                : ""}
            </span>
          </div>

          <div className="mt-5 flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <Button onPress={print} isDisabled={!btOnline} isPending={sending}>
                {!sending && <Printer size={16} aria-hidden />}
                打印曲线（原生 {settings.printer.width}px 竖版）
              </Button>
              {!btOnline && <p className="text-sm text-danger">打印机蓝牙不在线，无法打印</p>}
            </div>
            <div className="min-w-0">
              <img
                key={`${daysAgo}-${bust}`}
                src={`${tempPreviewUrl(daysAgo)}&t=${bust}`}
                alt={`温度曲线预览（${daysAgo === 0 ? "今天" : "昨天"}）`}
                className="w-full rounded-small border border-default-200 shadow-small dark:border-default-100"
              />
              <button
                type="button"
                onClick={() => setBust(Date.now())}
                className="mt-2 w-full text-center text-xs text-foreground/40 hover:text-foreground/60"
              >
                刷新预览
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
}
