#!/usr/bin/env python3
"""Genera las instancias estáticas de las fuentes de marca Neorigen en assets/fuentes/.

Fuentes variables de github.com/google/fonts (OFL, ver OFL_*.txt):
  - Fraunces (títulos): opsz 144, wght 300, SOFT 20, WONK 1 -> Fraunces-Titulo.ttf
  - Work Sans (textos y rótulos): wght 400 / 500 -> WorkSans-Regular.ttf / WorkSans-Medium.ttf
IBM Plex Mono Medium ya es estática (IBMPlexMono-Medium.ttf).

Uso: python3 tools/instanciar_fuentes.py   (requiere fonttools)
"""
import os

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fuentes")
JOBS = [
    ("Fraunces[SOFT,WONK,opsz,wght].ttf", {"opsz": 144, "wght": 300, "SOFT": 20, "WONK": 1}, "Fraunces-Titulo.ttf"),
    ("WorkSans[wght].ttf", {"wght": 400}, "WorkSans-Regular.ttf"),
    ("WorkSans[wght].ttf", {"wght": 500}, "WorkSans-Medium.ttf"),
]

for src, axes, dst in JOBS:
    font = instantiateVariableFont(TTFont(os.path.join(DIR, src)), axes, updateFontNames=False)
    font.save(os.path.join(DIR, dst))
    print(dst, axes)
