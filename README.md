# Türk Marka MCP (geliştirme aşamasında)

Türk marka hukuku için açık kaynak bir MCP sunucusu. Hedef kullanım: bir müvekkil logosunu son iki ayda Resmî Marka Bülteni'nde yayımlanan markalarla karşılaştırıp yayına itiraz (SMK m. 18) kararına destek olmak.

Bu depoda şimdilik iki GitHub Actions iş akışı var:

- **Bülten yoklaması:** tek bir bülteni indirip yapısını ölçer.
- **Bülten dizini:** bülten arşivini listeler ve bültenleri aranabilir bir dizine çevirir. Bu dizin, ileride gelecek "bu isim daha önce başvurulmuş mu?" ön kontrolünün Türkiye ayağı olacak.

## Bülten yoklaması

1. GitHub'da **Actions → Bülten yoklaması → Run workflow**.
2. Varsayılan adres 503 sayılı bülten (27.10.2026). Başka bir sayı için [Bültenler](https://www.turkpatent.gov.tr/bultenler) sayfasındaki "İndir" bağlantısını yapıştır.
3. Hızlı deneme için `max_pages` alanına örneğin `60` yaz; tam bülten için `0` bırak.
4. Rapor iş özetinde görünür. Örnek önizlemeler ve `ornek_kayitlar.json` üç gün saklanan **bulten-yoklama** çıktısındadır.

Rapor şunları ölçer: kayıt sayısı, (531) Viyana kodlarının oranı, logoların kendi kayıtlarına doğru bağlanıp bağlanmadığı, alan tutarlılığı ve önizleme arşivinin boyutu.

## Bülten dizini

**Neden bültenler?** TÜRKPATENT'in marka araştırma sayfası reCAPTCHA ile korunuyor, TMview'un kullanım şartları da otomatik erişime izin vermiyor. Bu yüzden ikisine de dokunulmaz. Resmî Marka Bülteni ise herkesin indirmesi için yayımlanıyor. Arşiv listesi, Bültenler sayfasının kendi kullandığı adresten alınıyor.

**Kapsam sınırı:** Bültenler yayıma çıkan başvuruları içerir. Eski tescilleri, yenilemeleri ve başvurunun sonraki durumunu (ret, geri çekme, sona erme) göstermez. Bu yüzden dizin "bu isim boş" sonucunu veremez. Sadece "şu bültenlerde benzer ibareler yayımlanmış" diyebilir. Kesin sonuç için TÜRKPATENT'te elle araştırma gerekir.

**Kullanım** (Actions → **Bülten dizini** → Run workflow):

- `kip = ornek`: Her yıldan bir bültenin ilk `max_pages` sayfasını okur. Ayrıştırıcının eski bülten biçimlerinde çalışıp çalışmadığını gösteren bir tablo üretir. Hiçbir şey yayımlamaz.
- `kip = tam`: Henüz dizinlenmemiş en yeni `adet` bülteni baştan sona okur. Her birinin dizinini (`<kimlik>.jsonl.gz`) ve özetini depodaki **dizin** sürümüne ekler. Aynı anda en fazla iki bülten indirilir. Bir bülten yaklaşık 400 MB olduğu için her çalıştırma birkaç bülteni işler; iş akışını tekrar çalıştırmak kaldığı yerden devam eder.

Araçlar: `tools/bulten_listesi.py` (arşiv listesi), `tools/dizin_plani.py` (hangi bültenler işlenecek), `tools/bulten_dizini.py` (PDF'ten dizine), `tools/dizin_raporu.py` (özet tablo).

## Kişisel veri

(731) sahip ve "Vekil:" satırlarının içeriği hiçbir çıktıya yazılmaz, dizine de girmez; yalnızca alanın varlığı sayılır. Bülten PDF'inin kendisi yüklenmez ve saklanmaz.

## Yerel test

```
pip install pymupdf pillow pdfplumber reportlab
python tests/test_bulten_yoklama.py
python tests/test_bulten_dizini.py
```

Test, gerçek bültenin düzenini taklit eden sentetik bir PDF üretir (iki sütun, sayfa aşan kayıt, vekil satırı, Viyana kodları) ve ayrıştırıcıyı kurulu her arka uçla dener.

---

**English summary.** Work-in-progress open-source MCP server for Turkish trademark law. This repository currently contains a GitHub Actions probe that downloads one issue of the Official Trademark Bulletin (Resmî Marka Bülteni), parses its records and reports structure statistics (Vienna codes, logo-to-record matching, thumbnail archive size). Personal data (applicant and attorney names) is never written to any output.
