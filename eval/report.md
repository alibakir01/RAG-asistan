# RAG Doğruluk Raporu (v2 — LLM-as-judge ile)

- Toplam soru: **145**
- Retrieval başarı (Hit@K): **134/145** → **%92.4**
- Cevap doğruluk (keyword match): **139/145** → **%95.9**
- Hem retrieval hem keyword: **130/145** → **%89.7**
- **LLM-as-judge ortalama skor: 4.03/5.0** (145 skorlu)
- LLM-as-judge kabul (≥3/5): **114/145** → **%78.6**
- LLM-as-judge mükemmel (≥4/5): **110/145** → **%75.9**
- Hata: **0**
- Ortalama **TTFT** (algılanan gecikme): **14.73s**
- Ortalama toplam cevap süresi: **28.21s**

## Bölüm Bazlı Sonuç

| Bölüm | N | Retrieval % | KW % | Birleşik % | Judge Ort | Judge ≥3 | Ort. TTFT | Ort. Toplam |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bilgisayar | 32 | %88 | %81 | %75 | 4.16/5 | %81 | 17.2s | 32.9s |
| ekonomi | 20 | %100 | %100 | %100 | 4.60/5 | %90 | 14.3s | 24.0s |
| elektrik | 12 | %100 | %100 | %100 | 4.17/5 | %83 | 18.7s | 36.4s |
| endustri | 12 | %83 | %100 | %83 | 3.42/5 | %67 | 7.8s | 18.1s |
| insaat | 12 | %83 | %100 | %83 | 3.08/5 | %58 | 15.7s | 28.4s |
| isletme | 20 | %90 | %100 | %90 | 4.05/5 | %80 | 13.2s | 22.6s |
| makine | 12 | %92 | %100 | %92 | 3.17/5 | %58 | 12.6s | 26.3s |
| malzeme | 10 | %100 | %100 | %100 | 4.60/5 | %90 | 19.2s | 36.7s |
| mimarlik | 15 | %100 | %100 | %100 | 4.47/5 | %87 | 12.4s | 28.4s |

## Detaylı Sonuçlar

