# Türk Marka MCP (geliştirme aşamasında)

Türk marka hukuku için açık kaynak bir MCP sunucusu. Hedef kullanım: bir müvekkil logosunu son iki ayda Resmî Marka Bülteni'nde yayımlanan markalarla karşılaştırıp yayına itiraz (SMK m. 18) kararına destek olmak.

Bu depoda şimdilik yalnızca **bülten yoklaması** var: tek bir bülteni indirip yapısını ölçen bir GitHub Actions iş akışı.

## Bülten yoklaması

1. GitHub'da **Actions → Bülten yoklaması → Run workflow**.
2. Varsayılan adres 503 sayılı bülten (27.10.2026). Başka bir sayı için [Bültenler](https://www.turkpatent.gov.tr/bultenler) sayfasındaki "İndir" bağlantısını yapıştır.
3. Hızlı deneme için `max_pages` alanına örneğin `60` yaz; tam bülten için `0` bırak.
4. Rapor iş özetinde görünür. Örnek önizlemeler ve `ornek_kayitlar.json` üç gün saklanan **bulten-yoklama** çıktısındadır.

Rapor şunları ölçer: kayıt sayısı, (531) Viyana kodlarının oranı, logoların kendi kayıtlarına doğru bağlanıp bağlanmadığı, alan tutarlılığı ve önizleme arşivinin boyutu.

## Kişisel veri

(731) sahip ve "Vekil:" satırlarının içeriği hiçbir çıktıya yazılmaz; yalnızca alanın varlığı sayılır. Bülten PDF'inin kendisi yüklenmez.

## Yerel test

```
pip install pymupdf pillow pdfplumber reportlab
python tests/test_bulten_yoklama.py
```

Test, gerçek bültenin düzenini taklit eden sentetik bir PDF üretir (iki sütun, sayfa aşan kayıt, vekil satırı, Viyana kodları) ve ayrıştırıcıyı kurulu her arka uçla dener.

---

**English summary.** Work-in-progress open-source MCP server for Turkish trademark law. This repository currently contains a GitHub Actions probe that downloads one issue of the Official Trademark Bulletin (Resmî Marka Bülteni), parses its records and reports structure statistics (Vienna codes, logo-to-record matching, thumbnail archive size). Personal data (applicant and attorney names) is never written to any output.
