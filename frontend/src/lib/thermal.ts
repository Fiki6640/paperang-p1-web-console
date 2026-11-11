import { useLayoutEffect, useRef, useState } from "react";

/**
 * 热敏纸文本预览模型。
 * 后端用 LXGW WenKai 渲染:CJK 字形宽 ≈ 1em,ASCII ≈ 0.5em。
 * 这里按同一模型在客户端做确定性换行(不让浏览器 CSS 自行折行,
 * 否则预览换行与真实打印不一致)。
 */

export const PAPER_WIDTH = 384; // 点

/** 一行文本的显示宽度(em 单位) */
export function lineWidthEm(line: string): number {
  let w = 0;
  for (const ch of line) {
    w += ch.charCodeAt(0) > 0x2e80 ? 1 : 0.5;
  }
  return w;
}

/** 按宽度模型把文本切成物理行(硬换行 + 超宽折行) */
export function wrapText(text: string, fontSize: number): string[] {
  const maxUnits = PAPER_WIDTH / fontSize; // 每行可容纳的"单位"(CJK=1)
  const out: string[] = [];
  for (const raw of text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")) {
    if (raw === "") {
      out.push("");
      continue;
    }
    let line = "";
    let w = 0;
    for (const ch of raw) {
      const cw = ch.charCodeAt(0) > 0x2e80 ? 1 : 0.5;
      if (w + cw > maxUnits && line !== "") {
        out.push(line);
        line = ch;
        w = cw;
      } else {
        line += ch;
        w += cw;
      }
    }
    out.push(line);
  }
  return out;
}

/** 行高(点) = 字号 + 行距 */
export function lineHeightDots(fontSize: number, lineSpacing: number): number {
  return fontSize + lineSpacing;
}

/** 预览总高度(点) → 用于纸张容器高度 */
export function previewHeightDots(lines: number, fontSize: number, lineSpacing: number): number {
  return Math.max(1, lines) * lineHeightDots(fontSize, lineSpacing) + 16; // 上下留白
}

/**
 * 预览纸自适应缩放:容器窄于设计宽度(384px)时按比例 zoom,
 * zoom 会影响布局尺寸,无需手动补偿高度(Chromium/Safari/Firefox 126+ 均支持)。
 */
export function useFitZoom(designWidth: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setZoom(Math.min(1, el.clientWidth / designWidth));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [designWidth]);
  return { ref, zoom };
}
