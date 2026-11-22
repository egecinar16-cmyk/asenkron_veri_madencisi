from flask import Flask, render_template, jsonify, request
import asyncio
import time

from main import (
    veri_topla,
    transform_data,
    filtrele_notalar,
    create_json
)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/cek")
def api_cek():
    try:
        start_time = time.perf_counter()

        nota_parametresi = request.args.get("notalar", "")
        eslesme = request.args.get("eslesme", "herhangi")

        secilen_notalar = [
            nota.strip()
            for nota in nota_parametresi.split(",")
            if nota.strip()
        ]

        sonuc = asyncio.run(veri_topla())

        products = sonuc["products"]
        basarili_kategori = sonuc["basarili_kategori"]
        toplam_kategori = sonuc["toplam_kategori"]

        df = transform_data(products)
        ham_urun = df.height

        if secilen_notalar:
            df = filtrele_notalar(
                df,
                secilen_notalar,
                eslesme
            )

        veriler = create_json(df)

        elapsed_time = time.perf_counter() - start_time

        return jsonify({
            "basarili_sayfa": basarili_kategori,
            "toplam_sayfa": toplam_kategori,
            "ham_urun": ham_urun,
            "toplam_urun": len(veriler),
            "sure": round(elapsed_time, 4),
            "secilen_notalar": secilen_notalar,
            "eslesme": eslesme,
            "veriler": veriler
        })

    except Exception as e:
        print("[HATA]", str(e))
        return jsonify({"hata": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
