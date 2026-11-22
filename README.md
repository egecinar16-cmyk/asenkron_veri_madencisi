# Asenkron Parfüm Veri Madencisi

Parfüm sitesindeki ürünleri **asenkron** olarak çekip, seçtiğiniz **notalara** göre filtreleyen ve **fiyata göre sıralayan** bir web uygulaması.

Arka uçta `asyncio` + `httpx` ile onlarca sayfa aynı anda çekilir, `BeautifulSoup` ile ayrıştırılır, `Polars` ile temizlenir ve Flask üzerinden bir arayüze JSON olarak sunulur.

## Özellikler

- 10 kategori sayfasını ve bulunan tüm ürün sayfalarını **eşzamanlı** çekme (`asyncio.gather`)
- Ürün adı, görsel, fiyat ve üst / orta / alt notaları otomatik ayrıştırma
- Türkçe fiyat formatını (`1.299,99 TL`) sayıya çevirme
- Nota bazlı filtreleme: **Herhangi biri** veya **Hepsi** eşleşme modu
- Fiyata göre **düşükten yükseğe** / **yüksekten düşüğe** sıralama
- Sayfalama (sayfa başına 10 ürün) ve responsive arayüz
- Sonuçları `sonuclar.json` dosyasına kaydetme

## Kullanılan Teknolojiler

| Katman | Teknoloji |
|---|---|
| Dil | Python, JavaScript |
| Web | Flask |
| Asenkron istek | asyncio, httpx |
| HTML ayrıştırma | BeautifulSoup (bs4) |
| Veri işleme | Polars |
| Arayüz | HTML5, CSS3, vanilla JavaScript (Fetch API) |

## Proje Yapısı

```
.
├── app.py              # Flask uygulaması ve /api/cek endpoint'i
├── main.py             # Veri çekme, ayrıştırma, Polars dönüşümü, nota filtresi
├── templates/
│   └── index.html      # Arayüz (filtre, sıralama, sayfalama)
└── sonuclar.json       # Çalışma sonrası oluşan çıktı
```

## Kurulum

Python 3.10 veya üzeri önerilir.

```bash
# Sanal ortam (isteğe bağlı)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Bağımlılıklar
pip install flask httpx beautifulsoup4 polars
```

## Çalıştırma

### Web arayüzü

```bash
python app.py
```

Tarayıcıda `http://127.0.0.1:5000` adresini açın.

1. **API ÇEK** butonuyla tüm parfümleri getirin.
2. İstediğiniz notaları seçip eşleşme modunu belirleyin, **Notaya Göre Getir**'e basın.
3. **Fiyat** menüsünden sıralamayı değiştirin.

### Sadece veri toplama (arayüzsüz)

```bash
python main.py
```

Sonuçlar `sonuclar.json` dosyasına yazılır ve konsolda toplam ürün sayısı ile süre gösterilir.

## API

### `GET /api/cek`

| Parametre | Açıklama | Örnek |
|---|---|---|
| `notalar` | Virgülle ayrılmış nota listesi (isteğe bağlı) | `vanilya,amber` |
| `eslesme` | `herhangi` (varsayılan) veya `hepsi` | `hepsi` |

Örnek istek:

```
/api/cek?notalar=vanilya,amber&eslesme=hepsi
```

Örnek yanıt:

```json
{
  "basarili_sayfa": 10,
  "toplam_sayfa": 10,
  "ham_urun": 120,
  "toplam_urun": 14,
  "sure": 6.2481,
  "secilen_notalar": ["vanilya", "amber"],
  "eslesme": "hepsi",
  "veriler": [
    {
      "parfum_adi": "...",
      "gorsel": "https://...",
      "ust_notalar": ["..."],
      "orta_notalar": ["..."],
      "alt_notalar": ["..."],
      "notalar": "...",
      "fiyat": 519.0,
      "kaynak": "https://..."
    }
  ]
}
```

## Nasıl Çalışır?

1. **Kategori sayfaları:** `?pg=1..10` adresleri `httpx.AsyncClient` ile aynı anda çekilir.
2. **Ürün bağlantıları:** Her sayfadaki linkler süzülür, menü ve sistem sayfaları elenir, tekrarlar silinir.
3. **Ürün sayfaları:** Bulunan bütün ürün sayfaları yine eşzamanlı çekilir.
4. **Ayrıştırma:** `BeautifulSoup` ve regex ile ad, fiyat, görsel ve notalar çıkarılır.
5. **Dönüştürme:** `Polars` DataFrame'i açık şema ile oluşturulur (boş nota listelerinde tip hatası çıkmaması için).
6. **Filtreleme:** Seçilen notalar küçük harfe çevrilip regex ile aranır (`herhangi` = OR, `hepsi` = AND).
7. **Sunum:** Flask sonucu JSON döner, arayüz sıralama ve sayfalamayı tarayıcıda yapar.

## Notlar

- Her `/api/cek` isteği verileri siteden baştan çeker. Sık kullanımda sonuçları kısa süreli önbelleğe (cache) almak hem hızı artırır hem de siteye binen yükü azaltır.
- Veri kaynağı sitenin HTML yapısı değişirse ayrıştırma fonksiyonlarının (`extract_product`, `extract_product_links`, `nota_bul`) güncellenmesi gerekebilir.
- Web scraping yaparken sitenin kullanım koşullarına ve `robots.txt` dosyasına uyun. Bu proje eğitim ve kişisel kullanım amaçlıdır.

## Geliştirme Fikirleri

- Sonuçlar için önbellekleme
- Birden fazla mağazadan veri çekip fiyat karşılaştırma
- Marka, cinsiyet ve fiyat aralığı filtreleri
- Hata veren sayfalar için yeniden deneme (retry)
