#!/usr/bin/env python3
"""Bülten özetlerini (`*.ozet.json`) tek bir Markdown tablosunda toplar.

Kullanım:  python tools/dizin_raporu.py ozetler/ > rapor.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ESIK = 90.0  # bu oranın altındaki doluluklar işaretlenir


def isaret(v: float) -> str:
    return f"{v:g}" if v >= ESIK else f"**{v:g}** ⚠"


def rapor(ozetler: list[dict]) -> str:
    ozetler = sorted(ozetler, key=lambda o: o.get("tarih", ""))
    satirlar = [
        "# Bülten dizini raporu",
        "",
        f"{len(ozetler)} bülten dosyası işlendi. %{ESIK:g} altındaki doluluk oranları ⚠ ile işaretli.",
        "",
        "| Tarih | Bülten | Dosya | Sayfa | Kayıt | Başvuru no % | İbare % | Sınıf % | Tarih % | Kısmi |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    toplam = 0
    for o in ozetler:
        toplam += o.get("kayit", 0)
        satirlar.append(
            f"| {o.get('tarih', '')} | {o.get('baslik', '')} | {o.get('dosya', '')} | {o.get('sayfa', 0)} "
            f"| {o.get('kayit', 0)} | {isaret(o.get('basvuru_no_%', 0))} | {isaret(o.get('ibare_%', 0))} "
            f"| {isaret(o.get('sinif_%', 0))} | {isaret(o.get('tarih_%', 0))} | {'evet' if o.get('kismi') else ''} |"
        )
    satirlar += ["", f"Toplam kayıt: {toplam}.", "",
                 "Hiç kayıt çıkmayan ya da oranları düşük bültenler, ayrıştırıcının o dönemin biçimini "
                 "tanımadığını gösterir. Bu dosyalar dizine güvenilir sayılmaz."]
    return "\n".join(satirlar) + "\n"


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    klasor = Path(argv[0] if argv else ".")
    ozetler = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(klasor.rglob("*.ozet.json"))]
    sys.stdout.write(rapor(ozetler))


if __name__ == "__main__":
    main()
