#!/usr/bin/env python3
"""Historia vertical (9:16) de "modelo destacado": Casa Lingue de Neorigen.

Uso: python3 historia_lingue.py <carpeta_tomas> <salida.mp4>

La carpeta tiene, por cada toma, el render y su pase de profundidad normalizado
(0 = cámara, blanco = 90 m), tal como los deja casa_lingue_3d.py:

  python casa_lingue_3d.py -- --vista apertura --still 1 --res 1080x1920 \
      --samples 48 --out tomas/apertura.png --prof tomas/apertura_z

El pase de profundidad es lo que permite las transiciones en tres dimensiones:
cada gráfico tiene una distancia en metros y se dibuja sólo donde la escena está
más lejos, así los textos entran por detrás de la casa, pasan entre ella y el
pasto, y salen por delante del primer plano.
"""
import glob
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FADE = 0.7            # fundido entre tomas
DEPTH_MAX = 90.0      # metros que abarca el pase de profundidad
SOFT = 0.30           # suavizado del borde de oclusión, en metros

INTER = "/usr/share/fonts/opentype/inter/{}.otf"
BLANCO = (247, 245, 241)
MADERA = (214, 158, 92)
NEGRO = (12, 12, 13)

# Datos del modelo publicados en neorigen.cl (línea Fundadores).
MODELO = {
    "nombre": "LINGUE",
    "linea": "LÍNEA FUNDADORES",
    "destacado": "MODELO DESTACADO",
    "superficie": "25 m²",
    "superficie_pie": "SUPERFICIE ÚTIL",
    "terraza": "+ TERRAZA 3 m²",
    "terraza_opc": "OPCIÓN 6 m²",
    "programa": ["1 DORMITORIO", "1 BAÑO", "ESTAR · COCINA · COMEDOR"],
    "eficiencia_t": "EFICIENCIA ENERGÉTICA",
    "eficiencia": ["AISLACIÓN TÉRMICA", "PANELES FOTOVOLTAICOS"],
    "plazo": "4 MESES",
    "plazo_pie": "DE CONSTRUCCIÓN",
    "entrega": ["LLAVE EN MANO", "SE CONSTRUYE EN TU TERRENO", "ESCALABLE Y PERSONALIZABLE"],
    "marca": "NEORIGEN",
    "sitio": "NEORIGEN.CL",
    "claim": "VIVE LO NATURAL",
}


# ------------------------------------------------------------- utilidades
def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)


def lerp(a, b, k):
    return a + (b - a) * k


def fuente(nombre, size):
    return ImageFont.truetype(INTER.format(nombre), size)


# --------------------------------------------------------------- gráficos
def sprite_texto(txt, peso, size, track=0, color=BLANCO, sombra=0.5):
    """Texto con tracking amplio (estética de la marca) y sombra suave."""
    f = fuente(peso, size)
    anchos = [f.getlength(c) for c in txt]
    total = sum(anchos) + track * max(len(txt) - 1, 0)
    asc, desc = f.getmetrics()
    blur = max(6, size // 10)
    pad = blur * 3
    im = Image.new("RGBA", (int(total) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    x = pad
    for c, a in zip(txt, anchos):
        d.text((x, pad), c, font=f, fill=(*color, 255))
        ds.text((x, pad + size * 0.04), c, font=f, fill=(0, 0, 0, int(255 * sombra)))
        x += a + track
    if sombra:
        im = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)), im)
    return im.crop(im.getbbox())


def sprite_linea(largo, grosor=3, color=BLANCO, sombra=0.45):
    im = Image.new("RGBA", (int(largo) + 24, grosor + 24), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle((12, 12, 12 + largo, 12 + grosor), fill=(*color, 255))
    ImageDraw.Draw(sh).rectangle((12, 14, 12 + largo, 14 + grosor), fill=(0, 0, 0, int(255 * sombra)))
    return Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)), im)


