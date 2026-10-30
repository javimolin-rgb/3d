#!/usr/bin/env python3
"""Genera un video estilo dron de Casa Cipres a partir de renders y planos.

Uso: python3 drone_video.py <carpeta_fuentes> <salida.mp4>

La carpeta de fuentes debe contener los archivos descargados de Drive
(Render_N.png, Axonometrica_Casa_Cipres.png y planta-1.png, que es la
planta "Sin Cotas" rasterizada con `pdftoppm -r 100 -png`).
"""
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
FADE = 0.9  # segundos de fundido entre tomas
FONT_THIN = "/usr/share/fonts/opentype/inter/Inter-Thin.otf"
FONT_LIGHT = "/usr/share/fonts/opentype/inter/Inter-Light.otf"
FONT_REG = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)


def load(path, bg=None, pad=0.0, max_w=None):
    im = Image.open(path)
    if im.mode == "RGBA" or bg is not None:
        im = im.convert("RGBA")
        base = Image.new("RGBA", im.size, bg or (255, 255, 255, 255))
        im = Image.alpha_composite(base, im)
    im = im.convert("RGB")
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if pad:
        pw, ph = int(im.width * pad), int(im.height * pad)
        canvas = Image.new("RGB", (im.width + 2 * pw, im.height + 2 * ph), bg[:3] if bg else (255, 255, 255))
        canvas.paste(im, (pw, ph))
        im = canvas
    return im


class Shot:
    """Una toma: imagen + trayectoria de cámara entre dos keyframes.

    Cámara: (cx, cy) centro normalizado, z = zoom sobre el encuadre que
    cubre la pantalla, r = giro en grados.
    """

    def __init__(self, img, dur, a, b, caption=None, clamp=True, drift=1.0):
        self.img, self.dur, self.a, self.b = img, dur, a, b
        self.caption, self.clamp, self.drift = caption, clamp, drift
        # renders: cubren la pantalla; planos: caben completos
        fit = max if clamp else min
        self.cover = fit(W / img.width, H / img.height)

    def frame(self, t, seed):
        k = ease(t / self.dur)
        cx, cy, z, r = (p + (q - p) * k for p, q in zip(self.a, self.b))
        # deriva lenta tipo dron (pequeñas oscilaciones de baja frecuencia)
        d = self.drift
        cx += d * 0.004 * math.sin(0.7 * t + seed)
        cy += d * 0.003 * math.sin(0.53 * t + 2 * seed)
        r += d * 0.35 * math.sin(0.41 * t + 3 * seed)
        iw, ih = self.img.size
        th = math.radians(r)
        s = self.cover * z
        if self.clamp:
            # zoom extra para que el giro no muestre los bordes
            ac, asn = abs(math.cos(th)), abs(math.sin(th))
            bw, bh = W * ac + H * asn, W * asn + H * ac
            s = max(s, bw / iw, bh / ih)
            hw, hh = bw / (2 * s), bh / (2 * s)
            px = min(max(cx * iw, hw), iw - hw)
            py = min(max(cy * ih, hh), ih - hh)
        else:
            px, py = cx * iw, cy * ih
        c, sn = math.cos(th) / s, math.sin(th) / s
        a0, b0 = c, sn
        d0, e0 = -sn, c
        data = (a0, b0, px - a0 * W / 2 - b0 * H / 2,
                d0, e0, py - d0 * W / 2 - e0 * H / 2)
        fill = self.img.getpixel((2, 2))
        return self.img.transform((W, H), Image.AFFINE, data, Image.BICUBIC, fillcolor=fill)


def text_layer(lines, backdrop=None):
    """lines: lista de (texto, fuente, tamaño, y, tracking, alineación)."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl, ds = ImageDraw.Draw(layer), ImageDraw.Draw(shadow)
    for txt, font, size, y, track, align in lines:
        f = ImageFont.truetype(font, size)
        widths = [f.getlength(ch) for ch in txt]
        total = sum(widths) + track * (len(txt) - 1)
        x = (W - total) / 2 if align == "c" else 110
        for ch, w in zip(txt, widths):
            dl.text((x, y), ch, font=f, fill=(255, 255, 255, 255))
            ds.text((x, y), ch, font=f, fill=(0, 0, 0, 150))
            x += w + track
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    out = Image.alpha_composite(shadow, layer)
    if backdrop is not None:
        out = Image.alpha_composite(backdrop, out)
    return out


def backdrop(kind):
    """Oscurecimiento suave detrás del texto para que se lea sobre los renders."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if kind == "center":
        a = np.exp(-(((xx - W / 2) / (W * 0.38)) ** 2 + ((yy - H / 2) / (H * 0.22)) ** 2)) * 0.55
    else:
        a = np.clip((yy - H * 0.72) / (H * 0.28), 0, 1) ** 1.5 * 0.6
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def caption_layer(txt):
    return text_layer([(txt.upper(), FONT_REG, 32, H - 120, 6, "l")], backdrop("bottom"))


