import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@heroui/react";
import { ImagePlus, Printer, X } from "lucide-react";
import { api, showError, showToast } from "../lib/api";
import { useStatus } from "../lib/status";
import { PAPER_WIDTH, useFitZoom } from "../lib/thermal";
import type { DitherRequest, DitherResponse } from "../lib/dither.worker";

type Method = "dither" | "threshold";

const METHODS: { key: Method; title: string; desc: string }[] = [
  { key: "dither", title: "抖动 (推荐)", desc: "Atkinson 抖动，照片类图片层次更好" },
  { key: "threshold", title: "阈值", desc: "黑白二值，文字/线条类更锐利" },
];

/**
 * 图片打印:拖拽上传 + 缩略图,二值化方式二选一,
 * Worker 实时渲染处理后效果(与后端 image_processor 同款算法)。
 */
export default function ImagePrint() {
  const { btOnline, status } = useStatus();
  const width = status?.width ?? 384;
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null); // 原图 objectURL
  const [method, setMethod] = useState<Method>("dither");
  const [sending, setSending] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const { ref: paperWrapRef, zoom } = useFitZoom(PAPER_WIDTH + 16);
  const inputRef = useRef<HTMLInputElement>(null);
  const workerRef = useRef<Worker | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Worker 生命周期
  useEffect(() => {
    workerRef.current = new Worker(new URL("../lib/dither.worker.ts", import.meta.url), { type: "module" });
    const w = workerRef.current;
    w.onmessage = (e: MessageEvent<DitherResponse>) => {
      const { data, width: w2, height } = e.data;
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = w2;
      canvas.height = height;
      canvas.getContext("2d")!.putImageData(new ImageData(data, w2, height), 0, 0);
    };
    return () => {
      w.terminate();
      workerRef.current = null;
    };
  }, []);

  const renderPreview = useCallback(
    (f: File, m: Method) => {
      const w = workerRef.current;
      if (!w) return;
      createImageBitmap(f)
        .then((bitmap) => {
          const req: DitherRequest = { id: Date.now(), bitmap, width, method: m };
          w.postMessage(req);
        })
        .catch(() => {});
    },
    [width],
  );

  const accept = useCallback(
    (f: File | undefined | null) => {
      if (!f || !f.type.startsWith("image/")) return;
      setFile(f);
      if (preview) URL.revokeObjectURL(preview);
      setPreview(URL.createObjectURL(f));
      renderPreview(f, method);
    },
    [preview, method, renderPreview],
  );

  // 切换二值化方式时重新渲染
  useEffect(() => {
    if (file) renderPreview(file, method);
  }, [method, file, renderPreview]);

  const print = async () => {
    if (!file || sending) return;
    setSending(true);
    try {
      showToast(await api.printImage(file, method));
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
          {/* 拖拽区 / 缩略图 */}
          {file ? (
            <div className="relative overflow-hidden rounded-large border border-default-200 bg-content1">
              <img src={preview!} alt="已选图片" className="max-h-56 w-full object-contain" />
              <button
                type="button"
                aria-label="移除图片"
                className="absolute top-2 right-2 flex size-8 items-center justify-center rounded-full bg-background/80 text-foreground shadow-small hover:bg-background focus-visible:outline-2 focus-visible:outline-primary"
                onClick={() => {
                  setFile(null);
                  if (preview) URL.revokeObjectURL(preview);
                  setPreview(null);
                }}
              >
                <X size={15} aria-hidden />
              </button>
              <p className="border-t border-default-200 px-4 py-2 text-xs text-foreground/50">
                {file.name} · {(file.size / 1024).toFixed(0)} KB
              </p>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                accept(e.dataTransfer.files?.[0]);
              }}
              className={[
                "flex flex-col items-center justify-center gap-2 rounded-large border-2 border-dashed px-6 py-12 transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                dragOver ? "border-primary bg-primary/5" : "border-default-300 hover:border-default-400",
              ].join(" ")}
            >
              <ImagePlus size={32} className="text-foreground/40" aria-hidden />
              <span className="text-sm font-medium">点击选择或拖拽图片到这里</span>
              <span className="text-xs text-foreground/50">支持 PNG / JPG / WebP</span>
            </button>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => accept(e.target.files?.[0])}
          />

          {/* 二值化方式:二选一卡片 */}
          <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="二值化方式">
            {METHODS.map((m) => (
              <button
                key={m.key}
                type="button"
                role="radio"
                aria-checked={method === m.key}
                onClick={() => setMethod(m.key)}
                className={[
                  "rounded-large border bg-content1 p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                  method === m.key
                    ? "border-primary ring-1 ring-primary"
                    : "border-default-200 opacity-70 hover:opacity-100",
                ].join(" ")}
              >
                <h3 className="text-sm font-semibold">{m.title}</h3>
                <p className="mt-1 text-xs text-foreground/60">{m.desc}</p>
              </button>
            ))}
          </div>

          <Button onPress={print} isDisabled={!file || !btOnline} isPending={sending} className="self-start">
            {!sending && <Printer size={16} aria-hidden />}
            {sending ? "发送中…" : "打印"}
          </Button>
          {!btOnline && <p className="text-sm text-danger">打印机蓝牙不在线，无法打印</p>}
        </div>

        {/* 处理效果预览 */}
        <div ref={paperWrapRef} className="mx-auto w-full min-w-0">
          <div
            className="mx-auto w-[384px] thermal-paper flex min-h-[240px] items-center justify-center rounded-small border border-default-200 p-2 shadow-small dark:border-default-100"
            style={{ zoom: zoom === 1 ? undefined : zoom }}
          >
            <canvas ref={canvasRef} className={file ? "max-w-full" : "hidden"} aria-label="二值化效果预览" role="img" />
            {!file && <span className="text-xs text-neutral-400">预览区</span>}
          </div>
        </div>
      </div>
    </>
  );
}
