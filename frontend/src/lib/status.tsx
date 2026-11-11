/**
 * 打印机状态轮询(30s,与旧 base.html 行为一致),Provider 全局共享,
 * 顶栏 StatusChip 与页面按钮禁用逻辑都读这里。
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, type PrinterStatus } from "./api";

interface StatusCtx {
  status: PrinterStatus | null;
  btOnline: boolean;
  refresh: () => void;
}

const Ctx = createContext<StatusCtx>({ status: null, btOnline: false, refresh: () => {} });

export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<PrinterStatus | null>(null);

  const refresh = useCallback(() => {
    api.status().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 30_000);
    return () => clearInterval(t);
  }, [refresh]);

  const btOnline = status?.bt.state === "online" || (status?.bt.state !== "offline" && status?.connected === true);
  return <Ctx.Provider value={{ status, btOnline, refresh }}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useStatus() {
  return useContext(Ctx);
}