def overlay(frame, layer, alpha):
    if alpha <= 0:
        return frame
    a = np.asarray(layer, dtype=np.float32)
    rgb, al = a[..., :3], a[..., 3:] / 255.0 * alpha
    return frame * (1 - al) + rgb * al


def main(src, out):
    R = {i: load(f"{src}/Render_{i}.png") for i in (1, 3, 5, 6, 7, 8)}
    planta = load(f"{src}/planta-1.png", bg=(255, 255, 255, 255), max_w=2400)
    # recorte de la planta del 1er piso (incluye terraza y porch)
    pw, ph = planta.size
    planta1 = planta.crop((int(0.07 * pw), int(0.27 * ph), int(0.49 * pw), int(0.76 * ph)))
    axo = load(f"{src}/Axonometrica_Casa_Cipres.png", bg=(255, 255, 255, 255), pad=0.25)

    shots = [
        # Apertura: el dron baja y se acerca a la casa entre los árboles nevados
        Shot(R[3], 7.5, (0.40, 0.18, 1.55, -2.0), (0.62, 0.52, 1.05, 0.5)),
        # Barrido lateral frente a la terraza al atardecer
        Shot(R[7], 6.0, (0.70, 0.50, 1.25, 1.2), (0.35, 0.48, 1.12, -0.8), "Terraza · Fachada principal"),
        # Acercamiento hacia el ventanal ...
        Shot(R[5], 5.0, (0.45, 0.52, 1.00, 0.0), (0.40, 0.60, 1.70, -1.0)),
        # ... y entramos al estar / cocina, elevándonos hacia el altillo
        Shot(R[6], 6.5, (0.45, 0.70, 1.55, 1.0), (0.55, 0.42, 1.05, 0.0), "Estar · Cocina · Doble altura"),
        # Living del segundo piso
        Shot(R[8], 5.5, (0.30, 0.45, 1.25, 0.0), (0.62, 0.52, 1.10, 0.6), "Living · 2do piso"),
        Shot(R[1], 5.0, (0.40, 0.55, 1.05, -0.4), (0.58, 0.48, 1.30, 0.4)),
        # Vista cenital sobre la planta
        Shot(planta1, 6.5, (0.50, 0.50, 0.85, 8.0), (0.50, 0.52, 1.30, 0.0), "Planta 1er piso", clamp=False, drift=0.3),
        # Volumetría
        Shot(axo, 5.0, (0.48, 0.50, 1.00, 0.0), (0.52, 0.48, 1.18, 0.0), "Volumetría", clamp=False, drift=0.3),
        # Cierre: el dron se aleja y sube sobre la fachada
        Shot(R[5], 7.0, (0.38, 0.62, 1.45, 0.8), (0.50, 0.40, 1.02, -0.5)),
    ]

    starts, t = [], 0.0
    for s in shots:
        starts.append(t)
        t += s.dur - FADE
    total = t + FADE
    nframes = int(total * FPS)

    title = text_layer([
        ("CASA CIPRES", FONT_THIN, 120, H / 2 - 100, 28, "c"),
        ("N E O R I G E N  ·  V I V E   L O   N A T U R A L", FONT_LIGHT, 28, H / 2 + 60, 4, "c"),
    ], backdrop("center"))
    captions = {i: caption_layer(s.caption) for i, s in enumerate(shots) if s.caption}

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
    vignette = (1 - 0.28 * np.clip(rr - 0.25, 0, 1.5) / 1.5)[..., None]

    ff = subprocess.Popen([
        "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", out,
    ], stdin=subprocess.PIPE)

    for n in range(nframes):
        t = n / FPS
        acc, wsum = None, 0.0
        for i, (s, st) in enumerate(zip(shots, starts)):
            lt = t - st
            if lt < 0 or lt > s.dur:
                continue
            w = 1.0
            if i > 0 and lt < FADE:
                w = ease(lt / FADE)
            fr = np.asarray(s.frame(lt, seed=i * 1.7), dtype=np.float32)
            if s.caption:
                ca = min(1.0, (lt - 0.6) / 0.8, (s.dur - FADE - 0.3 - lt) / 0.6)
                fr = overlay(fr, captions[i], ca)
            acc = fr if acc is None else acc * (1 - w) + fr * w
        f = acc * vignette
        # títulos de apertura y cierre
        a = min((t - 1.2) / 1.2, (6.0 - t) / 1.0)
        a = max(a, min((t - (total - 5.0)) / 1.5, (total - 0.6 - t) / 0.8))
        f = overlay(f, title, max(0.0, min(1.0, a)))
        # fundido desde/hacia negro
        f *= min(1.0, t / 1.0, (total - t) / 1.2)
        ff.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
        if n % 150 == 0:
            print(f"{n}/{nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"OK {out} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