| # | Bölüm | Soru | Retrieval | KW | Judge | TTFT |
|---|---|---|:---:|:---:|:---:|---:|
| 1 | bilgisayar | COMP 101 dersi kaç AKTS? | ✅ | ✅ | 5/5 | 10.1s |
| 2 | bilgisayar | COMP 305 dersinin ön şartı nedir? | ✅ | ❌ | 5/5 | 11.8s |
| 3 | bilgisayar | COMP 201 nedir, hangi konuları içerir? | ❌ | ❌ | 0/5 | 22.4s |
| 4 | bilgisayar | 2025 girişliyim, 1. dönem hangi dersleri alıyorum? | ✅ | ✅ | 5/5 | 0.2s |
| 5 | bilgisayar | 2023 girişliyim, 3. dönem dersleri neler? | ✅ | ✅ | 5/5 | 0.2s |
| 6 | bilgisayar | Bilgisayar Mühendisliği stajı kaç iş günü? | ✅ | ✅ | 5/5 | 16.7s |
| 7 | bilgisayar | Bilgisayar bölümünde mezuniyet için kaç AKTS gerekli? | ✅ | ❌ | 5/5 | 23.4s |
| 8 | bilgisayar | COMP 401 dersi var mı, varsa nedir? | ❌ | ✅ | 5/5 | 19.0s |
| 9 | bilgisayar | COMP 102 dersinin ön şartı nedir? | ❌ | ❌ | 0/5 | 17.0s |
| 10 | bilgisayar | Algoritmalar dersi kaç AKTS? | ✅ | ✅ | 5/5 | 9.7s |
| 11 | bilgisayar | Yapay zeka ile ilgili dersler hangileri? | ✅ | ✅ | 5/5 | 21.3s |
| 12 | bilgisayar | MATH 101 hangi dönemde alınır? | ✅ | ❌ | 5/5 | 6.2s |
| 13 | bilgisayar | Bitirme projesi kaç dönem sürer? | ✅ | ✅ | 5/5 | 33.1s |
| 14 | bilgisayar | COMP 391 nedir? | ❌ | ✅ | 0/5 | 31.2s |
| 15 | bilgisayar | 2021 müfredatında COMP 305 hangi dönemde? | ✅ | ❌ | 5/5 | 9.8s |
| 16 | bilgisayar | Operating Systems dersi var mı? | ✅ | ✅ | 5/5 | 37.0s |
| 17 | bilgisayar | Veri tabanı dersi hangi dönemde alınır? | ✅ | ✅ | 5/5 | 26.4s |
| 18 | bilgisayar | Bilgisayar mühendisliği toplam kaç ders alıyorum? | ✅ | ✅ | 0/5 | 18.8s |
| 19 | bilgisayar | COMP 462 dersinin ön şartı? | ✅ | ✅ | 5/5 | 5.0s |
| 20 | bilgisayar | Seçmeli ders havuzunda kaç COMP dersi var? | ✅ | ✅ | 2/5 | 11.6s |
| 21 | bilgisayar | 2016 ile 2023 müfredatı arasında fark var mı? | ✅ | ✅ | 5/5 | 0.0s |
| 22 | bilgisayar | ENG 101 kaç AKTS? | ✅ | ✅ | 5/5 | 5.0s |
| 23 | bilgisayar | GLB 101 ne dersi? | ✅ | ✅ | 5/5 | 3.0s |
| 24 | bilgisayar | Capstone projesi için ön koşullar nelerdir? | ✅ | ✅ | 5/5 | 24.9s |
| 25 | bilgisayar | COMP 491 hakkında bilgi | ✅ | ✅ | 5/5 | 4.7s |
| 26 | ekonomi | ECON 499 staj dersi kaç AKTS? | ✅ | ✅ | 5/5 | 13.4s |
| 27 | ekonomi | ECON 499 stajının ön koşulu nedir? | ✅ | ✅ | 5/5 | 15.2s |
| 28 | ekonomi | ECON 499 değerlendirmesi nasıl? | ✅ | ✅ | 5/5 | 3.5s |
| 29 | ekonomi | ECON 499 iş yükü hesabı nedir? | ✅ | ✅ | 5/5 | 6.4s |
| 30 | ekonomi | Ekonomi 1. yıl güz dersleri? | ✅ | ✅ | 2/5 | 8.9s |
| 31 | ekonomi | Ekonomi bölümünde kaç seçmeli kategori var? | ✅ | ✅ | 5/5 | 11.1s |
| 32 | ekonomi | Davranışsal iktisat dersi var mı? | ✅ | ✅ | 5/5 | 24.4s |
| 33 | ekonomi | ECON 101 dersi hakkında | ✅ | ✅ | 5/5 | 6.0s |
| 34 | ekonomi | ECON 201 ön şartı? | ✅ | ✅ | 5/5 | 10.9s |
| 35 | ekonomi | Ekonomi stajı için kaç AKTS tamamlamış olmam gerekir? | ✅ | ✅ | 5/5 | 53.5s |
| 36 | ekonomi | Ekonomi stajı kaç iş günü? | ✅ | ✅ | 5/5 | 20.2s |
| 37 | ekonomi | Mikroekonometri dersi nerede? | ✅ | ✅ | 5/5 | 17.8s |
| 38 | ekonomi | Ekonomi 4. yıl dersleri nelerdir? | ✅ | ✅ | 5/5 | 0.4s |
| 39 | ekonomi | Ekonomi bölümünde matematik dersleri hangileri? | ✅ | ✅ | 5/5 | 14.7s |
| 40 | ekonomi | Oyun teorisi dersi alabilir miyim? | ✅ | ✅ | 5/5 | 22.4s |
| 41 | ekonomi | Ekonomi 2. dönem dersleri? | ✅ | ✅ | 1/5 | 0.6s |
| 42 | ekonomi | ECN kodlu dersler ne için? | ✅ | ✅ | 5/5 | 20.2s |
| 43 | ekonomi | ECD kodlu dersler kimler için? | ✅ | ✅ | 5/5 | 21.3s |
| 44 | ekonomi | Toplam kaç seçmeli ders var ekonomide? | ✅ | ✅ | 4/5 | 9.7s |
| 45 | ekonomi | ECON 499 dersinin amacı nedir? | ✅ | ✅ | 5/5 | 4.8s |
| 46 | isletme | BA 499 staj dersi kaç AKTS? | ✅ | ✅ | 2/5 | 3.9s |
| 47 | isletme | İşletme stajı kaç iş günü? | ✅ | ✅ | 4/5 | 24.5s |
| 48 | isletme | İşletme 1. yıl güz dersleri? | ✅ | ✅ | 5/5 | 10.9s |
| 49 | isletme | BA 101 nedir? | ❌ | ✅ | 0/5 | 24.3s |
| 50 | isletme | İşletme bölümünde pazarlama dersleri hangileri? | ✅ | ✅ | 5/5 | 16.3s |
| 51 | isletme | BA 201 ön şartı? | ❌ | ✅ | 0/5 | 21.3s |
| 52 | isletme | İşletme 4. yıl dersleri | ✅ | ✅ | 5/5 | 0.3s |
| 53 | isletme | İşletme seçmeli ders havuzları nelerdir? | ✅ | ✅ | 5/5 | 12.4s |
| 54 | isletme | Finans dersi var mı işletmede? | ✅ | ✅ | 5/5 | 20.4s |
| 55 | isletme | BA 499 değerlendirmesi nasıl? | ✅ | ✅ | 2/5 | 7.2s |
| 56 | isletme | İşletme stajı ön koşulu nedir? | ✅ | ✅ | 5/5 | 18.3s |
| 57 | isletme | Muhasebe dersi hangi dönemde? | ✅ | ✅ | 5/5 | 12.6s |
| 58 | isletme | BA 301 ne dersi? | ✅ | ✅ | 5/5 | 2.8s |
| 59 | isletme | İşletme eğitim dili nedir? | ✅ | ✅ | 5/5 | 22.2s |
| 60 | isletme | İşletme mufredat yılı? | ✅ | ✅ | 5/5 | 20.9s |
| 61 | isletme | BA 401 nedir? | ✅ | ✅ | 5/5 | 2.6s |
| 62 | isletme | İşletme 2. yıl bahar dersleri? | ✅ | ✅ | 5/5 | 7.9s |
| 63 | isletme | İnsan kaynakları dersi var mı? | ✅ | ✅ | 5/5 | 17.5s |
| 64 | isletme | İşletme programında strateji dersi kaç AKTS? | ✅ | ✅ | 3/5 | 15.2s |
| 65 | isletme | BA 499 amacı nedir? | ✅ | ✅ | 5/5 | 3.6s |
| 66 | mimarlik | ARCH 101 dersi nedir? | ✅ | ✅ | 5/5 | 3.2s |
| 67 | mimarlik | Mimarlık 1. yıl güz dersleri? | ✅ | ✅ | 1/5 | 18.4s |
| 68 | mimarlik | Mimarlık stajı hakkında bilgi | ✅ | ✅ | 5/5 | 20.8s |
| 69 | mimarlik | Mimari proje stüdyosu kaç dönem? | ✅ | ✅ | 5/5 | 18.1s |
| 70 | mimarlik | ARCH 201 ön şartı? | ✅ | ✅ | 5/5 | 2.7s |
| 71 | mimarlik | Mimarlık eğitim dili? | ✅ | ✅ | 5/5 | 20.2s |
| 72 | mimarlik | Mimarlık seçmeli dersleri kaç tane? | ✅ | ✅ | 1/5 | 21.7s |
| 73 | mimarlik | ARCH 301 hangi dönemde? | ✅ | ✅ | 5/5 | 3.2s |
| 74 | mimarlik | Mimarlık 4. yıl dersleri | ✅ | ✅ | 5/5 | 0.2s |
| 75 | mimarlik | Mimarlık tarihi dersi var mı? | ✅ | ✅ | 5/5 | 21.6s |
| 76 | mimarlik | ARCH 102 kaç AKTS? | ✅ | ✅ | 5/5 | 3.0s |
| 77 | mimarlik | Mimarlık stajı kaç iş günü? | ✅ | ✅ | 5/5 | 22.0s |
| 78 | mimarlik | Yapı statiği dersi var mı? | ✅ | ✅ | 5/5 | 16.3s |
| 79 | mimarlik | ARCH 401 nedir? | ✅ | ✅ | 5/5 | 2.6s |
| 80 | mimarlik | Mimarlık 2. yıl güz dersleri? | ✅ | ✅ | 5/5 | 11.4s |
| 81 | makine | ME 101 dersi nedir? | ✅ | ✅ | 5/5 | 4.1s |
| 82 | makine | Makine 1. yıl bahar dersleri? | ✅ | ✅ | 5/5 | 12.8s |
| 83 | makine | Termodinamik dersi hangi dönemde? | ✅ | ✅ | 5/5 | 22.3s |
| 84 | makine | Makine stajı kaç iş günü? | ✅ | ✅ | 2/5 | 19.4s |
| 85 | makine | ME 201 ön şartı? | ❌ | ✅ | 0/5 | 22.7s |
| 86 | makine | Akışkanlar mekaniği dersi var mı? | ✅ | ✅ | 5/5 | 18.7s |
| 87 | makine | Makine 4. yıl dersleri? | ✅ | ✅ | 3/5 | 0.3s |
| 88 | makine | ME 301 nedir? | ✅ | ✅ | 5/5 | 3.6s |
| 89 | makine | Makine 2021 ve 2025 müfredatları farklı mı? | ✅ | ✅ | 2/5 | 0.1s |
| 90 | makine | Bitirme projesi makine için nedir? | ✅ | ✅ | 5/5 | 15.0s |
| 91 | makine | Mukavemet dersi hangi dönemde? | ✅ | ✅ | 0/5 | 20.0s |
| 92 | makine | Makine seçmeli dersleri | ✅ | ✅ | 1/5 | 12.9s |
| 93 | endustri | IE 101 dersi nedir? | ❌ | ✅ | 0/5 | 7.2s |
| 94 | endustri | Endüstri 1. yıl güz dersleri? | ✅ | ✅ | 2/5 | 5.3s |
| 95 | endustri | Endüstri stajı kaç iş günü? | ✅ | ✅ | 5/5 | 21.4s |
| 96 | endustri | Yöneylem araştırması dersi var mı? | ✅ | ✅ | 5/5 | 9.4s |
| 97 | endustri | IE 201 ön şartı? | ✅ | ✅ | 2/5 | 2.9s |
| 98 | endustri | İstatistik dersi hangi dönemde? | ✅ | ✅ | 5/5 | 15.1s |
| 99 | endustri | Endüstri 4. yıl dersleri? | ✅ | ✅ | 4/5 | 0.2s |
| 100 | endustri | IE 301 hakkında bilgi | ❌ | ✅ | 0/5 | 14.1s |
| 101 | endustri | Simulasyon dersi var mı? | ✅ | ✅ | 5/5 | 6.4s |
| 102 | endustri | 2016 ve 2021 endüstri müfredatları farklı mı? | ✅ | ✅ | 5/5 | 0.1s |
| 103 | endustri | Endüstri 2. dönem dersleri? | ✅ | ✅ | 5/5 | 0.4s |
| 104 | endustri | Üretim planlama dersi nerede? | ✅ | ✅ | 3/5 | 11.4s |
| 105 | elektrik | EE 101 dersi nedir? | ✅ | ✅ | 5/5 | 9.7s |
| 106 | elektrik | Elektrik 1. yıl güz dersleri? | ✅ | ✅ | 1/5 | 19.8s |
| 107 | elektrik | Elektrik stajı kaç iş günü? | ✅ | ✅ | 5/5 | 16.4s |
| 108 | elektrik | Devre teorisi dersi hangi dönemde? | ✅ | ✅ | 5/5 | 20.3s |
| 109 | elektrik | EE 201 ön şartı? | ✅ | ✅ | 5/5 | 6.9s |
| 110 | elektrik | Sinyaller ve sistemler dersi var mı? | ✅ | ✅ | 5/5 | 22.0s |
| 111 | elektrik | EE Capsule sistemi nedir? | ✅ | ✅ | 5/5 | 36.8s |
| 112 | elektrik | EE 301 nedir? | ✅ | ✅ | 5/5 | 15.0s |
| 113 | elektrik | Elektrik 4. yıl dersleri? | ✅ | ✅ | 3/5 | 0.3s |
| 114 | elektrik | Güç sistemleri dersi var mı? | ✅ | ✅ | 5/5 | 42.1s |
| 115 | elektrik | EE 2025 müfredatı hangi öğrenciler için? | ✅ | ✅ | 1/5 | 0.3s |
| 116 | elektrik | Elektrik bitirme projesi | ✅ | ✅ | 5/5 | 35.4s |
| 117 | insaat | CE 101 dersi nedir? | ✅ | ✅ | 5/5 | 18.5s |
| 118 | insaat | İnşaat 1. yıl güz dersleri? | ✅ | ✅ | 2/5 | 11.0s |
| 119 | insaat | İnşaat stajı kaç iş günü? | ✅ | ✅ | 5/5 | 13.9s |
| 120 | insaat | Statik dersi hangi dönemde? | ✅ | ✅ | 0/5 | 19.9s |
| 121 | insaat | CE 201 ön şartı? | ❌ | ✅ | 0/5 | 22.5s |
| 122 | insaat | Beton teknolojisi dersi var mı? | ✅ | ✅ | 5/5 | 23.7s |
| 123 | insaat | İnşaat 4. yıl dersleri? | ✅ | ✅ | 4/5 | 0.2s |
| 124 | insaat | CE 301 nedir? | ❌ | ✅ | 0/5 | 20.0s |
| 125 | insaat | Geoteknik dersi var mı? | ✅ | ✅ | 5/5 | 24.4s |
| 126 | insaat | Su yapıları dersi | ✅ | ✅ | 5/5 | 19.8s |
| 127 | insaat | İnşaat 2025 müfredatı hangi giriş yılları için? | ✅ | ✅ | 1/5 | 0.2s |
| 128 | insaat | Yapı malzemeleri dersi | ✅ | ✅ | 5/5 | 13.9s |
| 129 | malzeme | MSNE 101 dersi nedir? | ✅ | ✅ | 5/5 | 5.0s |
| 130 | malzeme | Malzeme 1. yıl güz dersleri? | ✅ | ✅ | 5/5 | 12.7s |
| 131 | malzeme | MSNE stajı kaç iş günü? | ✅ | ✅ | 5/5 | 14.8s |
| 132 | malzeme | Nanoteknoloji dersi var mı? | ✅ | ✅ | 5/5 | 17.0s |
| 133 | malzeme | MSNE 201 ön şartı? | ✅ | ✅ | 1/5 | 3.2s |
| 134 | malzeme | Polimerler dersi var mı? | ✅ | ✅ | 5/5 | 48.5s |
| 135 | malzeme | MSNE 4. yıl dersleri? | ✅ | ✅ | 5/5 | 0.2s |
| 136 | malzeme | MSNE 301 nedir? | ✅ | ✅ | 5/5 | 7.8s |
| 137 | malzeme | Karakterizasyon dersi var mı? | ✅ | ✅ | 5/5 | 57.5s |
| 138 | malzeme | Malzeme bitirme projesi | ✅ | ✅ | 5/5 | 25.2s |
| 139 | bilgisayar | Erasmus başvurusu nasıl yapılır? | ✅ | ✅ | 5/5 | 34.5s |
| 140 | bilgisayar | Erasmus için minimum not ortalaması? | ✅ | ✅ | 5/5 | 23.7s |
| 141 | bilgisayar | Yatay geçiş şartları? | ✅ | ✅ | 5/5 | 24.3s |
| 142 | bilgisayar | Kayıt dondurma nasıl yapılır? | ✅ | ✅ | 5/5 | 29.6s |
| 143 | bilgisayar | Akademik takvim ne zaman güz dönemi başlar? | ✅ | ✅ | 1/5 | 21.6s |
| 144 | bilgisayar | Final sınavları ne zaman? | ✅ | ✅ | 5/5 | 22.3s |
| 145 | bilgisayar | İngilizce hazırlık zorunlu mu? | ✅ | ✅ | 5/5 | 24.7s |

