#!/usr/bin/env python3
"""Resmî Marka Bülteni yoklaması.

Tek bir bülten PDF'ini okur, kayıtları ayrıştırır ve yapıyla ilgili bir kalite
raporu üretir. Amaç, ileride yazılacak gerçek ayrıştırıcı için şu sorulara cevap
almaktır:

  - Bültende kaç kayıt var, alanlar ne kadar tutarlı?
  - (531) Viyana kodları hangi oranda var (şekil markalarında / diğerlerinde)?
  - Logolar kendi kayıtlarıyla doğru eşleşiyor mu?
  - Önizleme arşivi ne kadar yer tutar?

Kişisel veri ilkesi: (731) sahip ve "Vekil:" satırlarının içeriği hiçbir yere
yazılmaz; yalnızca alanın varlığı sayılır. Çıktıda başvuru no, tarih, ibare,
Viyana kodları ve sınıflar bulunur.

Kullanım:
  python tools/bulten_yoklama.py bulten.pdf --out cikti/ [--max-pages N]
                                 [--samples 15] [--backend pymupdf|pdfplumber]
"""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Ortak veri yapıları (PDF kütüphanesinden bağımsız)
# ---------------------------------------------------------------------------


@dataclass
class Word:
    x0: float
    top: float
    x1: float
    bottom: float
    text: str


@dataclass
class Img:
    x0: float
    top: float
    x1: float
    bottom: float
    key: str  # kütüphaneye özgü kimlik (xref vb.)


@dataclass
class Page:
    number: int  # 1'den başlar
    width: float
    height: float
    words: list[Word]
    images: list[Img]


@dataclass
class Record:
    basvuru_no: str = ""
    basvuru_tarihi: str = ""
    ibare: str = ""
    viyana: list[str] = field(default_factory=list)
    siniflar: list[int] = field(default_factory=list)
    kismi_yayin: bool = False
    sahip_var: bool = False
    vekil_var: bool = False
    sayfa: int = 0
    image_key: str | None = None
    image_page: int | None = None
    extra_images: int = 0
    # ayrıştırma sırasında kullanılan geçici alanlar
    _field: str = ""
    _raw: dict = field(default_factory=dict)

    @property
    def sekil(self) -> bool:
        return self.ibare.strip().lower() in {"şekil", "sekil"}


# ---------------------------------------------------------------------------
# PDF okuma arka uçları
# ---------------------------------------------------------------------------


class PyMuPDFBackend:
    """Asıl kullanım: hızlı, C tabanlı."""

    def __init__(self, path: str):
        import fitz  # PyMuPDF

        self.fitz = fitz
        self.doc = fitz.open(path)

    def page_count(self) -> int:
        return self.doc.page_count

    def page(self, i: int) -> Page:
        p = self.doc[i]
        words = [
            Word(w[0], w[1], w[2], w[3], w[4])
            for w in p.get_text("words")
            if w[4].strip()
        ]
        images = []
        for info in p.get_image_info(xrefs=True):
            x0, y0, x1, y1 = info["bbox"]
            images.append(Img(x0, y0, x1, y1, str(info.get("xref", 0))))
        return Page(i + 1, p.rect.width, p.rect.height, words, images)

    def image_bytes(self, key: str) -> bytes | None:
        xref = int(key)
        if xref <= 0:
            return None
        return self.doc.extract_image(xref)["image"]


