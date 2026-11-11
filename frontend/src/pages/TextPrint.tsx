import { useMemo, useState } from "react";
import { Button, Label, TextArea, TextField, ToggleButton, ToggleButtonGroup } from "@heroui/react";
import { Printer, Trash2 } from "lucide-react";
import { api, showError, showToast } from "../lib/api";
import { useStatus } from "../lib/status";
import {
  PAPER_WIDTH,
  previewHeightDots,
  useFitZoom,
  wrapText,
} from "../lib/thermal";

const FONT_SIZES = [16, 20, 24, 32];
const LINE_SPACINGS = [4, 8, 12];

/**
 * 文本打印:左侧输入(自适应高度 + 字号/行距分段选择),
 * 右侧 384px 热敏纸实时预览(按后端同款换行模型渲染)。
 */
export default function TextPrint() {
  const { btOnline } = useStatus();
  const [text, setText] = useState("");
  const [fontSize, setFontSize] = useState(20);
  const [lineSpacing, setLineSpacing] = useState(8);
  const [sending, setSending] = useState(false);
  const { ref: paperWrapRef, zoom } = useFitZoom(PAPER_WIDTH + 24); // 容器含内边距

  const lines = useMemo(() => wrapText(text, fontSize), [text, fontSize]);
  const paperHeight = previewHeightDots(lines.length, fontSize, lineSpacing);

  const disabled = !btOnline || text.trim() === "";

  const print = async () => {
    if (sending) return;
    setSending(true);
    try {
      showToast(await api.printText(text, fontSize, lineSpacing));
    } catch (e) {
      showError(e);
    } finally {
      setSending(false);
    }
  };

  return (
    <>

      <div className="grid min-w-0 grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_384px]">
        <div className="flex min-w-0 flex-col gap-5">
          <TextField fullWidth value={text} onChange={(v) => setText(v)} className="flex flex-col gap-2">
            <Label>打印内容</Label>
            <TextArea placeholder="输入要打印的文字…" className="min-h-40 resize-y" aria-label="打印内容" />
          </TextField>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-foreground/50">字号</span>
              <ToggleButtonGroup
                disallowEmptySelection
                selectedKeys={new Set([String(fontSize)])}
                onSelectionChange={(keys) => {
                  const v = Number([...keys][0]);
                  if (v) setFontSize(v);
                }}
                aria-label="字号"
              >
                {FONT_SIZES.map((s) => (
                  <ToggleButton key={String(s)} id={String(s)} aria-label={`字号 ${s}`}>
                    {s}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-foreground/50">行距</span>
              <ToggleButtonGroup
                disallowEmptySelection
                selectedKeys={new Set([String(lineSpacing)])}
                onSelectionChange={(keys) => {
                  const v = Number([...keys][0]);
                  if (!Number.isNaN(v)) setLineSpacing(v);
                }}
                aria-label="行距"
              >
                {LINE_SPACINGS.map((s) => (
                  <ToggleButton key={String(s)} id={String(s)} aria-label={`行距 ${s}`}>
                    {s}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onPress={print} isDisabled={disabled} isPending={sending}>
              {!sending && <Printer size={16} aria-hidden />}
              {sending ? "发送中…" : "打印"}
            </Button>
            <Button
              variant="ghost"
              onPress={() => setText("")}
              isDisabled={text === "" || sending}
              aria-label="清空内容"
            >
              <Trash2 size={16} aria-hidden />
              清空
            </Button>
            <span className="text-xs text-foreground/50">
              {text.length} 字 · 预计 {lines.length} 行 · 纸高 {Math.ceil(paperHeight / 8)}mm
            </span>
          </div>
          {!btOnline && <p className="text-sm text-danger">打印机蓝牙不在线，无法打印</p>}
        </div>

        {/* 热敏纸预览:1 点 = 1 px,384px 宽纸张,窄屏自动缩放 */}
        <div ref={paperWrapRef} className="mx-auto w-full min-w-0">
          <div
            className="mx-auto w-[384px] thermal-paper rounded-small border border-default-200 px-3 py-2 shadow-small dark:border-default-100"
            style={{ minHeight: 240, zoom: zoom === 1 ? undefined : zoom }}
            aria-label="热敏纸打印预览"
            role="img"
          >
            {lines.length === 1 && lines[0] === "" ? (
              <div className="flex h-[220px] items-center justify-center text-xs text-neutral-400">
                预览区
              </div>
            ) : (
              <div
                style={{
                  fontSize: fontSize,
                  lineHeight: `${fontSize + lineSpacing}px`,
                }}
              >
                {lines.map((line, i) => (
                  <div key={i} className="whitespace-pre">
                    {line || "\u00A0"}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