## Düşük Skorlu Vakalar (judge < 3) — 31 adet

### `comp_003` (bilgisayar) — judge: **0/5**
**Soru:** COMP 201 nedir, hangi konuları içerir?
**Kriter:** _Cevap COMP 201 dersinin adını/içeriğini (veri yapıları veya nesne yönelimli prog.) belirtmeli._
**Hakem gerekçesi:** Cevap dersin adı ve içeriği hakkında bilgi vermedi, kriteri karşılamıyor.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `comp_009` (bilgisayar) — judge: **0/5**
**Soru:** COMP 102 dersinin ön şartı nedir?
**Kriter:** _Cevap COMP 102'nin ön koşulunu belirtmeli (varsa kod, yoksa 'yok')._
**Hakem gerekçesi:** Cevap ön koşulu belirtmedi, bilgi eksik.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `comp_014` (bilgisayar) — judge: **0/5**
**Soru:** COMP 391 nedir?
**Kriter:** _Cevap COMP 391 (yaz stajı / summer practice) konusunda bilgi vermeli._
**Hakem gerekçesi:** Kriteri karşılamıyor, COMP 391 hakkında bilgi vermemiş.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `comp_018` (bilgisayar) — judge: **0/5**
**Soru:** Bilgisayar mühendisliği toplam kaç ders alıyorum?
**Kriter:** _Cevap toplam ders sayısı veya 8 dönemdeki yaklaşık ders sayısını vermeli._
**Hakem gerekçesi:** Cevap soruya yanıt vermemiş, bilgi eksikliği belirtmiştir.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `ba_004` (isletme) — judge: **0/5**
**Soru:** BA 101 nedir?
**Kriter:** _Cevap BA 101 dersinin adını ve özelliklerini (AKTS/içerik) belirtmeli._
**Hakem gerekçesi:** Cevap dersin adı ve AKTS/içerik gibi istenen bilgileri vermedi.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `ba_006` (isletme) — judge: **0/5**
**Soru:** BA 201 ön şartı?
**Kriter:** _Cevap BA 201 ön koşulunu belirtmeli._
**Hakem gerekçesi:** Cevap, BA 201 ön koşulunu belirtmedi ve soruya yanıt vermedi.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `me_005` (makine) — judge: **0/5**
**Soru:** ME 201 ön şartı?
**Kriter:** _Cevap ME 201 ön koşulunu belirtmeli._
**Hakem gerekçesi:** Cevap, ME 201 ön koşulunu belirtmedi ve soruya yanıt vermedi.
**Cevap (ilk 400 char):** _ME 201 dersinin ön şartı hakkında elimdeki dokümanlarda bir bilgi bulunmamaktadır. (Bu bilgi elimdeki dokümanlarda yok)_

