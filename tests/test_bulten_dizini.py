"""Bülten listesi, plan, dizin ve rapor araçlarının testleri (ağa çıkmaz).

`API_YANITI`, TÜRKPATENT /api/bulletins yanıtının biçimini taklit eder
(Kasım 2026'da gözlenen alanlar). Kimlikler uydurmadır.

Çalıştırma:  python tests/test_bulten_dizini.py
"""

from __future__ import annotations

import gzip
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import bulten_dizini as bd  # noqa: E402
import bulten_listesi as bl  # noqa: E402
import dizin_plani as dp  # noqa: E402
import dizin_raporu as dr  # noqa: E402
import test_bulten_yoklama as ty  # noqa: E402


def _bulten(title, date, *files):
    return {"id": f"id-{title}", "title": title, "publish_at": f"{date}T06:16:00.000Z",
            "media": [{"id": f"m-{s}", "slug": s, "title": t} for s, t in files],
            "categories": [{"slug": "marka"}]}


API_YANITI = [
    {"mode": "all", "page": 1, "pages": 2, "pageSize": 3, "total": 5, "data": [
        _bulten("504", "2026-11-12", ("s504", "504_Sayili_Resmi Marka Bülteni")),
        _bulten("503", "2026-10-27", ("s503", "503_Sayili_Resmi Marka Bülteni")),
        _bulten("300", "2017-06-12", ("s300", "300 Sayılı Bülten")),
        _bulten("503", "2026-09-30", ("sg503", "503_Sayili_Marka_Gazetesi")),
    ]},
    {"mode": "all", "page": 2, "pages": 2, "pageSize": 3, "total": 5, "data": [
        _bulten("300", "2017-06-12", ("s300", "300 Sayılı Bülten")),      # sayfalar arasında yinelenen kayıt
        _bulten("1-102", "2009-09-14", ("s1", "Marka Bülteni 1-32"), ("s33", "Marka Bülteni 33-45")),
        _bulten("boş", "2009-09-14"),                                      # dosyası olmayan kayıt
    ]},
]


def test_liste():
    rows = bl.rows_from(API_YANITI)
    assert [r["kimlik"] for r in rows] == ["s504", "s503", "sg503", "s300", "s33", "s1"], rows
    assert rows[0]["url"] == "https://webim.turkpatent.gov.tr/file/s504?download"
    assert rows[0]["tarih"] == "2026-11-12" and rows[0]["baslik"] == "504"
    assert {r["baslik"] for r in rows if r["tarih"] == "2009-09-14"} == {"1-102"}


def test_plan():
    rows = bl.rows_from(API_YANITI)
    ornek = dp.ornek(rows)
    assert [r["tarih"][:4] for r in ornek] == ["2009", "2017", "2026"]
    assert ornek[-1]["kimlik"] == "s504"                       # yılın en yenisi
    assert [r["kimlik"] for r in dp.tam(rows, {"s504"}, 2)] == ["s503", "sg503"]   # tam() süzmez
    import subprocess
    liste = Path(tempfile.mkdtemp()) / "l.json"
    liste.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "dizin_plani.py"), str(liste), "--kip", "tam",
                          "--adet", "9"], capture_output=True, text=True, check=True).stdout
    assert "sg503" not in out and "s503" in out                 # Marka Gazetesi plandan çıkar


def test_dizin_ve_rapor():
    if "pdfplumber" not in ty.available_backends():
        print("pdfplumber yok, dizin testi atlandı")
        return
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        pdf = t / "bulten.pdf"
        ty.make_pdf(pdf)
        bd.main([str(pdf), "--kimlik", "s503", "--baslik", "503", "--tarih", "2026-10-27",
                 "--out", str(t / "dizin"), "--backend", "pdfplumber"])
        lines = [json.loads(s) for s in gzip.open(t / "dizin" / "s503.jsonl.gz", "rt", encoding="utf-8")]
        assert lines, "dizin boş"
        assert all(r["bulten"] == "503" and r["bulten_kimlik"] == "s503" for r in lines)
        blob = json.dumps(lines, ensure_ascii=False)
        for yasak in ("sahip", "vekil", "Vekil"):               # kişisel veri alanları dizine girmez
            assert yasak not in blob, yasak
        oz = json.loads((t / "dizin" / "s503.ozet.json").read_text(encoding="utf-8"))
        assert oz["kayit"] == len(lines) and oz["basvuru_no_%"] > 0
        md = dr.rapor([oz, {**oz, "tarih": "2009-09-14", "ibare_%": 12.0, "kismi": True}])
        assert md.index("2009-09-14") < md.index("2026-10-27")  # tarihe göre sıralı
        assert "**12** ⚠" in md and "evet" in md


if __name__ == "__main__":
    for fn in (test_liste, test_plan, test_dizin_ve_rapor):
        fn()
        print("ok", fn.__name__)
