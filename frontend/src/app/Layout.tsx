/**
 * 全局布局:
 * - 顶部 App Bar:产品名 + 蓝牙状态胶囊 + 暗色切换(全端)
 * - 桌面 lg+:左侧竖向 Sidebar;移动端:底部 Tab Bar,当前项 primary-soft 底
 */
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import {
  CloudSun,
  House,
  Image as ImageIcon,
  Moon,
  Monitor,
  Printer,
  Settings as SettingsIcon,
  Sun,
  Thermometer,
  Type,
} from "lucide-react";
import { Chip } from "@heroui/react";
import { useStatus } from "../lib/status";
import { getStoredTheme, setTheme, watchSystemTheme, type ThemeChoice } from "../lib/theme";
import type { LucideIcon } from "lucide-react";

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/", label: "首页", icon: House, end: true },
  { to: "/text-print", label: "文本打印", icon: Type },
  { to: "/image-print", label: "图片打印", icon: ImageIcon },
  { to: "/weather", label: "天气", icon: CloudSun },
  { to: "/temp-chart", label: "温度曲线", icon: Thermometer },
  { to: "/settings", label: "设置", icon: SettingsIcon },
];

function navClass(isActive: boolean): string {
  return [
    "flex items-center gap-3 rounded-medium px-3 py-2.5 text-sm font-medium transition-colors",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
    isActive
      ? "bg-primary/10 text-primary"
      : "text-foreground/70 hover:bg-default-100 hover:text-foreground",
  ].join(" ");
}

function StatusChipInner() {
  const { status } = useStatus();
  const state = status?.bt.state ?? "unknown";
  const label = state === "online" ? "在线" : state === "offline" ? "离线" : "未知";
  const color = state === "online" ? "success" : state === "offline" ? "danger" : "default";
  return (
    <Chip color={color} variant="soft" size="sm" aria-label={`打印机蓝牙${label}`}>
      <span className="flex items-center gap-1.5">
        <Printer size={13} aria-hidden />
        {label}
      </span>
    </Chip>
  );
}

function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(() => getStoredTheme());
  useEffect(() => watchSystemTheme(), []);
  const next: Record<ThemeChoice, ThemeChoice> = { light: "dark", dark: "system", system: "light" };
  const Icon = choice === "light" ? Sun : choice === "dark" ? Moon : Monitor;
  const title = { light: "浅色模式", dark: "深色模式", system: "跟随系统" }[choice];
  return (
    <button
      type="button"
      aria-label={`切换主题（当前${title}）`}
      title={`${title}，点击切换`}
      onClick={() => {
        const n = next[choice];
        setChoice(n);
        setTheme(n);
      }}
      className="flex size-9 items-center justify-center rounded-medium text-foreground/70 hover:bg-default-100 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      <Icon size={18} aria-hidden />
    </button>
  );
}

function AppBar() {
  const { pathname } = useLocation();
  const title =
    NAV.find((n) => (n.end ? pathname === n.to : pathname.startsWith(n.to)))?.label ?? "首页";
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-default-200 bg-content1/90 px-4 backdrop-blur">
      {/* 页面标题在顶栏左上角(原品牌位);品牌在 Sidebar 与标签页 title */}
      <h1 className="text-base font-semibold tracking-tight">{title}</h1>
      <div className="ml-auto flex items-center gap-2">
        <StatusChipInner />
        <ThemeToggle />
      </div>
    </header>
  );
}

export default function Layout() {
  return (
    <div className="min-h-dvh">
      <div className="lg:flex">
        {/* 桌面 Sidebar */}
        <aside className="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col border-r border-default-200 bg-content1 px-3 py-4 lg:flex">
          <div className="mb-4 flex items-center gap-2 px-2">
            <div className="flex size-7 items-center justify-center rounded-medium bg-primary text-primary-foreground">
              <Printer size={16} aria-hidden />
            </div>
            <span className="text-sm font-semibold tracking-tight">Paperang P1</span>
          </div>
          <nav className="flex flex-col gap-1" aria-label="主导航">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => navClass(isActive)}>
                <Icon size={17} aria-hidden />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <AppBar />
          <main className="mx-auto w-full max-w-4xl flex-1 px-4 pt-5 pb-24 sm:px-6 lg:pb-10">
            <Outlet />
          </main>
        </div>
      </div>

      {/* 移动端底部 Tab Bar */}
      <nav
        className="fixed inset-x-0 bottom-0 z-20 flex border-t border-default-200 bg-content1/95 backdrop-blur lg:hidden"
        aria-label="底部导航"
      >
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium",
                "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary",
                isActive ? "text-primary" : "text-foreground/60",
              ].join(" ")
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`flex size-8 items-center justify-center rounded-full ${isActive ? "bg-primary/10" : ""}`}
                >
                  <Icon size={19} aria-hidden />
                </span>
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