### `me_011` (makine) — judge: **0/5**
**Soru:** Mukavemet dersi hangi dönemde?
**Kriter:** _Cevap mukavemet (strength of materials) dersinin dönemini belirtmeli._
**Hakem gerekçesi:** Cevap, mukavemet dersinin dönemini belirtmediği için kriteri karşılamamaktadır.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok. (Kaynak 1)_

### `ie_001` (endustri) — judge: **0/5**
**Soru:** IE 101 dersi nedir?
**Kriter:** _Cevap IE 101 dersinin adını/içeriğini belirtmeli._
**Hakem gerekçesi:** Cevap, IE 101 dersinin adını veya içeriğini belirtmediği için kriteri karşılamamaktadır.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok. (Verilen kaynaklarda **IE 101** dersiyle ilgili bir tanım, kod, kredi, AKTS veya ön şart bilgisi bulunmamaktadır.)_

### `ie_008` (endustri) — judge: **0/5**
**Soru:** IE 301 hakkında bilgi
**Kriter:** _Cevap IE 301 dersinin adını belirtmeli._
**Hakem gerekçesi:** Cevap dersin adını belirtmedi ve soruya yanıt vermedi.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `ce_004` (insaat) — judge: **0/5**
**Soru:** Statik dersi hangi dönemde?
**Kriter:** _Cevap statik (statics) dersinin dönemini/kodunu belirtmeli._
**Hakem gerekçesi:** Cevap, statik dersinin dönemini/kodunu belirtmediği için kriteri karşılamamaktadır.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `ce_005` (insaat) — judge: **0/5**
**Soru:** CE 201 ön şartı?
**Kriter:** _Cevap CE 201 ön koşulunu belirtmeli._
**Hakem gerekçesi:** Cevap, CE 201 ön koşulunu belirtmediği için kriteri karşılamamaktadır.
**Cevap (ilk 400 char):** _**CE 201 dersinin ön şartı:** Bu bilgi elimdeki dokümanlarda yok. (Bağlamda “Ön şart:” alanı yalnızca listelenen dersler için mevcut.)_

