/**
 * 图片处理 Worker:为预览复刻后端 image_processor 的二值化效果。
 * - threshold: 全局阈值(与后端 im2binimage_threshold 的 128 阈值一致)
 * - dither:    Atkinson 抖动(与后端 dither_atkinson 一致,6/8 扩散)
 */

export interface DitherRequest {
  id: number;
  bitmap: ImageBitmap;
  width: number; // 目标宽度(打印机 384)
  method: "dither" | "threshold";
}

export interface DitherResponse {
  id: number;
  width: number;
  height: number;
  data: Uint8ClampedArray<ArrayBuffer>; // RGBA
}

function grayscale(img: ImageData): Float64Array {
  const { width, height, data } = img;
  const out = new Float64Array(width * height);
  for (let i = 0; i < out.length; i++) {
    const r = data[i * 4]!;
    const g = data[i * 4 + 1]!;
    const b = data[i * 4 + 2]!;
    out[i] = 0.299 * r + 0.587 * g + 0.114 * b;
  }
  return out;
}

function renderBinary(pixels: Float64Array, w: number, h: number): Uint8ClampedArray<ArrayBuffer> {
  const out = new Uint8ClampedArray(new ArrayBuffer(w * h * 4));
  for (let i = 0; i < pixels.length; i++) {
    const v = pixels[i]! > 128 ? 255 : 0;
    out[i * 4] = v;
    out[i * 4 + 1] = v;
    out[i * 4 + 2] = v;
    out[i * 4 + 3] = 255;
  }
  return out;
}

function threshold(img: ImageData): Float64Array {
  return grayscale(img); // >128 为白
}

/** Atkinson 抖动:误差只扩散 1/8 给 6 个邻居 */
function atkinson(img: ImageData): Float64Array {
  const px = grayscale(img);
  const w = img.width;
  const h = img.height;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const old = px[i]!;
      const newV = old > 128 ? 255 : 0;
      const err = (old - newV) / 8;
      px[i] = newV;
      const spread = (nx: number, ny: number) => {
        if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
          px[ny * w + nx] = (px[ny * w + nx] as number) + err;
        }
      };
      spread(x + 1, y);
      spread(x + 2, y);
      spread(x - 1, y + 1);
      spread(x, y + 1);
      spread(x + 1, y + 1);
      spread(x, y + 2);
    }
  }
  return px;
}

self.onmessage = async (e: MessageEvent<DitherRequest>) => {
  const { id, bitmap, width, method } = e.data;
  // 等比缩放到目标宽度
  const scale = width / bitmap.width;
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const off = new OffscreenCanvas(width, height);
  const ctx = off.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0, width, height);
  const img = ctx.getImageData(0, 0, width, height);

  const pixels = method === "dither" ? atkinson(img) : threshold(img);
  const data = renderBinary(pixels, width, height);
  bitmap.close();
  const resp: DitherResponse = { id, width, height, data };
  self.postMessage(resp);
};
