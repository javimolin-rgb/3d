#!/usr/bin/env python3
"""Genera la locución de un reel con Voicebox (https://github.com/jamiepine/voicebox),
local y sin clave de API.

La diferencia con mandar el guion entero a un servicio: acá se genera **frase por frase**
y los silencios los pone este script, no el modelo. Eso importa porque el problema de la
locución de Casa Peumo es justamente el reparto del tiempo (ver LOCUCION.md §1): con
<break> uno le pide al modelo una pausa y le hace caso más o menos, acá la pausa dura
exactamente lo que dice el guion y la tabla de tiempos calza al cuadro.

  tools/generar_voz_local.py guiones/peumo_voz.txt salida.wav

Variables de entorno:
  VOICEBOX=/ruta/al/repo   (por defecto /home/user/jamiepine/voicebox)
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

VOICEBOX = Path(os.environ.get("VOICEBOX", "/home/user/jamiepine/voicebox"))

# La descripción de la voz. Es el "Voice Design" de LOCUCION.md §3, en inglés porque
# el modelo interpreta la instrucción mucho mejor en inglés que en español, aunque
# después hable en español.
DESIGN = (
    "A warm, friendly Chilean man in his early thirties. Mid-range voice, relaxed and "
    "close, like telling a friend about something he is excited about. Natural everyday "
    "speech, never an advertising or broadcast tone, no grandiosity."
)
# Instrucción de interpretación por defecto y por etiqueta del guion.
INSTRUCT = "Speak at a normal conversational speed, with light natural emphasis."
INSTRUCT_TAGS = {
    "cálido": "Speak at a normal conversational speed, warm and inviting.",
    "más suave": "Speak a little softer and slower, settling into a calm close.",
}

RE_BREAK = re.compile(r'<break\s+time="([\d.]+)s"\s*/>')
RE_TAG = re.compile(r"^\[(.+?)\]$")


def leer_guion(ruta: Path):
    """Devuelve [(texto, pausa_despues_s, instruct)] desde el cuerpo del guion."""
    cuerpo, n = [], 0
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("-----"):
            n += 1
            continue
        if n == 1:
            cuerpo.append(linea)

    segmentos, instruct = [], INSTRUCT
    for linea in cuerpo:
        linea = linea.strip()
        if not linea:
            continue
        tag = RE_TAG.match(linea)
        if tag:
            instruct = INSTRUCT_TAGS.get(tag.group(1), INSTRUCT)
            continue
        m = RE_BREAK.search(linea)
        pausa = float(m.group(1)) if m else 0.0
        texto = RE_BREAK.sub("", linea).strip()
        if texto:
            segmentos.append((texto, pausa, instruct))
    return segmentos


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--design", default=DESIGN)
    ap.add_argument("--desde", type=int, default=1, help="primera frase (para reanudar)")
    ap.add_argument("--hasta", type=int, default=0, help="última frase, 0 = todas")
    args = ap.parse_args()

    if not VOICEBOX.exists():
        sys.exit(f"no encuentro el repo de Voicebox en {VOICEBOX} (ver VOICEBOX=)")
    sys.path.insert(0, str(VOICEBOX))

    import numpy as np
    import soundfile as sf
    import librosa
    from backend.backends.qwen_voice_design_backend import QwenVoiceDesignBackend

    segmentos = leer_guion(args.guion)
    if not segmentos:
        sys.exit(f"no encontré frases en {args.guion}")
    hasta = args.hasta or len(segmentos)
    print(f"{len(segmentos)} frases en el guion; genero de la {args.desde} a la {hasta}")

    motor = QwenVoiceDesignBackend(model_size="1.7B")
    print("cargando el modelo (la primera vez baja ~3,5 GB de HuggingFace)...", flush=True)

    trozos, sr = [], None
    cache = args.salida.parent / (args.salida.stem + "_frases")
    cache.mkdir(parents=True, exist_ok=True)

    for i, (texto, pausa, instruct) in enumerate(segmentos, 1):
        if not (args.desde <= i <= hasta):
            continue
        parcial = cache / f"f{i:02d}.wav"
        if parcial.exists():                       # reanudable: no regenera lo hecho
            audio, sr = sf.read(parcial)
            print(f"  [{i:2d}/{len(segmentos)}] (cacheada) {texto[:52]}", flush=True)
        else:
            print(f"  [{i:2d}/{len(segmentos)}] {texto[:52]}", flush=True)
            audio, sr = await motor.generate(
                text=texto,
                voice_prompt={"design_prompt": args.design},
                language=args.idioma,
                seed=args.semilla,
                instruct=instruct,
            )
            audio = np.asarray(audio, dtype=np.float32)
            # El modelo deja aire al principio y al final de cada frase. Se saca para
            # que la pausa que manda sea la del guion y no la del modelo más la nuestra.
            audio, _ = librosa.effects.trim(audio, top_db=35)
            sf.write(parcial, audio, sr)
        trozos.append((audio, pausa))

    if not trozos:
        sys.exit("no se generó nada")

    piezas, t, tabla = [], 0.0, []
    for audio, pausa in trozos:
        tabla.append((t, len(audio) / sr))
        piezas.append(audio)
        t += len(audio) / sr
        if pausa:
            piezas.append(np.zeros(int(pausa * sr), dtype=np.float32))
            t += pausa

    final = np.concatenate(piezas)
    sf.write(args.salida, final, sr)
    print(f"\n{args.salida}  ·  {len(final)/sr:.2f} s  ·  {sr} Hz")
    print("  arranque de cada frase:",
          " ".join(f"{t0:.1f}" for t0, _ in tabla))


if __name__ == "__main__":
    asyncio.run(main())