### `ce_008` (insaat) — judge: **0/5**
**Soru:** CE 301 nedir?
**Kriter:** _Cevap CE 301'in adını belirtmeli._
**Hakem gerekçesi:** Cevap CE 301'in adını vermedi ve soruya yanıt vermedi.
**Cevap (ilk 400 char):** _Bu bilgi elimdeki dokümanlarda yok._

### `ekon_016` (ekonomi) — judge: **1/5**
**Soru:** Ekonomi 2. dönem dersleri?
**Kriter:** _Cevap Ekonomi 1. yıl bahar dönemi derslerini listelemeli._
**Hakem gerekçesi:** Liste gerçek ekonomi 1. yıl bahar dönemi derslerini tam olarak yansıtmıyor, çoğu alakasız ve eksik.
**Cevap (ilk 400 char):** _## 2025 Ekonomi müfredatı — seçili dönem dersleri  ### 1. yıl Bahar dönemi (2. dönem) — 8 ders - **CP 100** — Career Planning     T: 1, L: 0, Kredi: 1, AKTS: 1 · Ön şart: yok - **ECON 102** — Exploring Economics II     T: 3, L: 0, Kredi: 3, AKTS: 5 · Ön şart: yok - **ECON 3NX2** — Non-Departmental Elective (3AKTS)     T: -, L: -, Kredi: -, AKTS: 3 · Ön şart: yok - **ENG 102** — English II     T: 4_

