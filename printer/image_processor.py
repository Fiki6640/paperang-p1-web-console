#!/usr/bin/python3
# -*-coding:utf-8 -*-
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageEnhance, ImageDraw, ImageFont
import os


def _pack_block(bits_str: str) -> bytes:
    if len(bits_str) % 8 != 0:
        raise ValueError("bits_str should have the length of multiple of 8")
    partitioned_str = [bits_str[i:i + 8] for i in range(0, len(bits_str), 8)]
    int_str = [int(i, 2) for i in partitioned_str]
    return bytes(int_str)


def binimage2bitstream(bin_image: np.ndarray):
    assert bin_image.max() <= 1 and bin_image.min() >= 0
    return _pack_block(''.join(map(str, bin_image.flatten())))


def im2binimage_threshold(im, width=384):
    if len(im.shape) != 2:
        im = np.array(Image.fromarray(im).convert('L'))
    img = Image.fromarray(im).convert('L')
    wpercent = (width / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((width, hsize), Image.LANCZOS)
    img_array = np.array(img)
    threshold = np.mean(img_array)
    ret = (img_array < threshold).astype(int)
    ret = ret[::-1, ::-1]
    return ret


def dither_atkinson(num, thresh=127):
    derr = np.zeros(num.shape, dtype=float)
    div = 8
    for y in range(num.shape[0]):
        for x in range(num.shape[1]):
            newval = derr[y, x] + float(num[y, x])
            if newval >= thresh:
                errval = newval - 255.0
                num[y, x] = 1.0
            else:
                errval = newval
                num[y, x] = 0.0
            if x + 1 < num.shape[1]:
                derr[y, x + 1] += errval / div
                if x + 2 < num.shape[1]:
                    derr[y, x + 2] += errval / div
            if y + 1 < num.shape[0]:
                if x - 1 >= 0:
                    derr[y + 1, x - 1] += errval / div
                derr[y + 1, x] += errval / div
                if x + 1 < num.shape[1]:
                    derr[y + 1, x + 1] += errval / div
                if y + 2 < num.shape[0]:
                    derr[y + 2, x] += errval / div
    return num * 255


def im2binimage_dither(image_path, width=384):
    img = Image.open(image_path).convert('L')
    wpercent = (width / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((width, hsize), Image.LANCZOS)
    m = np.array(img).astype(float)
    m2 = dither_atkinson(m)
    out = Image.fromarray(m2[::-1, ::-1].astype(np.uint8))
    enhancer = ImageEnhance.Contrast(out)
    enhanced_img = enhancer.enhance(4.0)
    np_img = np.array(enhanced_img).astype(int)
    np_img[np_img > 0] = 1
    np_img = 1 - np_img
    return binimage2bitstream(np_img)


def text_to_image(text, width=384, font_size=24, line_spacing=8):
    # 网页表单提交的换行是 \r\n,只按 \n 拆行会让 \r 留在行尾被字体画成可见字形
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 其余控制字符同样没有可打印字形,一并剔除(保留 \t)
    text = ''.join(ch for ch in text if ch >= ' ' or ch in '\n\t')
    lines = text.split('\n')
    font = None
    try:
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/truetype/lxgw/LXGWWenKai-Medium.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                break
    except Exception:
        pass
    if font is None:
        font = ImageFont.load_default()
    line_height = font_size + line_spacing
    total_height = len(lines) * line_height + 20
    img = Image.new('L', (width, total_height), color=255)
    draw = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        draw.text((10, y), line, fill=0, font=font)
        y += line_height
    return img


def text_to_bitstream(text, width=384, font_size=24, line_spacing=8, conversion="threshold"):
    img = text_to_image(text, width, font_size, line_spacing)
    if conversion == "threshold":
        img_array = np.array(img)
        bin_img = (img_array < 128).astype(int)
        bin_img = bin_img[::-1, ::-1]
        return binimage2bitstream(bin_img)
    else:
        raise ValueError("Unsupported conversion method")


class ImageProcessor:
    def __init__(self, width=384):
        self.width = width

    def image_file_to_bitstream(self, image_path, method="dither"):
        if method == "dither":
            return im2binimage_dither(image_path, self.width)
        elif method == "threshold":
            img = Image.open(image_path)
            img_array = np.array(img)
            bin_img = im2binimage_threshold(img_array, self.width)
            return binimage2bitstream(bin_img)
        else:
            raise ValueError("Unsupported method: %s" % method)

    def text_to_bitstream(self, text, font_size=24, line_spacing=8):
        return text_to_bitstream(text, self.width, font_size, line_spacing)

    def text_to_image(self, text, font_size=24, line_spacing=8):
        return text_to_image(text, self.width, font_size, line_spacing)
