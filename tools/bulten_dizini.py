#!/usr/bin/env python3
"""Bir Resmî Marka Bülteni PDF'ini aranabilir dizin satırlarına çevirir.

Ayrıştırmayı `bulten_yoklama.parse` yapar. Bu araç kayıtları, kişisel veri
içermeyen alanlarla (`bulten_yoklama.public`) bir `.jsonl.gz` dosyasına yazar ve
ayrıştırmanın bu bültende ne kadar iyi çalıştığını gösteren bir özet çıkarır.
Özet, eski bülten biçimlerinde ayrıştırıcının işe yarayıp yaramadığını ölçmek
içindir.

Kişisel veri ilkesi: (731) sahip ve vekil bilgisi dizine yazılmaz.

Kullanım:
  python tools/bulten_dizini.py bulten.pdf --kimlik <slug> --baslik 503 --tarih 2026-10-27 \\
         --out dizin/ [--max-pages N] [--backend pymupdf|pdfplumber]
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bulten_yoklama as by  # noqa: E402


def oran(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def ozet(records, meta: dict, kaynak: dict) -> dict:
    n = len(records)
    ilan = [r for r in records if r.tur == "ilan"]
    return {
        **kaynak,
        "bulten_no_pdf": meta.get("bulten_no", ""),
        "yayin_tarihi_pdf": meta.get("yayin_tarihi", ""),
        "sayfa": meta.get("sayfa", 0),
        "sure_sn": meta.get("sure_sn", 0),
        "kayit": n,
        "turler": {t: sum(1 for r in records if r.tur == t) for t in ("ilan", "madrid", "serh", "belirsiz")},
        # Doluluk oranları (%): dizinin işe yarayıp yaramadığını bunlar söyler.
        "basvuru_no_%": oran(sum(1 for r in records if r.basvuru_no), n),
        "ibare_%": oran(sum(1 for r in records if r.ibare.strip()), n),
        "sinif_%": oran(sum(1 for r in records if r.siniflar), n),
        "tarih_%": oran(sum(1 for r in records if r.basvuru_tarihi), n),
        "ilan_ibare_%": oran(sum(1 for r in ilan if r.ibare.strip()), len(ilan)),
        "sekil_%": oran(sum(1 for r in records if r.sekil), n),
        "sahipsiz_gorsel": meta.get("sahipsiz_gorsel", 0),
    }


def satir(r, kaynak: dict) -> dict:
    d = by.public(r)
    d.update({"bulten": kaynak.get("baslik", ""), "bulten_tarihi": kaynak.get("tarih", ""),
              "bulten_kimlik": kaynak.get("kimlik", "")})
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--kimlik", required=True, help="Bülten dosyasının slug'ı (bulten_listesi çıktısı)")
    ap.add_argument("--baslik", default="")
    ap.add_argument("--dosya", default="")
    ap.add_argument("--tarih", default="")
    ap.add_argument("--out", default="dizin")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--backend", choices=["pymupdf", "pdfplumber"], default="pymupdf")
    a = ap.parse_args(argv)

    kaynak = {"kimlik": a.kimlik, "baslik": a.baslik, "dosya": a.dosya, "tarih": a.tarih,
              "kismi": bool(a.max_pages)}
    backend = by.PyMuPDFBackend(a.pdf) if a.backend == "pymupdf" else by.PdfPlumberBackend(a.pdf)
    records, meta = by.parse(backend, a.max_pages)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / f"{a.kimlik}.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(satir(r, kaynak), ensure_ascii=False) + "\n")
    oz = ozet(records, meta, kaynak)
    (out / f"{a.kimlik}.ozet.json").write_text(json.dumps(oz, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(oz, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
