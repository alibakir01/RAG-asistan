# BULUT RAG Dogruluk Raporu — 200 soru (tum bolumler)

- Toplam soru: **200** (13 bolum, veriden otomatik ground-truth)
- Gercek cevaplanan: **199** | Ucretsiz-kota (429, altyapi): **1**

## Cevaplanan sorularda skor
- Retrieval (Hit@K): **%100.0**
- LLM-as-judge ort: **5.00/5** (kabul >=3: **%100**)
- Gercek basarisizlik: **0**

## Bolum bazli (cevaplananlar)
| Bolum | N | Retrieval % | Judge>=3 % |
|---|---:|---:|---:|
| bilgisayar | 20 | %100 | %100 |
| biyomuhendislik | 15 | %100 | %100 |
| ekonomi | 15 | %100 | %100 |
| elektrik | 16 | %100 | %100 |
| endustri | 16 | %100 | %100 |
| insaat | 16 | %100 | %100 |
| isletme | 15 | %100 | %100 |
| makine | 14 | %100 | %100 |
| malzeme | 14 | %100 | %100 |
| mbg | 12 | %100 | %92 |
| mimarlik | 16 | %100 | %100 |
| psikoloji | 14 | %100 | %100 |
| siyaset | 16 | %100 | %100 |

## Not
1 MBG sorusu (mbg_004) ucretsiz LLM kotasi (429) yuzunden skorlanamadi — model hatasi degil. Kotalar sifirlaninca: python eval/run_eval_cloud.py --set eval/eval_retry2.json