### `arch_002` (mimarlik) — judge: **1/5**
**Soru:** Mimarlık 1. yıl güz dersleri?
**Kriter:** _Cevap mimarlık 1. dönem derslerini en az 5 ders olarak listelemeli._
**Hakem gerekçesi:** Sadece üç ders listelenmiş, kriter olan en az beş ders sağlanmamış.
**Cevap (ilk 400 char):** _**Mimarlık 1. yıl – Güz dönemi (1. dönem) dersleri**  1. **ARCH 101 – Tasarım 1: Temel Tasarım**      - Haftalık saat: 12 (T: 6 + L: 6)      - Kredi: 9, AKTS: 12      - Tip: Zorunlu, Dil: İngilizce      - Ön şart: **yok**      *(Kaynak 1, Kaynak 2)*    2. **ARCH 131 – Günümüz Mimarlığı**      - Haftalık saat: 3 (T: 3 + L: 0)      - Kredi: 3, AKTS: 3      - Tip: Zorunlu, Dil: İngilizce      - Ön şa_

### `arch_007` (mimarlik) — judge: **1/5**
**Soru:** Mimarlık seçmeli dersleri kaç tane?
**Kriter:** _Cevap mimarlık seçmeli dersi sayısını veya örnek dersler vermeli._
**Hakem gerekçesi:** Cevap kesin bir sayı veriyor ancak doğruluğu kanıtlanmadığı ve genelleme yapılmadığı için kriteri tam karşılamıyor.
**Cevap (ilk 400 char):** _Mimarlık programında **toplam 54 adet seçmeli ders** bulunmaktadır.    - **ARCG Seçmeli I (Elective I)** – 10 ders (3 AKTS her biri)   - **ARCD Seçmeli II (Elective II)** – 24 ders (5 AKTS her biri)   - **ARCA Seçmeli III (Elective III)** – 7 ders (6 AKTS her biri)   - **Değişim/Transfer Seçmelileri** – 13 ders (AKTS belirtilmemiş)    Bu bilgiler **[Kaynak 1] – “AGÜ Mimarlık Bölümü — Seçmeli Ders _