class PdfPlumberBackend:
    """Yedek ve yerel test: yavaş ama saf Python."""

    def __init__(self, path: str):
        import pdfplumber

        self.pdf = pdfplumber.open(path)
        self._streams: dict[str, object] = {}

    def page_count(self) -> int:
        return len(self.pdf.pages)

    def page(self, i: int) -> Page:
        p = self.pdf.pages[i]
        words = [
            Word(w["x0"], w["top"], w["x1"], w["bottom"], w["text"])
            for w in p.extract_words(keep_blank_chars=False, use_text_flow=False)
        ]
        images = []
        for n, im in enumerate(p.images):
            key = f"{i}:{n}"
            self._streams[key] = im["stream"]
            images.append(Img(im["x0"], im["top"], im["x1"], im["bottom"], key))
        p.flush_cache()
        return Page(i + 1, float(p.width), float(p.height), words, images)

    def image_bytes(self, key: str) -> bytes | None:
        """JPEG ise olduğu gibi; değilse çözülmüş pikselleri PNG'ye çevirir."""
        s = self._streams.get(key)
        if s is None:
            return None
        try:
            filt = s.attrs.get("Filter")
            names = [getattr(f, "name", str(f)) for f in (filt if isinstance(filt, list) else [filt])]
            if names and names[-1] == "DCTDecode":
                return s.get_data() if len(names) > 1 else s.get_rawdata()
            from PIL import Image

            w, h = int(s.attrs["Width"]), int(s.attrs["Height"])
            data = s.get_data()
            mode = "RGB" if len(data) >= w * h * 3 else "L"
            im = Image.frombytes(mode, (w, h), data[: w * h * (3 if mode == "RGB" else 1)])
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return buf.getvalue()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Sayfa düzeni: başlık, sütunlar, satırlar
# ---------------------------------------------------------------------------

HEADER_RE = re.compile(r"(\d{4}/\d+)\s+Resmi\s+Marka\s+B[üu]lteni", re.I)
DATE_RE = re.compile(r"Yay[ıi]n\s+Tarihi\s*:?\s*(\d{2}\.\d{2}\.\d{4})", re.I)
MIN_IMAGE_PT = 30  # bundan küçük görseller süs/çizgi sayılır


def split_header(page: Page) -> tuple[str, list[Word]]:
    """Sayfanın en üstündeki başlık bandını ayırır."""
    if not page.words:
        return "", []
    top = min(w.top for w in page.words)
    band = [w for w in page.words if w.top - top < 6]
    header_text = " ".join(w.text for w in sorted(band, key=lambda w: w.x0))
    if "Bülten" in header_text or "Bulteni" in header_text or "Tarihi" in header_text:
        rest = [w for w in page.words if w not in band]
        return header_text, rest
    return "", page.words


def rows_in(words: list[Word], tol: float = 3.0) -> list[tuple[float, str]]:
    """Aynı yükseklikteki kelimeleri satır yapar: (üst, metin)."""
    rows: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.top, w.x0)):
        if rows and abs(rows[-1][0].top - w.top) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    out = []
    for r in rows:
        r.sort(key=lambda w: w.x0)
        out.append((r[0].top, " ".join(w.text for w in r)))
    return out


def ordered_items(page: Page, words: list[Word]):
    """Okuma sırası: sol sütun yukarıdan aşağı, sonra sağ sütun."""
    mid = page.width / 2
    items = []
    for col in (0, 1):
        cw = [w for w in words if (w.x0 < mid) == (col == 0)]
        ci = [
            im
            for im in page.images
            if ((im.x0 + im.x1) / 2 < mid) == (col == 0)
            and (im.x1 - im.x0) >= MIN_IMAGE_PT
            and (im.bottom - im.top) >= MIN_IMAGE_PT
        ]
        col_items = [("row", top, text) for top, text in rows_in(cw)]
        col_items += [("img", im.top, im) for im in ci]
        col_items.sort(key=lambda t: t[1])
        items.extend(col_items)
    return items


# ---------------------------------------------------------------------------
# Kayıt ayrıştırma
# ---------------------------------------------------------------------------

LABEL_SPLIT = re.compile(r"\((\d{3})\)")
VIENNA_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{1,2})\b")
APPNO_RE = re.compile(r"^\d{4}/\d{5,6}$")
DATE_ONLY_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
BEFORE_GOODS = {"210", "220", "731", "740", "vekil", "540", "531", "591", "300"}


