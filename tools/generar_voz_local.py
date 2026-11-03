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
# "with clear separation between words" tiene que estar en las tres: medido, es lo que
# baja la velocidad de ~240 ppm a ~155. Pedir "slowly" sin eso casi no mueve la aguja
# (239 ppm), y agregar comas al texto tampoco ayuda (177 ppm) — el texto va plano.
# Medido: con "normal conversational speed" el modelo entrega ~270 ppm, muy por encima
# del objetivo de 150-165 (LOCUCION.md §1). Hay que pedirle lento explícitamente.
INSTRUCT = (
    "Speak slowly and unhurried, taking your time, with clear separation between words "
    "and light natural emphasis. Relaxed pace, never rushed."
)
INSTRUCT_TAGS = {
    "cálido": (
        "Speak slowly and unhurried, warm and inviting, with clear separation between "
        "words and light natural emphasis. Relaxed pace, never rushed."
    ),
    "más suave": (
        "Speak softly and slowly, with clear separation between words, settling into a "
        "calm, gentle close. Relaxed pace, never rushed."
    ),
}

# Duración de diseño de cada frase, en segundos: la que sale de repartir 107 palabras a
# ~158 ppm y es la que hace calzar la tabla de tiempos del guion con los 49,57 s del reel.
# Qwen VoiceDesign no tiene parámetro de velocidad y entrega ~240 ppm por mucho que se le
# pida lento en el instruct, así que con --ajustar-tempo cada frase se estira hasta su
# duración de diseño con ffmpeg atempo (WSOLA, no vocoder de fase: mejor para voz).
DURACION_DISENO = {
    1: 3.4, 2: 4.2, 3: 2.7, 4: 3.4, 5: 2.7, 6: 2.3, 7: 2.7,
    8: 3.4, 9: 3.8, 10: 5.3, 11: 1.5, 12: 1.0, 13: 2.7, 14: 2.2,
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


def estirar(audio, sr, factor):
    """Cambia la duración sin cambiar el tono, con el atempo de ffmpeg (WSOLA)."""
    import subprocess, tempfile, soundfile as sf, numpy as np
    with tempfile.TemporaryDirectory() as d:
        ent, sal = f"{d}/i.wav", f"{d}/o.wav"
        sf.write(ent, audio, sr)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", ent,
                        "-filter:a", f"atempo={factor:.4f}", sal], check=True)
        a, _ = sf.read(sal)
    return np.asarray(a, dtype=np.float32)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guion", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--design", default=DESIGN)
    ap.add_argument("--desde", type=int, default=1, help="primera frase (para reanudar)")
    ap.add_argument("--hasta", type=int, default=0, help="última frase, 0 = todas")
    ap.add_argument("--ajustar-tempo", action="store_true",
                    help="estira cada frase hasta su duración de diseño (ver DURACION_DISENO)")
    ap.add_argument("--tempo-minimo", type=float, default=0.72,
                    help="estiramiento máximo permitido; por debajo se oye artificial")
    ap.add_argument("--reintentos", type=int, default=0,
                    help="si la frase sale apurada, regenerarla con otra semilla hasta N veces "
                         "y quedarse con la más cercana a su duración de diseño")
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
            objetivo = DURACION_DISENO.get(i)
            mejor = None
            # La generación es muestreada: la misma frase sale a 155 ppm o a 245 según la
            # semilla. Volver a tirar los dados sale mejor que estirar al límite, porque
            # el estiramiento grande se oye. Se corta apenas una queda dentro de rango.
            for intento in range(args.reintentos + 1):
                semilla = args.semilla if intento == 0 or args.semilla is None \
                          else args.semilla + 1000 * intento
                audio, sr = await motor.generate(
                    text=texto,
                    voice_prompt={"design_prompt": args.design},
                    language=args.idioma,
                    seed=semilla,
                    instruct=instruct,
                )
                audio = np.asarray(audio, dtype=np.float32)
                # El modelo deja aire al principio y al final de cada frase. Se saca para
                # que la pausa que manda sea la del guion y no la del modelo más la nuestra.
                audio, _ = librosa.effects.trim(audio, top_db=35)
                dur = len(audio) / sr
                if objetivo is None:
                    mejor = audio
                    break
                if mejor is None or abs(dur - objetivo) < abs(len(mejor) / sr - objetivo):
                    mejor = audio
                if dur >= objetivo * 0.88:         # ya está suficientemente cerca
                    break
                if intento < args.reintentos:
                    print(f"       {dur:5.2f} s apurada, otra semilla...", flush=True)
            audio = mejor
            sf.write(parcial, audio, sr)
        # Aviso inmediato si el modelo se apura: el objetivo es 150-165 ppm dentro de la
        # frase (LOCUCION.md §1). Sin esto el apuro recién se nota al medir el total.
        ppm = 60 * len(texto.split()) / max(len(audio) / sr, 0.01)
        marca = "" if 140 <= ppm <= 175 else "  <- FUERA"
        print(f"       {len(audio)/sr:5.2f} s  {ppm:3.0f} ppm{marca}", flush=True)
        if args.ajustar_tempo and i in DURACION_DISENO:
            objetivo = DURACION_DISENO[i]
            factor = (len(audio) / sr) / objetivo      # <1 = hay que alargar
            factor = max(factor, args.tempo_minimo)
            if abs(factor - 1.0) > 0.03:
                audio = estirar(audio, sr, factor)
                print(f"       tempo x{factor:.2f} -> {len(audio)/sr:5.2f} s", flush=True)
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
