#!/usr/bin/env python3
"""Resmî Marka Bülteni arşivinin listesini çıkarır.

TÜRKPATENT'in Bültenler sayfası (turkpatent.gov.tr/bultenler) listeyi kendi
`/api/bulletins` adresinden alır. Bu araç aynı listeyi, sayfa sayfa ve aralarda
bekleyerek okur; arama sayfasına (CAPTCHA'lı) hiç dokunmaz.

Her bülten kaydında bir ya da birden çok PDF dosyası olabilir (2009'da toplu
yüklenen eski sayılar böyle). Çıktı, dosya başına bir satırdır:

    {"kimlik": "<slug>", "baslik": "503", "dosya": "503_Sayili_Resmi Marka Bülteni",
     "tarih": "2026-10-27", "url": "https://webim.turkpatent.gov.tr/file/<slug>?download"}

Kullanım:
  python tools/bulten_listesi.py --out bultenler.json
  python tools/bulten_listesi.py --from-file kayitli_yanit.json   # çevrimdışı (test)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

LIST_URL = "https://www.turkpatent.gov.tr/api/bulletins"
FILE_URL = "https://webim.turkpatent.gov.tr/file/{slug}?download"
UA = "turk-marka-mcp bulten-listesi (+https://github.com/skraptt/turk-marka-mcp)"


def fetch_page(page: int, timeout: int = 60) -> dict:
    q = urllib.parse.urlencode({"locale": "tr", "category": "marka", "title": "", "date": "",
                                "mode": "all", "page": page})
    req = urllib.request.Request(f"{LIST_URL}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.load(r)
    if not body.get("success"):
        raise RuntimeError(f"Liste sayfası {page} başarısız: {str(body)[:200]}")
    return body["payload"]


def rows_from(payloads: list[dict]) -> list[dict]:
    """API yanıtlarını dosya başına bir satıra çevirir; yinelenenleri atar, yeniden eskiye sıralar."""
    out, seen = [], set()
    for p in payloads:
        for b in p.get("data", []):
            tarih = (b.get("publish_at") or "")[:10]
            for m in b.get("media") or []:
                slug = m.get("slug")
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                out.append({
                    "kimlik": slug,
                    "baslik": str(b.get("title") or "").strip(),
                    "dosya": (m.get("title") or "").strip(),
                    "tarih": tarih,
                    "url": FILE_URL.format(slug=slug),
                })
    out.sort(key=lambda r: (r["tarih"], r["baslik"], r["dosya"]), reverse=True)
    return out


def fetch_all(delay: float = 1.0) -> list[dict]:
    first = fetch_page(1)
    payloads = [first]
    for page in range(2, int(first.get("pages") or 1) + 1):
        time.sleep(delay)  # siteye yük bindirmemek için
        payloads.append(fetch_page(page))
    return rows_from(payloads)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="bultenler.json")
    ap.add_argument("--from-file", help="Kaydedilmiş API yanıtlarını (liste) oku; ağa çıkma")
    ap.add_argument("--delay", type=float, default=1.0)
    a = ap.parse_args(argv)

    if a.from_file:
        rows = rows_from(json.loads(Path(a.from_file).read_text(encoding="utf-8")))
    else:
        rows = fetch_all(a.delay)
    Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    yillar: dict[str, int] = {}
    for r in rows:
        yillar[r["tarih"][:4]] = yillar.get(r["tarih"][:4], 0) + 1
    print(f"{len(rows)} dosya; yıllara göre: " + ", ".join(f"{y}: {n}" for y, n in sorted(yillar.items())),
          file=sys.stderr)


if __name__ == "__main__":
    main()
