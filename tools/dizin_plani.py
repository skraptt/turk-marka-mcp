#!/usr/bin/env python3
"""Hangi bültenlerin işleneceğini seçer ve GitHub Actions matrisi olarak yazar.

İki kip var:
  ornek  Her yıldan bir bülten (yılın en yenisi). Ayrıştırıcının eski biçimlerde
         çalışıp çalışmadığını ölçmek için; --max-pages ile kısmi okunur.
  tam    Henüz dizinlenmemiş en yeni N bülten. Dizinlenmiş olanlar --hazir
         dosyasındaki kimliklerdir (sürüm varlıklarının adları).

Kullanım:
  python tools/dizin_plani.py bultenler.json --kip ornek
  python tools/dizin_plani.py bultenler.json --kip tam --adet 10 --hazir hazir.txt
Çıktı (stdout): {"include": [{"kimlik": ..., "baslik": ..., "dosya": ..., "tarih": ..., "url": ...}, ...]}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def ornek(rows: list[dict]) -> list[dict]:
    secim: dict[str, dict] = {}
    for r in rows:  # rows yeniden eskiye sıralı
        secim.setdefault(r["tarih"][:4], r)
    return sorted(secim.values(), key=lambda r: r["tarih"])


def tam(rows: list[dict], hazir: set[str], adet: int) -> list[dict]:
    return [r for r in rows if r["kimlik"] not in hazir][:adet]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("liste")
    ap.add_argument("--kip", choices=["ornek", "tam"], default="ornek")
    ap.add_argument("--adet", type=int, default=10)
    ap.add_argument("--hazir", help="Dizinlenmiş kimlikler, satır başına bir tane")
    a = ap.parse_args(argv)

    rows = json.loads(Path(a.liste).read_text(encoding="utf-8"))
    # Marka Gazetesi ayrı bir yayın (tescil kayıtları); bülten ayrıştırıcısı ondan ibare
    # çıkaramıyor. Şimdilik dizine alınmaz.
    rows = [r for r in rows if "gazete" not in (r.get("dosya", "") + r.get("baslik", "")).lower()]
    if a.kip == "ornek":
        secim = ornek(rows)
    else:
        hazir = set()
        if a.hazir and Path(a.hazir).exists():
            # Varlık adları "<kimlik>.jsonl.gz" ya da ZIP parçaları için "<kimlik>-NN.jsonl.gz".
            hazir = {s.strip().split(".")[0] for s in Path(a.hazir).read_text().splitlines() if s.strip()}
            hazir |= {h[:-3] for h in hazir if len(h) > 3 and h[-3] == "-" and h[-2:].isdigit()}
        secim = tam(rows, hazir, min(a.adet, 256))
    print(json.dumps({"include": secim}, ensure_ascii=False))


if __name__ == "__main__":
    main()