def norm_vienna(m: re.Match) -> str:
    return "{:02d}.{:02d}.{:02d}".format(*(int(g) for g in m.groups()))


def feed_text(rec: Record, fld: str, text: str) -> None:
    """Bir alana metin ekler. Kişisel veri alanlarının içeriği saklanmaz."""
    text = text.strip()
    if fld == "731":
        rec.sahip_var = True
        return
    if fld == "vekil":
        rec.vekil_var = True
        return
    if fld == "510" or not text:
        return
    rec._raw.setdefault(fld, []).append(text)


def finalize(rec: Record) -> Record:
    raw = rec._raw
    rec.basvuru_no = " ".join(raw.get("210", [])).split()[0] if raw.get("210") else ""
    d = DATE_ONLY_RE.search(" ".join(raw.get("220", [])))
    rec.basvuru_tarihi = d.group(0) if d else ""
    rec.ibare = " ".join(raw.get("540", [])).strip()
    rec.viyana = [norm_vienna(m) for m in VIENNA_RE.finditer(" ".join(raw.get("531", [])))]
    rec.siniflar = sorted(
        {int(x) for x in re.findall(r"\b\d{1,2}\b", " ".join(raw.get("511", []))) if 1 <= int(x) <= 45}
    )
    rec._raw = {}
    rec._field = ""
    return rec


def parse(backend, max_pages: int = 0, progress_every: int = 100):
    records: list[Record] = []
    orphan_images = 0
    bulten_no, yayin_tarihi = "", ""
    cur: Record | None = None
    n = backend.page_count()
    if max_pages:
        n = min(n, max_pages)
    t0 = time.time()

    for i in range(n):
        page = backend.page(i)
        header, words = split_header(page)
        if header and not bulten_no:
            m = HEADER_RE.search(header)
            bulten_no = m.group(1) if m else ""
            m = DATE_RE.search(header)
            yayin_tarihi = m.group(1) if m else ""

        for kind, _top, payload in ordered_items(page, words):
            if kind == "img":
                if cur is not None and cur.image_key is None and cur._field in BEFORE_GOODS:
                    cur.image_key = payload.key
                    cur.image_page = page.number
                elif cur is not None:
                    cur.extra_images += 1
                else:
                    orphan_images += 1
                continue

            text: str = payload
            if text.startswith("(210)"):
                if cur is not None:
                    records.append(finalize(cur))
                cur = Record(sayfa=page.number)
            if cur is None:
                continue  # ön sayfalar
            if text.startswith("Vekil"):
                cur._field = "vekil"
                feed_text(cur, "vekil", text)
                continue
            if text.startswith("Çıkarılan Mal") or text.startswith("Cikarilan Mal"):
                cur.kismi_yayin = True
                cur._field = "510"
                continue
            parts = LABEL_SPLIT.split(text)
            # parts: [önek, kod1, metin1, kod2, metin2, ...]
            if parts[0].strip():
                feed_text(cur, cur._field, parts[0])
            for k in range(1, len(parts), 2):
                cur._field = parts[k]
                feed_text(cur, cur._field, parts[k + 1] if k + 1 < len(parts) else "")

        if progress_every and (i + 1) % progress_every == 0:
            el = time.time() - t0
            print(f"  {i + 1}/{n} sayfa, {len(records)} kayıt, {el:.0f} sn", file=sys.stderr)

    if cur is not None:
        records.append(finalize(cur))
    meta = {
        "bulten_no": bulten_no,
        "yayin_tarihi": yayin_tarihi,
        "sayfa": n,
        "sure_sn": round(time.time() - t0, 1),
        "sahipsiz_gorsel": orphan_images,
    }
    return records, meta


# ---------------------------------------------------------------------------
# Önizleme boyutu ve rapor
# ---------------------------------------------------------------------------