### `me_012` (makine) — judge: **1/5**
**Soru:** Makine seçmeli dersleri
**Kriter:** _Cevap makine seçmeli derslerinden en az 1-2 örnek vermeli veya kategori sayısını belirtmeli._
**Hakem gerekçesi:** Cevap makine seçmeli derslerine özgü örnekler vermedi, sadece ortak seçmeli dersleri listeler
**Cevap (ilk 400 char):** _**Makine Mühendisliği – Seçmeli Dersler (Ortak Zorunlu Seçmeli – GLB Havuzu)**    Aşağıdaki dört ders, Bilgisayar, Makine ve Endüstri Mühendisliği bölümlerinin **tüm öğrencileri** (2025 müfredatı kapsamında) alması zorunlu olan **ortak seçmeli** derslerdir. Her biri 3 kredi / 4 AKTS değerindedir.  | Ders Kodu | Ders Adı | Teorik Saat | Lab Saat | Kredi | AKTS | |-----------|----------|------------_

### `ee_002` (elektrik) — judge: **1/5**
**Soru:** Elektrik 1. yıl güz dersleri?
**Kriter:** _Cevap EE 1. dönem derslerini listelemeli._
**Hakem gerekçesi:** Cevap çok eksik ve gerçek EE 1. yıl güz derslerini doğru şekilde listelemiyor.
**Cevap (ilk 400 char):** _**Elektrik‑Elektronik Mühendisliği 1. sınıf – Güz (1. dönem) dersleri**  Aşağıdaki listeler, **giriş yılına göre geçerli müfredatı** (kaynaklarda verilen “ee_…_temiz.csv” dosyalarından) içermektedir. Ders kodu, adı, teorik‑lab saatleri, kredi ve AKTS bilgileri aynı satırda verilmiştir.  ---  ### 1. 2025 müfredatı (2025 ve sonrası giriş yapan öğrenciler) – **Kaynak 1, 3, 4, 7** | Ders Kodu | Ders A_

### `ee_011` (elektrik) — judge: **1/5**
**Soru:** EE 2025 müfredatı hangi öğrenciler için?
**Kriter:** _Cevap 2025 müfredatının hangi giriş yıllılar için olduğunu belirtmeli._
**Hakem gerekçesi:** Cevap müfredatı listeliyor ancak 2025 giriş yılına ait olduğunu belirtmiyor.
**Cevap (ilk 400 char):** _## 2025 Elektrik-Elektronik Mühendisliği müfredatı — seçili dönem dersleri  ### 1. yıl Güz dönemi (1. dönem) — 7 ders - **EE 101** — Introduction to Programming     T: 2, L: 2, Kredi: 3, AKTS: 5 · Ön şart: yok - **ENG 101** — English 1     T: 4, L: 0, Kredi: 4, AKTS: 4 · Ön şart: yok - **GLB 101** — AGU Ways     T: 3, L: 0, Kredi: 3, AKTS: 4 · Ön şart: yok - **MATH 161** — Calculus I for Electrica_

