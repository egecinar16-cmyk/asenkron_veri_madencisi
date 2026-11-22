import asyncio
import json
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
import polars as pl
from bs4 import BeautifulSoup


# ============================================================
# AYARLAR
# ============================================================

BASE_URL = "https://www.parfumevi.com.tr"

MAX_CATEGORY_PAGES = 10

CATEGORY_URLS = [
    f"{BASE_URL}/acik-parfum?pg={page}"
    for page in range(1, MAX_CATEGORY_PAGES + 1)
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def temizle_metin(metin):
    """
    Metindeki gereksiz boşlukları temizler.
    """
    if metin is None:
        return ""

    metin = str(metin)
    metin = re.sub(r"\s+", " ", metin)

    return metin.strip()


def fiyat_temizle(metin):
    """
    Sayfadaki TL fiyatını bulur.

    Örnek:
    1.299,99 TL -> 1299.99
    519 TL      -> 519.0
    """

    if not metin:
        return None

    metin = temizle_metin(metin)

    eslesme = re.search(
        r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*TL",
        metin,
        re.IGNORECASE
    )

    if not eslesme:
        return None

    fiyat = eslesme.group(1)

    # Türkçe fiyat formatını Python formatına çevir
    fiyat = fiyat.replace(".", "")
    fiyat = fiyat.replace(",", ".")

    try:
        return float(fiyat)
    except ValueError:
        return None


# ============================================================
# ASENKRON VERİ ÇEKME
# ============================================================

async def fetch_url(client, url):
    """
    Tek bir URL'yi asenkron olarak çeker.
    """

    try:
        response = await client.get(
            url,
            timeout=30
        )

        return {
            "url": url,
            "status": response.status_code,
            "html": response.text
        }

    except Exception as e:

        return {
            "url": url,
            "status": 0,
            "html": "",
            "error": str(e)
        }


async def fetch_many(urls):
    """
    Birden fazla URL'yi aynı anda çeker.
    asyncio.gather() burada kullanılıyor.
    """

    if not urls:
        return []

    limits = httpx.Limits(
        max_connections=30,
        max_keepalive_connections=20
    )

    async with httpx.AsyncClient(
        follow_redirects=True,
        headers=HEADERS,
        limits=limits
    ) as client:

        tasks = [
            fetch_url(client, url)
            for url in urls
        ]

        results = await asyncio.gather(*tasks)

        return results


# ============================================================
# ÜRÜN LİNKLERİNİ BUL
# ============================================================

def extract_product_links(page):

    if page["status"] != 200:
        return []

    soup = BeautifulSoup(
        page["html"],
        "html.parser"
    )

    product_links = []

    yasakli = [
        "/acik-parfum",
        "/erkek-parfumleri",
        "/kadin-parfumleri",
        "/unisex-parfumler",
        "/yeni-parfumler",
        "/markalar",
        "/parfum-notalari",
        "/parfum",
        "/tester-parfum",
        "/hakkimizda",
        "/iletisim",
        "/gizlilik",
        "/uyelik",
        "/sepet",
        "/hesabim",
        "/giris",
        "/kayit",
        "/arama",
    ]

    menu_kelime = [
        "giriş",
        "kayıt",
        "hesabım",
        "sepet",
        "hakkımızda",
        "gizlilik",
        "sözleşme",
        "iletişim",
        "parfüm notaları",
        "parfümde kalıcılık",
    ]

    for a in soup.find_all("a", href=True):

        href = a.get("href", "").strip()

        if not href:
            continue

        full_url = urljoin(
            BASE_URL,
            href
        )

        parsed = urlparse(full_url)

        # Sadece parfumevi.com.tr
        if parsed.netloc not in (
            "www.parfumevi.com.tr",
            "parfumevi.com.tr"
        ):
            continue

        path = parsed.path.rstrip("/")

        if not path:
            continue

        path_lower = path.lower()

        # Kategori ve sistem sayfalarını çıkar
        if any(
            path_lower == yasak
            or path_lower.startswith(yasak + "/")
            for yasak in yasakli
        ):
            continue

        # Resim, CSS, JS vb.
        if re.search(
            r"\.(jpg|jpeg|png|gif|webp|svg|pdf|css|js)$",
            path_lower
        ):
            continue

        # Sayfalama linkleri
        if "pg=" in parsed.query.lower():
            continue

        # Ürün URL'sinin tek seviyeli olmasını bekliyoruz
        parcalar = [
            x for x in path.split("/")
            if x
        ]

        if len(parcalar) != 1:
            continue

        img = a.find("img")

        anchor_text = temizle_metin(
            a.get_text(" ", strip=True)
        )

        # Görsel veya metin yoksa ürün değildir
        if img is None and not anchor_text:
            continue

        # Menü linklerini çıkar
        if any(
            kelime in anchor_text.lower()
            for kelime in menu_kelime
        ):
            continue

        product_links.append(full_url)

    # Tekrarlananları kaldır
    return list(dict.fromkeys(product_links))


# ============================================================
# NOTA İŞLEMLERİ
# ============================================================

def nota_listesine_cevir(metin):
    """
    'Elma, Bergamot, Yasemin'
    gibi metni listeye çevirir.

    Hiçbir zaman None döndürmez.
    """

    if metin is None:
        return []

    metin = temizle_metin(metin)

    if not metin:
        return []

    parcalar = re.split(
        r"\s*[,;]\s*",
        metin
    )

    sonuc = []

    for nota in parcalar:

        nota = temizle_metin(nota)

        if not nota:
            continue

        # null kelimesini nota olarak alma
        if nota.lower() == "null":
            continue

        if nota not in sonuc:
            sonuc.append(nota)

    return sonuc


def nota_bul(text):
    """
    Sayfadaki üst, orta ve alt notaları bulur.
    """

    text = temizle_metin(text)

    ust = []
    orta = []
    alt = []

    # --------------------------------------------------------
    # ÜST NOTALAR
    # --------------------------------------------------------

    ust_pattern = re.search(
        r"Üst\s+nota(?:lar)?\s*[:\-]?\s*(.*?)"
        r"(?=\s+Orta\s+nota(?:lar)?\s*[:\-]?)",
        text,
        re.IGNORECASE
    )

    # --------------------------------------------------------
    # ORTA NOTALAR
    # --------------------------------------------------------

    orta_pattern = re.search(
        r"Orta\s+nota(?:lar)?\s*[:\-]?\s*(.*?)"
        r"(?=\s+Alt\s+nota(?:lar)?\s*[:\-]?)",
        text,
        re.IGNORECASE
    )

    # --------------------------------------------------------
    # ALT NOTALAR
    # --------------------------------------------------------

    alt_pattern = re.search(
        r"Alt\s+nota(?:lar)?\s*[:\-]?\s*(.*?)"
        r"(?=\s+Cinsiyet\b"
        r"|\s+Ürün\s+Açıklaması\b"
        r"|\s+Koku\s+Türü\b"
        r"|$)",
        text,
        re.IGNORECASE
    )

    if ust_pattern:
        ust = nota_listesine_cevir(
            ust_pattern.group(1)
        )

    if orta_pattern:
        orta = nota_listesine_cevir(
            orta_pattern.group(1)
        )

    if alt_pattern:
        alt = nota_listesine_cevir(
            alt_pattern.group(1)
        )

    return {
        "ust_notalar": ust,
        "orta_notalar": orta,
        "alt_notalar": alt
    }


# ============================================================
# ÜRÜN AYRIŞTIRMA
# ============================================================

def extract_product(page):

    if page["status"] != 200:
        return None

    soup = BeautifulSoup(
        page["html"],
        "html.parser"
    )

    text = temizle_metin(
        soup.get_text(
            " ",
            strip=True
        )
    )

    # --------------------------------------------------------
    # ÜRÜN ADI
    # --------------------------------------------------------

    parfum_adi = ""

    h1 = soup.find("h1")

    if h1:
        parfum_adi = temizle_metin(
            h1.get_text(
                " ",
                strip=True
            )
        )

    # H1 yoksa title kullan
    if not parfum_adi:

        title = soup.find("title")

        if title:
            parfum_adi = temizle_metin(
                title.get_text(
                    " ",
                    strip=True
                )
            )

    if not parfum_adi:
        return None

    # --------------------------------------------------------
    # FİYAT
    # --------------------------------------------------------

    fiyat = fiyat_temizle(text)

    if fiyat is None:
        return None

    # --------------------------------------------------------
    # GÖRSEL
    # --------------------------------------------------------

    gorsel = ""

    image = soup.select_one(
        "a.product-images-item img"
    )

    if image:

        gorsel = (
            image.get("src")
            or image.get("data-src")
            or image.get("data-original")
            or ""
        )

    # Alternatif görsel bul
    if not gorsel:

        image = soup.select_one(
            "img[alt]"
        )

        if image:

            gorsel = (
                image.get("src")
                or image.get("data-src")
                or ""
            )

    if gorsel:

        gorsel = urljoin(
            BASE_URL,
            gorsel
        )

    # --------------------------------------------------------
    # NOTALAR
    # --------------------------------------------------------

    notalar = nota_bul(text)

    tum_notalar = (
        notalar["ust_notalar"]
        + notalar["orta_notalar"]
        + notalar["alt_notalar"]
    )

    notalar_metni = ", ".join(tum_notalar)

    # --------------------------------------------------------
    # ÜRÜN
    # --------------------------------------------------------

    return {

        "parfum_adi": parfum_adi,

        "gorsel": gorsel,

        "fiyat": fiyat,

        "ust_notalar": notalar[
            "ust_notalar"
        ],

        "orta_notalar": notalar[
            "orta_notalar"
        ],

        "alt_notalar": notalar[
            "alt_notalar"
        ],

        "notalar": notalar_metni,

        "kaynak": page["url"]
    }


# ============================================================
# TÜM VERİYİ TOPLA
# ============================================================

async def veri_topla():

    print()
    print("=" * 70)
    print("ASENKRON PARFÜM VERİ MADENCİSİ")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # 1 - KATEGORİ SAYFALARI
    # --------------------------------------------------------

    print(
        "[1] 10 kategori sayfası asenkron olarak çekiliyor..."
    )

    category_pages = await fetch_many(
        CATEGORY_URLS
    )

    basarili_kategori = sum(
        1
        for page in category_pages
        if page["status"] == 200
    )

    print(
        f"[OK] Başarılı kategori sayfası: "
        f"{basarili_kategori}/{len(CATEGORY_URLS)}"
    )

    print()

    # --------------------------------------------------------
    # 2 - ÜRÜN LİNKLERİ
    # --------------------------------------------------------

    print(
        "[2] Ürün bağlantıları bulunuyor..."
    )

    product_links = []

    for page in category_pages:

        links = extract_product_links(
            page
        )

        print(
            f"{page['url']} -> "
            f"{len(links)} ürün bağlantısı"
        )

        product_links.extend(
            links
        )

    # Tekrarlanan ürünleri sil
    product_links = list(
        dict.fromkeys(
            product_links
        )
    )

    print()

    print(
        f"[OK] Toplam benzersiz ürün bağlantısı: "
        f"{len(product_links)}"
    )

    print()

    # --------------------------------------------------------
    # 3 - ÜRÜN SAYFALARINI ÇEK
    # --------------------------------------------------------

    print(
        "[3] Ürün sayfaları asenkron olarak çekiliyor..."
    )

    product_pages = await fetch_many(
        product_links
    )

    basarili_urun = sum(
        1
        for page in product_pages
        if page["status"] == 200
    )

    print(
        f"[OK] Başarılı ürün sayfası: "
        f"{basarili_urun}/{len(product_pages)}"
    )

    print()

    # --------------------------------------------------------
    # 4 - BEAUTIFULSOUP
    # --------------------------------------------------------

    print(
        "[4] BeautifulSoup ile ürünler ayrıştırılıyor..."
    )

    products = []

    for page in product_pages:

        try:

            product = extract_product(
                page
            )

            if product:
                products.append(
                    product
                )

        except Exception as e:

            print(
                "[UYARI] Ürün ayrıştırılamadı:",
                page["url"],
                str(e)
            )

    # --------------------------------------------------------
    # TEKRARLARI TEMİZLE
    # --------------------------------------------------------

    benzersiz = {}

    for product in products:

        key = product["kaynak"]

        benzersiz[key] = product

    products = list(
        benzersiz.values()
    )

    print()

    print(
        f"[OK] Toplam ürün: {len(products)}"
    )

    return {

        "products": products,

        "basarili_kategori": basarili_kategori,

        "toplam_kategori": len(
            CATEGORY_URLS
        )
    }


# ============================================================
# POLARS DÖNÜŞÜMÜ
# ============================================================

def transform_data(products):

    if not products:

        return pl.DataFrame({
            "parfum_adi": pl.Series([], dtype=pl.String),
            "gorsel": pl.Series([], dtype=pl.String),
            "ust_notalar": pl.Series([], dtype=pl.List(pl.String)),
            "orta_notalar": pl.Series([], dtype=pl.List(pl.String)),
            "alt_notalar": pl.Series([], dtype=pl.List(pl.String)),
            "notalar": pl.Series([], dtype=pl.String),
            "fiyat": pl.Series([], dtype=pl.Float64),
            "kaynak": pl.Series([], dtype=pl.String),
        })

    temiz_products = []

    for product in products:

        ust = product.get("ust_notalar", []) or []
        orta = product.get("orta_notalar", []) or []
        alt = product.get("alt_notalar", []) or []

        ust = [
            str(x).strip()
            for x in ust
            if x is not None and str(x).strip() and str(x).lower() != "null"
        ]
        orta = [
            str(x).strip()
            for x in orta
            if x is not None and str(x).strip() and str(x).lower() != "null"
        ]
        alt = [
            str(x).strip()
            for x in alt
            if x is not None and str(x).strip() and str(x).lower() != "null"
        ]

        # Filtreleme için ayrıca düz metin nota alanı oluşturuyoruz.
        # Böylece Polars'ın List(Null) hatası tamamen ortadan kalkıyor.
        notalar = ", ".join(ust + orta + alt)

        temiz_products.append({
            "parfum_adi": str(product.get("parfum_adi", "") or "").strip(),
            "gorsel": str(product.get("gorsel", "") or ""),
            "ust_notalar": ust,
            "orta_notalar": orta,
            "alt_notalar": alt,
            "notalar": notalar,
            "fiyat": product.get("fiyat", 0),
            "kaynak": str(product.get("kaynak", "") or "").strip(),
        })

    # Liste kolonlarının tipini açıkça belirtiyoruz.
    # Böylece bütün değerler boş olsa bile List(Null) oluşmuyor.
    df = pl.DataFrame(
        temiz_products,
        schema={
            "parfum_adi": pl.String,
            "gorsel": pl.String,
            "ust_notalar": pl.List(pl.String),
            "orta_notalar": pl.List(pl.String),
            "alt_notalar": pl.List(pl.String),
            "notalar": pl.String,
            "fiyat": pl.Float64,
            "kaynak": pl.String,
        },
        strict=False,
    )

    return df


# ============================================================
# NOTA FİLTRELEME
# ============================================================

def filtrele_notalar(
    df,
    notalar=None,
    eslesme="herhangi"
):

    if not notalar:
        return df

    # Artık liste kolonlarında list.join() kullanmıyoruz.
    # transform_data() içinde hazırlanan düz "notalar" metnini kullanıyoruz.
    df = df.with_columns(
        pl.col("notalar")
        .cast(pl.String)
        .fill_null("")
        .str.to_lowercase()
        .alias("_tum_notalar")
    )

    kosullar = []

    for nota in notalar:

        nota = temizle_metin(nota).lower()

        if not nota:
            continue

        desen = re.escape(nota)

        kosullar.append(
            pl.col("_tum_notalar").str.contains(desen)
        )

    if not kosullar:
        return df.drop("_tum_notalar")

    if eslesme == "hepsi":
        kosul = kosullar[0]
        for item in kosullar[1:]:
            kosul = kosul & item
    else:
        kosul = kosullar[0]
        for item in kosullar[1:]:
            kosul = kosul | item

    return df.filter(kosul).drop("_tum_notalar")


# ============================================================
# JSON OLUŞTUR
# ============================================================

def create_json(df):

    veriler = df.to_dicts()

    with open(
        "sonuclar.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            veriler,
            file,
            ensure_ascii=False,
            indent=4
        )

    return veriler


# ============================================================
# PROGRAMI ÇALIŞTIR
# ============================================================

if __name__ == "__main__":

    start_time = time.perf_counter()

    sonuc = asyncio.run(
        veri_topla()
    )

    products = sonuc[
        "products"
    ]

    # Polars dönüşümü
    df = transform_data(
        products
    )

    # JSON oluştur
    veriler = create_json(
        df
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    print()

    print("=" * 70)

    print(
        f"Toplam ürün: {len(veriler)}"
    )

    print(
        f"Toplam süre: {elapsed:.4f} saniye"
    )

    print(
        "sonuclar.json oluşturuldu."
    )

    print("=" * 70)