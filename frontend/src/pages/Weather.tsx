import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Button, Card, Skeleton } from "@heroui/react";
import { CloudSun, Droplets, Gauge, Printer, Sunrise, Sunset, Timer, Wind } from "lucide-react";
import PageHeader from "../components/PageHeader";
import { api, showError, showToast, weatherPreviewUrl, type WeatherData } from "../lib/api";
import { useStatus } from "../lib/status";

/** 今日天气:数据卡片 + 打印预览;定时打印在「设置」页配置 */
export default function Weather() {
  const { btOnline } = useStatus();
  const navigate = useNavigate();
  const [data, setData] = useState<WeatherData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [bust, setBust] = useState(() => Date.now()); // 预览防缓存

  useEffect(() => {
    api
      .weatherData()
      .then((d) => setData(d))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const print = async () => {
    if (sending) return;
    setSending(true);
    try {
      showToast(await api.printWeather());
    } catch (e) {
      showError(e);
    } finally {
      setSending(false);
    }
  };

  const stats = data
    ? [
        { icon: Droplets, label: "湿度", value: `${data.humidity ?? "-"}%` },
        { icon: Wind, label: "风力", value: `${data.windDir ?? ""} ${data.windScale ?? "-"} 级` },
        { icon: Gauge, label: "气压", value: `${data.pressure ?? "-"}` },
        { icon: Sunrise, label: "日出", value: data.sunrise ?? "-" },
        { icon: Sunset, label: "日落", value: data.sunset ?? "-" },
      ]
    : [];

  return (
    <>
      <PageHeader
        actions={
          <Button variant="ghost" size="sm" onPress={() => navigate("/settings")}>
            <Timer size={15} aria-hidden />
            定时设置
          </Button>
        }
      />

      {error ? (
        <Card className="p-5 text-sm text-danger">{error}</Card>
      ) : !data ? (
        <div className="flex flex-wrap gap-4">
          <Skeleton className="h-28 w-full rounded-large" />
          <Skeleton className="h-20 w-full rounded-large" />
        </div>
      ) : (
        <>
          <Card>
            <div className="flex flex-wrap items-center gap-x-8 gap-y-4 p-5">
              <div className="flex items-center gap-3">
                <CloudSun size={40} className="text-primary" aria-hidden />
                <div>
                  <div className="text-3xl font-semibold tracking-tight">
                    {data.temp ?? "-"}°
                  </div>
                  <div className="text-sm text-foreground/60">
                    {data.city} · {data.text}
                  </div>
                </div>
              </div>
              <div className="text-sm text-foreground/70">
                体感 {data.feelsLike ?? "-"}° · 最高 {data.temp_max ?? "-"}° · 最低 {data.temp_min ?? "-"}°
              </div>
            </div>
          </Card>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {stats.map(({ icon: Icon, label, value }) => (
              <Card key={label} className="p-3.5">
                <Icon size={16} className="text-foreground/50" aria-hidden />
                <div className="mt-2 text-sm font-medium">{value}</div>
                <div className="text-xs text-foreground/50">{label}</div>
              </Card>
            ))}
          </div>
        </>
      )}

      <h2 className="mb-3 mt-7 text-sm font-semibold text-foreground/70">打印预览</h2>
      <div className="grid min-w-0 grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_384px]">
        <div>
          <Button onPress={print} isDisabled={!btOnline} isPending={sending}>
            {!sending && <Printer size={16} aria-hidden />}
            打印天气卡片
          </Button>
          {!btOnline && <p className="mt-3 text-sm text-danger">打印机蓝牙不在线，无法打印</p>}
        </div>
        <div className="mx-auto w-[384px] min-w-0 max-w-full">
          <img
            key={bust}
            src={`${weatherPreviewUrl}?t=${bust}`}
            alt="天气卡片打印预览"
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
  );
}