def thumb_size(data: bytes, px: int) -> tuple[int, bytes] | None:
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(data))
        im = im.convert("RGB")
        im.thumbnail((px, px))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=75)
        b = buf.getvalue()
        return len(b), b
    except Exception:
        return None


def pct(a: int, b: int) -> str:
    return f"{(100 * a / b):.1f}%" if b else "—"


def build_report(records, meta, backend, out: Path, samples: int, thumb_px: int):
    out.mkdir(parents=True, exist_ok=True)
    N = len(records)
    sekil = [r for r in records if r.sekil]
    diger = [r for r in records if not r.sekil]
    with_img = [r for r in records if r.image_key]
    bad_no = [r for r in records if not APPNO_RE.match(r.basvuru_no)]
    no_date = [r for r in records if not r.basvuru_tarihi]
    no_cls = [r for r in records if not r.siniflar]
    no_ibare = [r for r in records if not r.ibare]
    sekil_no_img = [r for r in sekil if not r.image_key]
    sekil_no_vie = [r for r in sekil if not r.viyana]
    multi = [r for r in records if r.extra_images]

    # Önizleme boyutu: tüm görsellerin küçük hâli ölçülür
    sizes, orig = [], []
    for r in with_img:
        data = backend.image_bytes(r.image_key)
        if not data:
            continue
        orig.append(len(data))
        t = thumb_size(data, thumb_px)
        if t:
            sizes.append(t[0])

    # Örnekler: rastgele kayıtlar + önizlemeleri (eşleşmeyi gözle doğrulamak için)
    rnd = random.Random(42)
    pool = [r for r in with_img]
    pick = rnd.sample(pool, min(samples, len(pool))) if samples else []
    # şekil markalarından da örnek olsun
    pick_sek = [r for r in rnd.sample(sekil, min(samples // 3, len(sekil)))] if samples else []
    sample_recs = []
    sdir = out / "ornek_onizleme"
    if pick or pick_sek:
        sdir.mkdir(exist_ok=True)
    for r in {id(x): x for x in pick + pick_sek}.values():
        name = r.basvuru_no.replace("/", "-") or f"sayfa{r.sayfa}"
        if r.image_key:
            data = backend.image_bytes(r.image_key)
            t = thumb_size(data, thumb_px) if data else None
            if t:
                (sdir / f"{name}.webp").write_bytes(t[1])
        sample_recs.append(public(r))

    (out / "ornek_kayitlar.json").write_text(
        json.dumps(sample_recs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    def first(rs, k=15):
        return ", ".join(f"{r.basvuru_no or '?'} (s.{r.sayfa})" for r in rs[:k]) or "yok"

    total_thumb = sum(sizes)
    lines = [
        f"# Bülten yoklama raporu — {meta['bulten_no'] or '?'} ({meta['yayin_tarihi'] or '?'})",
        "",
        f"- Sayfa: {meta['sayfa']} · süre: {meta['sure_sn']} sn · kayıt: {N}",
        f"- Şekil markası ((540) = \"şekil\"): {len(sekil)} ({pct(len(sekil), N)})",
        "",
        "## Viyana kodları (531)",
        "",
        f"- Tüm kayıtlarda (531) var: {sum(1 for r in records if r.viyana)} ({pct(sum(1 for r in records if r.viyana), N)})",
        f"- Şekil markalarında var: {len(sekil) - len(sekil_no_vie)} / {len(sekil)} ({pct(len(sekil) - len(sekil_no_vie), len(sekil))})",
        f"- Görselli ama şekil olmayan kayıtlarda var: {sum(1 for r in diger if r.image_key and r.viyana)} / {sum(1 for r in diger if r.image_key)}",
        f"- Kod başına kayıtta ortalama: {statistics.mean([len(r.viyana) for r in records if r.viyana]):.1f}" if any(r.viyana for r in records) else "- Kod yok",
        "",
        "## Görsel eşleşmesi",
        "",
        f"- Görseli olan kayıt: {len(with_img)} ({pct(len(with_img), N)})",
        f"- Görseli olmayan şekil markası (0 olmalı): {len(sekil_no_img)} — {first(sekil_no_img)}",
        f"- Birden fazla görsel düşen kayıt: {len(multi)} — {first(multi)}",
        f"- Hiçbir kayda bağlanamayan görsel: {meta['sahipsiz_gorsel']}",
        "",
        "## Alan tutarlılığı",
        "",
        f"- Geçersiz başvuru no: {len(bad_no)} — {first(bad_no)}",
        f"- Başvuru tarihi okunamayan: {len(no_date)} — {first(no_date)}",
        f"- Sınıfı okunamayan: {len(no_cls)} — {first(no_cls)}",
        f"- İbaresi boş: {len(no_ibare)} — {first(no_ibare)}",
        f"- Kısmi yayın (Çıkarılan Mal/Hizmetler): {sum(r.kismi_yayin for r in records)}",
        f"- Sahip alanı bulunan: {pct(sum(r.sahip_var for r in records), N)} · vekil satırı bulunan: {pct(sum(r.vekil_var for r in records), N)} (içerikleri kaydedilmedi)",
        "",
        "## Önizleme arşivi",
        "",
        f"- Özgün görseller: {len(orig)} adet, toplam {sum(orig) / 1e6:.1f} MB",
        f"- {thumb_px}px WebP önizleme: toplam {total_thumb / 1e6:.2f} MB, ortalama {(total_thumb / len(sizes) / 1e3 if sizes else 0):.1f} KB",
        f"- İki aylık tahmin (4 bülten): {4 * total_thumb / 1e6:.1f} MB",
        "",
        "## Sınıf dağılımı (ilk 10)",
        "",
    ]
    counts: dict[int, int] = {}
    for r in records:
        for c in r.siniflar:
            counts[c] = counts.get(c, 0) + 1
    for c, k in sorted(counts.items(), key=lambda t: -t[1])[:10]:
        lines.append(f"- Sınıf {c:02d}: {k} kayıt")
    lines += [
        "",
        f"Örnek kayıtlar `ornek_kayitlar.json` ve `ornek_onizleme/` içinde ({len(sample_recs)} adet). "
        "Görsellerin doğru kayda bağlandığını bunlarla gözle kontrol et.",
    ]
    (out / "rapor.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "ozet.json").write_text(
        json.dumps(
            {
                **meta,
                "kayit": N,
                "sekil": len(sekil),
                "viyana_tum": sum(1 for r in records if r.viyana),
                "viyana_sekil": len(sekil) - len(sekil_no_vie),
                "gorselli": len(with_img),
                "sekil_gorselsiz": len(sekil_no_img),
                "coklu_gorsel": len(multi),
                "onizleme_mb": round(total_thumb / 1e6, 2),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out / "rapor.md"


def public(r: Record) -> dict:
    """Dışarı yazılabilecek alanlar; kişisel veri yok."""
    return {
        "basvuru_no": r.basvuru_no,
        "basvuru_tarihi": r.basvuru_tarihi,
        "ibare": r.ibare,
        "sekil": r.sekil,
        "viyana": r.viyana,
        "siniflar": r.siniflar,
        "kismi_yayin": r.kismi_yayin,
        "sayfa": r.sayfa,
        "gorsel_var": bool(r.image_key),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--out", default="cikti")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--samples", type=int, default=15)
    ap.add_argument("--thumb-px", type=int, default=160)
    ap.add_argument("--backend", choices=["pymupdf", "pdfplumber"], default="pymupdf")
    a = ap.parse_args(argv)

    backend = PyMuPDFBackend(a.pdf) if a.backend == "pymupdf" else PdfPlumberBackend(a.pdf)
    records, meta = parse(backend, a.max_pages)
    rapor = build_report(records, meta, backend, Path(a.out), a.samples, a.thumb_px)
    print(rapor.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
