"""Sentetik bir bülten üretip yoklama ayrıştırıcısını test eder.

Gerçek bültenin düzenini taklit eder: sayfa başlığı, iki sütun, sütun ve sayfa
aşan kayıt, "Vekil:" satırı, (531) kodları, kısmi yayın ve ön sayfada süs
görseli. Kişi adları uydurmadır.

Çalıştırma:  python -m pytest tests/  (ya da doğrudan: python tests/test_bulten_yoklama.py)
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bulten_yoklama as by  # noqa: E402

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


def _logo(text: str) -> bytes:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (591, 591), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([60, 220, 530, 370], outline="black", width=8)
    d.text((120, 280), text, fill="black")
    b = io.BytesIO()
    im.save(b, "JPEG", quality=80)
    return b.getvalue()


def make_pdf(path: Path) -> None:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font = next(p for p in FONT_CANDIDATES if Path(p).exists())
    pdfmetrics.registerFont(TTFont("T", font))
    W, H = 595, 842
    c = canvas.Canvas(str(path), pagesize=(W, H))
    cols = [40, 315]
    state = {"page": 0, "col": 0, "y": 0}

    def header():
        state["page"] += 1
        c.setFont("T", 9)
        c.drawString(40, H - 30, "2026/503  Resmi Marka Bülteni")
        c.drawString(230, H - 30, "Türk Patent ve Marka Kurumu")
        c.drawString(420, H - 30, f"Yayın Tarihi : 27.10.2026   {654 + state['page']}")
        state["col"], state["y"] = 0, H - 60

    def next_col():
        if state["col"] == 0:
            state["col"], state["y"] = 1, H - 60
        else:
            c.showPage()
            header()

    def line(text: str, gap: float = 13, size: float = 10):
        if state["y"] - gap < 50:
            next_col()
        c.setFont("T", size)
        c.drawString(cols[state["col"]], state["y"], text)
        state["y"] -= gap

    def image(data: bytes, size: float = 170):
        if state["y"] - size < 50:
            next_col()
        c.drawImage(ImageReader(io.BytesIO(data)), cols[state["col"]] + 30, state["y"] - size, size, size)
        state["y"] -= size + 10

    # Ön sayfa: açıklama + küçük süs görseli (kayda bağlanmamalı)
    c.setFont("T", 14)
    c.drawString(40, H - 80, "RESMİ MARKA BÜLTENİ 503")
    c.drawImage(ImageReader(io.BytesIO(_logo("TP"))), 40, H - 300, 150, 150)  # ön sayfa görseli
    c.showPage()
    header()

    # Kayıt 1: kelime + logo, kısmi yayın
    line("(210)  2026/092671          (220)  17.07.2026")
    line("(731)  5256379-UYDURMA KİŞİ (TR)")
    line("(540)  face")
    image(_logo("FACE"))
    line("(511)  03")
    line("(510)")
    for _ in range(4):
        line("Beyazlatma ve temizlik amaçlı maddeler; deterjanlar.")
    line("Çıkarılan Mal/Hizmetler:")
    line("Parfümeri, kozmetik maddeleri.")

    # Kayıt 2: şekil markası, vekil, (531) iki satıra taşar, sınıflar iki satır
    line("(210)  2026/092701          (220)  17.07.2026")
    line("(731)  6952921-ÖRNEK BRANDS, INC. (US)")
    line("       1000 ÖRNEK MALL MINNEAPOLIS 55403")
    line("Vekil:  UYDURMA VEKİL (ÖRNEK PATENT A.Ş.)")
    line("(540)  şekil")
    line("(531)  25.7.8, 26.1.3,")
    line("       27.5.1")
    image(_logo("SEKIL"))
    line("(511)  05 , 06 , 09 , 10 , 11 , 12 , 14 , 16 , 17 , 18 ,")
    line("       25 , 35")
    line("(510)")
    for _ in range(18):
        line("Mallar ve hizmetler listesi satırı.")

    # Kayıt 3: sütun/sayfa sonunda başlar, logo bir sonraki sütun/sayfada
    while state["y"] > 50 + 13 * 3 + 5:
        line("Mallar ve hizmetler listesi satırı.")
    line("(210)  2026/092702          (220)  18.07.2026")
    line("(731)  1234567-BAŞKA UYDURMA (TR)")
    line("(540)  sanatavm")
    image(_logo("SANATAVM"))  # yer kalmadığı için sonraki sütuna düşer
    line("(511)  16 , 35")
    line("(510)")
    line("Kağıt, karton.")

    # Şerhler bölümü: (566) taşıyan kayıtlar ilan sayılmamalı
    c.showPage()
    header()
    line("503. Marka Bülteni Şerhleri", gap=24, size=18)
    line("HACİZ KONULANLAR", gap=20, size=14)
    line("(210) 2026/039531 (220) 30/03/2026")
    line("(566) bacasan Esas No: 2026/7 (KONYA 6. İCRA DAİRESİ")
    line("MÜDÜRLÜĞÜ) Esas Tarihi : 20/10/2026")
    line("BOLUNMELER", gap=20, size=14)
    line("(210) 2026/059582 (220) 07.05.2026")
    line("(566) trendfinansia")

    # Madrid kaydı: üstte uluslararası no, iki düzeyli Viyana kodları
    c.showPage()
    header()
    line("1943075", gap=16, size=12)
    line("(210)  2026/988978          (220)  24.08.2026")
    line("(731)  8116261-ÖRNEK FOOD PTE LTD (SG)")
    line("(540)  waten")
    line("(531)  26.01;27.01;28.03;")
    image(_logo("WATEN"))
    line("(511)  30")
    line("(510)")
    line("Blends of seasonings; dried culinary herbs.")
    c.showPage()
    c.save()


def available_backends() -> list[str]:
    names = []
    for name, mod in (("pdfplumber", "pdfplumber"), ("pymupdf", "fitz")):
        try:
            __import__(mod)
            names.append(name)
        except ImportError:
            pass
    return names


def run(tmp: Path, backend_name: str = "pdfplumber"):
    pdf = tmp / "sentetik.pdf"
    if not pdf.exists():
        make_pdf(pdf)
    cls = by.PyMuPDFBackend if backend_name == "pymupdf" else by.PdfPlumberBackend
    backend = cls(str(pdf))
    records, meta = by.parse(backend, progress_every=0)
    return records, meta, backend


def test_parse(tmp_path: Path = None):
    tmp = tmp_path or Path(__import__("tempfile").mkdtemp())
    names = available_backends()
    assert names, "pdfplumber ya da PyMuPDF kurulu olmalı"
    for name in names:
        print(f"--- arka uç: {name}")
        check(tmp, name)


def check(tmp: Path, backend_name: str):
    records, meta, backend = run(tmp, backend_name)
    by_no = {r.basvuru_no: r for r in records}

    assert meta["bulten_no"] == "2026/503", meta
    assert meta["yayin_tarihi"] == "27.10.2026", meta
    assert meta["sahipsiz_gorsel"] == 1, meta  # ön sayfa görseli
    ilanlar = {r.basvuru_no: r for r in records if r.tur in ("ilan", "madrid")}
    assert set(ilanlar) == {"2026/092671", "2026/092701", "2026/092702", "2026/988978"}, list(ilanlar)
    assert sorted(r.basvuru_no for r in records if r.tur == "serh") == ["2026/039531", "2026/059582"]
    assert not [r for r in records if r.tur == "belirsiz"], [r.basvuru_no for r in records if r.tur == "belirsiz"]

    rm = by_no["2026/988978"]
    assert rm.tur == "madrid" and rm.uluslararasi_no == "1943075", (rm.tur, rm.uluslararasi_no)
    assert rm.viyana == ["26.01", "27.01", "28.03"], rm.viyana
    assert rm.siniflar == [30] and rm.image_key
    assert by_no["2026/092671"].tur == "ilan" and by_no["2026/092671"].uluslararasi_no == ""

    basliklar = meta["basliklar"]
    assert any("Şerhleri" in h for h in basliklar), basliklar
    assert any("HACİZ" in h for h in basliklar), basliklar

    r1 = by_no["2026/092671"]
    assert r1.basvuru_tarihi == "17.07.2026"
    assert r1.ibare == "face" and not r1.sekil
    assert r1.siniflar == [3]
    assert r1.viyana == []
    assert r1.kismi_yayin and r1.sahip_var and not r1.vekil_var
    assert r1.image_key and r1.extra_images == 0

    r2 = by_no["2026/092701"]
    assert r2.sekil and r2.vekil_var
    assert r2.viyana == ["25.07.08", "26.01.03", "27.05.01"], r2.viyana
    assert r2.siniflar == [5, 6, 9, 10, 11, 12, 14, 16, 17, 18, 25, 35], r2.siniflar
    assert r2.image_key

    r3 = by_no["2026/092702"]
    assert r3.ibare == "sanatavm"
    assert r3.siniflar == [16, 35]
    assert r3.image_key and r3.image_page == r3.sayfa + 1, (r3.sayfa, r3.image_page)  # logo sonraki sayfada

    # Görseller çıkarılabiliyor ve önizlemeye çevrilebiliyor
    for r in ilanlar.values():
        data = backend.image_bytes(r.image_key)
        assert data and by.thumb_size(data, 160), r.basvuru_no

    # Kişisel veri hiçbir public kayıtta yok
    blob = str([by.public(r) for r in records])
    for leak in ("UYDURMA", "ÖRNEK BRANDS", "MINNEAPOLIS", "VEKİL", "5256379", "ÖRNEK FOOD", "İCRA"):
        assert leak not in blob, leak

    # Rapor üretimi uçtan uca çalışıyor
    rapor = by.build_report(records, meta, backend, tmp / f"cikti-{backend_name}", samples=3, thumb_px=160)
    text = rapor.read_text(encoding="utf-8")
    assert "Viyana kodları" in text and "Şekil markalarında var: 1 / 1" in text, text
    print(text)


if __name__ == "__main__":
    test_parse()
    print("OK")