### `ce_011` (insaat) — judge: **1/5**
**Soru:** İnşaat 2025 müfredatı hangi giriş yılları için?
**Kriter:** _Cevap 2025 müfredatının hangi giriş yıllıları kapsadığını belirtmeli._
**Hakem gerekçesi:** Cevap müfredatı detaylandırıyor ancak hangi giriş yıllarını kapsadığı sorusuna yanıt vermiyor.
**Cevap (ilk 400 char):** _## 2025 İnşaat Mühendisliği müfredatı — seçili dönem dersleri  ### 1. yıl Güz dönemi (1. dönem) — 7 ders - **CHEM 101** — Chemistry for Engineers     T: 2, L: 3, Kredi: 4, AKTS: 5 · Ön şart: yok - **COMP 103** — Art of Computing     T: 3, L: 2, Kredi: 4, AKTS: 5 · Ön şart: yok - **ENG 101** — English I     T: 4, L: 0, Kredi: 4, AKTS: 4 · Ön şart: yok - **GLB 101** — AGU Ways     T: 3, L: 0, Kredi:_

### `msne_005` (malzeme) — judge: **1/5**
**Soru:** MSNE 201 ön şartı?
**Kriter:** _Cevap MSNE 201 ön koşulunu belirtmeli._
**Hakem gerekçesi:** Cevap ön koşulu yok olarak belirtmiş ancak gerçek müfredatta bir ön koşul bulunabilir, bu yüzden yanlıştır.
**Cevap (ilk 400 char):** _**MSNE 201 – “Malzeme Bilimi ve Mühendisliği – I” dersinin ön şartı:** **Yoktur.**    *Kaynak: 2025 müfredatındaki “MSNE 201” satırı (Kaynak 1 ve Kaynak 2).*_

### `ort_005` (bilgisayar) — judge: **1/5**
**Soru:** Akademik takvim ne zaman güz dönemi başlar?
**Kriter:** _Cevap güz dönemi başlangıç tarihi hakkında bilgi vermeli._
**Hakem gerekçesi:** Cevap çok spesifik bir üniversiteye ve yıla odaklanmış, genel akademik takvim sorusunu yeterince karşılamıyor.
**Cevap (ilk 400 char):** _**Güz dönemi (Güz Yarıyılı) 2025‑2026 akademik takvime göre 29 Eylül 2025 Pazartesi tarihinde başlar.**    *Kaynak: “AGÜ 2025‑2026 Akademik Takvim — Güz Yarıyılı” (Kaynak 1).*_

### `comp_020` (bilgisayar) — judge: **2/5**
**Soru:** Seçmeli ders havuzunda kaç COMP dersi var?
**Kriter:** _Cevap seçmeli COMP dersi sayısı veya örnek dersler vermeli._
**Hakem gerekçesi:** Cevap örnek dersler vermiş ancak sayının doğruluğu ve kaynak doğruluğu teyit edilemedi.
**Cevap (ilk 400 char):** _Seçmeli ders havuzunda **8 adet COMP dersi** bulunmaktadır.  - COMP 413 Nesnelerin İnterneti   - COMP 411 Haberleşme Ağları   - COMP 405 Görüntü İşleme   - COMP 465 Yapay Zeka   - COMP 463 Hesaplamalı Genomik   - COMP 431 Bilgisayar Görü   - COMP 461 Derin Öğrenme   - COMP 462 Biyoenformatik    (“Bilgisayar Mühendisliği Teknik Seçmeli Havuzu” kaynakları 1‑8)_

### `ekon_005` (ekonomi) — judge: **2/5**
**Soru:** Ekonomi 1. yıl güz dersleri?
**Kriter:** _Cevap Ekonomi 2025 müfredatı 1. dönem derslerini en az 5 ders olarak listelemeli._
**Hakem gerekçesi:** Ekonomi dersleri eksik ve birçok alakasız ders listelenmiş, kriter tam karşılanmamış.
**Cevap (ilk 400 char):** _**Ekonomi Bölümü – 1. yıl Güz Dönemi (1. dönem) Ders Listesi**   *(2025 Ekonomi müfredatına göre – Kaynak 3, 1‑7)*    1. **MATH 121 – Introductory Mathematics I**      - Teorik: 4 saat, Lab: 0 saat      - Kredi: 4, AKTS: 6      - Ön şart: **yok**    2. **GLB 101 – AGU Ways**      - Teorik: 3 saat, Lab: 0 saat      - Kredi: 3, AKTS: 4      - Ön şart: **yok**    3. **COMP 101 – Art of Computing**   _

### `ba_001` (isletme) — judge: **2/5**
**Soru:** BA 499 staj dersi kaç AKTS?
**Kriter:** _Cevap BA 499'un AKTS değerini belirtmeli._
**Hakem gerekçesi:** Verilen 7 AKTS değeri muhtemelen hatalı; gerçek AKTS değeri farklıdır.
**Cevap (ilk 400 char):** _BA 499 Summer Internship dersi **7 AKTS**’dir. (Kaynak 5 – “AKTS (ECTS): 7”)_
