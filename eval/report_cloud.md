# BULUT RAG Doğruluk Raporu (Voyage + Pinecone)

- Toplam soru: **5**
- Retrieval (kod bağlamda): **4/5** → **%80.0**
- Cevap doğruluk (keyword): **5/5** → **%100.0**
- Birleşik: **4/5** → **%80.0**
- **LLM-as-judge ortalama: 4.20/5.0** (5 skorlu)
- Judge kabul (≥3/5): **4/5** → **%80.0**
- Ortalama süre: **10.06s**

## Bölüm Bazlı
| Bölüm | N | Retrieval % | KW % | Judge Ort |
|---|---:|---:|---:|---:|
| bilgisayar | 5 | %80 | %100 | 4.20/5 |

## Düşük Skorlu Vakalar (judge < 3) — 1 adet

### `comp_003` (bilgisayar) — **1/5**
**Soru:** COMP 201 nedir, hangi konuları içerir?
**Hakem:** Cevap COMP 201 dersinin adını/içeriğini belirtmemiştir.
**Cevap:** _2023 Bilgisayar Mühendisliği müfredatı hakkında bilgi verilmemiştir. Ancak 2016 müfredatına göre, COMP 201 Yazılım Mühendisliği dersinin içeriği hakkında bilgi bulunmamaktadır. 

2016 müfredatına göre, 2. yıl Bahar dönemi (4. dönem) seçmeli derslerinden biri olan COMP 202 Yazılım Mühendisliği'nin 3 teorik saatlik dersi vardır, 0 laboratuvar saati, 3 kredi ve 7 AKTS ile verilir. COMP 101 Programlam_