def sprite_dato(txt, size=34, track=7, pad=(36, 22)):
    """Etiqueta de dato: píldora translúcida con borde claro."""
    f = fuente("Inter-Medium", size)
    anchos = [f.getlength(c) for c in txt]
    total = sum(anchos) + track * max(len(txt) - 1, 0)
    asc, desc = f.getmetrics()
    w, h = int(total) + 2 * pad[0], asc + desc + 2 * pad[1]
    im = Image.new("RGBA", (w + 28, h + 28), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    caja = (14, 14, 14 + w, 14 + h)
    d.rounded_rectangle(caja, radius=h // 2, fill=(12, 12, 13, 125), outline=(*BLANCO, 110), width=2)
    x = 14 + pad[0]
    for c, a in zip(txt, anchos):
        d.text((x, 14 + pad[1]), c, font=f, fill=(*BLANCO, 255))
        x += a + track
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((caja[0], caja[1] + 4, caja[2], caja[3] + 4),
                                         radius=h // 2, fill=(0, 0, 0, 120))
    return Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)), im)


def sprite_panel(ancho, alto, fuerza=0.42):
    """Sombra suave detrás de un bloque de texto, para que se lea sobre el campo."""
    yy, xx = np.mgrid[0:int(alto), 0:int(ancho)].astype(np.float32)
    a = np.exp(-(((xx - ancho / 2) / (ancho * 0.42)) ** 2 +
                 ((yy - alto / 2) / (alto * 0.42)) ** 2)) * fuerza
    arr = np.zeros((int(alto), int(ancho), 4), np.uint8)
    arr[..., :3] = NEGRO
    arr[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


class Grafico:
    """Capa que viaja por la escena a una distancia dada de la cámara.

    `a` y `b` son (x, y, escala) con x e y en fracción del cuadro (centro del
    gráfico); `z` y `z1` son la distancia en metros al inicio y al final: si la
    escena está más cerca que el gráfico, lo tapa. Con z=None va siempre delante.
    """

    def __init__(self, sprite, t0, t1, a, b, z=None, z1=None, fade=(0.5, 0.5)):
        self.sp, self.t0, self.t1, self.a, self.b = sprite, t0, t1, a, b
        self.z, self.z1 = z, z if z1 is None else z1
        self.fade = fade

    def componer(self, frame, dep, t):
        if not (self.t0 - 0.001 <= t <= self.t1 + 0.001):
            return
        fin, fout = self.fade
        al = min(1.0, (t - self.t0) / fin if fin else 1.0,
                 (self.t1 - t) / fout if fout else 1.0)
        if al <= 0.004:
            return
        k = ease((t - self.t0) / (self.t1 - self.t0))
        x, y = lerp(self.a[0], self.b[0], k) * W, lerp(self.a[1], self.b[1], k) * H
        s = lerp(self.a[2], self.b[2], k)
        sp = self.sp if abs(s - 1) < 0.01 else self.sp.resize(
            (max(1, int(self.sp.width * s)), max(1, int(self.sp.height * s))), Image.LANCZOS)
        x0, y0 = int(x - sp.width / 2), int(y - sp.height / 2)
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x0 + sp.width), min(H, y0 + sp.height)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        rec = np.asarray(sp, dtype=np.float32)[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
        a = rec[..., 3:] / 255.0 * al
        if self.z is not None:
            zt = lerp(self.z, self.z1, k)
            vis = np.clip((dep[cy0:cy1, cx0:cx1, None] - zt) / SOFT + 0.5, 0, 1)
            a = a * vis
        sub = frame[cy0:cy1, cx0:cx1]
        sub *= 1 - a
        sub += rec[..., :3] * a


# ----------------------------------------------------------------- tomas
class Toma:
    """Un render con su pase de profundidad y un movimiento lento de cámara.

    `a` y `b` son (cx, cy, zoom) al principio y al final del recorrido.
    """

    def __init__(self, nombre, carpeta, dur, a, b):
        self.nombre, self.dur, self.a, self.b = nombre, dur, a, b
        self.img = Image.open(f"{carpeta}/{nombre}.png").convert("RGB")
        z = sorted(glob.glob(f"{carpeta}/{nombre}_z*.png"))
        if not z:
            raise SystemExit(f"falta el pase de profundidad de '{nombre}' en {carpeta}")
        dep = np.asarray(Image.open(z[0]).convert("I"), dtype=np.float32)
        dep = dep / 65535.0 * DEPTH_MAX
        dep[dep <= 0] = DEPTH_MAX
        self.dep = Image.fromarray(dep, "F")
        self.cover = max(W / self.img.width, H / self.img.height)
        self.graficos = []
        self.inicio = 0.0

    def g(self, *args, **kw):
        self.graficos.append(Grafico(*args, **kw))
        return self.graficos[-1]

    def _warp(self, im, cx, cy, s, resample):
        iw, ih = im.size
        hw, hh = W / (2 * s), H / (2 * s)
        px = min(max(cx * iw, hw), iw - hw)
        py = min(max(cy * ih, hh), ih - hh)
        data = (1 / s, 0, px - W / (2 * s), 0, 1 / s, py - H / (2 * s))
        return im.transform((W, H), Image.AFFINE, data, resample)

    def frame(self, t):
        k = ease(t / self.dur)
        cx, cy, z = (lerp(p, q, k) for p, q in zip(self.a, self.b))
        s = self.cover * z
        rgb = np.asarray(self._warp(self.img, cx, cy, s, Image.BICUBIC), dtype=np.float32)
        dep = np.asarray(self._warp(self.dep, cx, cy, s, Image.BILINEAR), dtype=np.float32)
        return rgb.copy(), dep


# ------------------------------------------------------------- la historia
def construir(carpeta):
    """Las seis tomas de la historia, con la coreografía de cada gráfico.

    Las distancias (z) salen del pase de profundidad de cada toma: en la
    apertura la casa está a unos 16 m y el pasto del frente a 5-9 m, así que un
    texto a 20 m queda tapado por la casa y a 6 m pasa por delante de ella.
    """
    M = MODELO
    T = []

    # 1. Apertura: el nombre del modelo nace detrás de la casa y avanza hacia el frente.
    t1 = Toma("apertura", carpeta, 6.4, (0.50, 0.47, 1.16), (0.50, 0.50, 1.06))
    t1.g(sprite_texto(M["marca"], "Inter-Light", 40, 22), 0.2, 6.4,
         (0.5, 0.075, 1.0), (0.5, 0.075, 1.0), fade=(0.8, 0.6))
    t1.g(sprite_linea(150, 2), 0.6, 6.4, (0.5, 0.115, 1.0), (0.5, 0.115, 1.0), fade=(1.0, 0.6))
    t1.g(sprite_texto(M["nombre"], "InterDisplay-Thin", 230, 22), 0.5, 5.9,
         (0.50, 0.455, 0.34), (0.50, 0.615, 1.00), z=20.0, z1=6.5, fade=(0.5, 0.6))
    t1.g(sprite_panel(900, 300), 2.3, 5.9, (0.5, 0.73, 1.0), (0.5, 0.73, 1.0),
         z=3.5, fade=(1.0, 0.6))
    t1.g(sprite_texto(M["destacado"], "Inter-Light", 38, 18, MADERA), 2.5, 5.9,
         (0.50, 0.715, 1.0), (0.50, 0.705, 1.0), z=3.5, fade=(0.9, 0.6))
    t1.g(sprite_texto(M["linea"], "Inter-Regular", 28, 14), 3.1, 5.9,
         (0.50, 0.762, 1.0), (0.50, 0.755, 1.0), z=3.5, fade=(0.9, 0.6))
    T.append(t1)

    # 2. Superficie: el número cruza el cuadro pasando por detrás de la casa.
    t2 = Toma("superficie", carpeta, 5.8, (0.46, 0.50, 1.02), (0.54, 0.48, 1.10))
    t2.g(sprite_panel(950, 330), 2.0, 5.3, (0.5, 0.825, 1.0), (0.5, 0.825, 1.0),
         z=3.5, fade=(1.0, 0.5))
    # el número viaja por la franja del cielo: el techo de la casa lo tapa al pasar
    t2.g(sprite_texto(M["superficie"], "InterDisplay-Thin", 260, 10), 0.1, 5.3,
         (1.30, 0.285, 1.0), (0.39, 0.285, 1.0), z=12.0, fade=(0.4, 0.5))
    t2.g(sprite_texto(M["superficie_pie"], "Inter-Regular", 28, 14, MADERA), 2.7, 5.3,
         (0.39, 0.368, 1.0), (0.39, 0.363, 1.0), z=3.5, fade=(0.8, 0.5))
    t2.g(sprite_texto(M["terraza"], "Inter-ExtraLight", 70, 8), 2.2, 5.3,
         (-0.32, 0.80, 1.0), (0.50, 0.80, 1.0), z=3.5, fade=(0.4, 0.5))
    t2.g(sprite_texto(M["terraza_opc"], "Inter-Light", 28, 12), 3.4, 5.3,
         (0.50, 0.848, 1.0), (0.50, 0.848, 1.0), z=3.5, fade=(0.8, 0.5))
    T.append(t2)

    # 3. Programa: las etiquetas salen desde detrás del marco negro del ventanal.
    t3 = Toma("interior", carpeta, 5.6, (0.50, 0.52, 1.10), (0.50, 0.50, 1.00))
    for i, dato in enumerate(M["programa"]):  # salen desde detrás del marco negro
        t3.g(sprite_dato(dato), 0.6 + i * 0.7, 5.1, (0.14, 0.425 + i * 0.085, 1.0),
             (0.50, 0.425 + i * 0.085, 1.0), z=6.0, z1=3.5, fade=(0.5, 0.5))
    T.append(t3)

    # 4. Eficiencia: una línea viaja por detrás de la casa, de un costado al otro.
    t4 = Toma("eficiencia", carpeta, 5.4, (0.50, 0.46, 1.04), (0.52, 0.52, 1.00))
    t4.g(sprite_linea(900, 4), 0.2, 5.0, (-0.45, 0.47, 1.0), (1.45, 0.47, 1.0),
         z=9.6, fade=(0.4, 0.4))
    t4.g(sprite_panel(1000, 260, 0.45), 0.4, 4.9, (0.5, 0.30, 1.0), (0.5, 0.30, 1.0),
         z=3.5, fade=(0.9, 0.5))
    t4.g(sprite_texto(M["eficiencia_t"], "Inter-ExtraLight", 56, 10), 0.5, 4.9,
         (0.50, 0.305, 1.0), (0.50, 0.298, 1.0), z=3.5, fade=(0.7, 0.5))
    for i, dato in enumerate(M["eficiencia"]):
        t4.g(sprite_dato(dato), 1.6 + i * 0.7, 4.9, (0.50, 0.765 + i * 0.085, 1.0),
             (0.50, 0.76 + i * 0.085, 1.0), z=3.5, fade=(0.6, 0.5))
    T.append(t4)

    # 5. Plazo y entrega: el plazo también asoma desde detrás de la casa.
    t5 = Toma("acceso", carpeta, 5.4, (0.52, 0.50, 1.00), (0.46, 0.50, 1.06))
    t5.g(sprite_texto(M["plazo"], "InterDisplay-Thin", 200, 10), 0.2, 4.9,
         (0.50, 0.31, 0.78), (0.50, 0.345, 1.0), z=12.5, z1=5.0, fade=(0.5, 0.5))
    t5.g(sprite_texto(M["plazo_pie"], "Inter-Regular", 28, 14, MADERA), 1.6, 4.9,
         (0.50, 0.425, 1.0), (0.50, 0.42, 1.0), z=3.5, fade=(0.8, 0.5))
    for i, dato in enumerate(M["entrega"]):
        t5.g(sprite_dato(dato, 30), 1.9 + i * 0.55, 4.9, (0.50, 0.705 + i * 0.082, 1.0),
             (0.50, 0.70 + i * 0.082, 1.0), z=3.5, fade=(0.6, 0.5))
    T.append(t5)

    # 6. Cierre: la ficha completa sobre la toma abierta del campo.
    t6 = Toma("cierre", carpeta, 6.2, (0.50, 0.50, 1.08), (0.50, 0.47, 1.00))
    t6.g(sprite_texto(M["nombre"], "InterDisplay-Thin", 190, 22), 0.3, 6.2,
         (0.50, 0.305, 1.0), (0.50, 0.30, 1.0), fade=(0.8, 1.0))
    t6.g(sprite_linea(260, 2), 0.9, 6.2, (0.5, 0.365, 1.0), (0.5, 0.365, 1.0), fade=(1.0, 1.0))
    t6.g(sprite_panel(980, 540, 0.46), 1.1, 6.2, (0.5, 0.68, 1.0), (0.5, 0.68, 1.0),
         z=7.0, fade=(1.2, 1.2))
    ficha = [f'{M["superficie"]}  ·  TERRAZA 3 m²', " · ".join(M["programa"][:2]),
             f'{M["plazo"]} · {M["entrega"][0]}']
    for i, linea in enumerate(ficha):
        t6.g(sprite_texto(linea, "Inter-Light", 34, 8), 1.3 + i * 0.5, 6.2,
             (0.50, 0.605 + i * 0.052, 1.0), (0.50, 0.60 + i * 0.052, 1.0),
             z=7.0, fade=(0.8, 1.0))
    t6.g(sprite_texto(M["claim"], "Inter-ExtraLight", 52, 16), 3.1, 6.2,
         (0.50, 0.825, 1.0), (0.50, 0.82, 1.0), z=7.0, fade=(1.0, 1.2))
    t6.g(sprite_texto(M["sitio"], "Inter-Regular", 30, 14, MADERA), 3.7, 6.2,
         (0.50, 0.878, 1.0), (0.50, 0.878, 1.0), z=7.0, fade=(1.0, 1.2))
    T.append(t6)

    t = 0.0
    for toma in T:
        toma.inicio = t
        t += toma.dur - FADE
    return T, t + FADE


def main(carpeta, salida):
    tomas, total = construir(carpeta)
    nframes = int(total * FPS)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
    vineta = (1 - 0.3 * np.clip(rr - 0.3, 0, 1.6) / 1.6)[..., None]
    # barrido de madera que corta entre tomas (transición de marca)
    banda = np.array(MADERA, dtype=np.float32)

    ff = subprocess.Popen([
        "ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", salida,
    ], stdin=subprocess.PIPE)

    for n in range(nframes):
        t = n / FPS
        base = None
        for i, toma in enumerate(tomas):
            lt = t - toma.inicio
            if lt < 0 or lt > toma.dur:
                continue
            rgb, dep = toma.frame(lt)
            for g in toma.graficos:
                g.componer(rgb, dep, lt)
            w = ease(lt / FADE) if i > 0 and lt < FADE else 1.0
            base = rgb if base is None else base * (1 - w) + rgb * w
        f = base * vineta
        # corte de marca: una banda cálida barre el cuadro en cada cambio de toma
        for toma in tomas[1:]:
            u = (t - (toma.inicio - 0.18)) / 0.5
            if 0 <= u <= 1:
                borde = u * (H + 420) - 210
                d = np.abs(yy - borde)
                a = np.clip(1 - d / 130, 0, 1)[..., None] ** 1.6 * 0.7
                f = f * (1 - a) + banda * a
        f *= min(1.0, t / 0.8, (total - t) / 0.9)
        ff.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
        if n % 120 == 0:
            print(f"{n}/{nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"OK {salida} ({total:.1f} s)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
