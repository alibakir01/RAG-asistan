# AGÜ RAG Asistanı

Abdullah Gül Üniversitesi öğrencileri için Türkçe RAG asistanı.
Müfredat, ders içerikleri, seçmeli ders havuzları, staj yönergeleri, akademik takvim,
Erasmus ve yatay geçiş sorularını cevaplar.

## Desteklenen Bölümler
**Mühendislik & Mimarlık**
- Bilgisayar Mühendisliği
- Makine Mühendisliği
- Endüstri Mühendisliği
- Elektrik-Elektronik Mühendisliği
- İnşaat Mühendisliği
- Malzeme Bilimi ve Nanoteknoloji Mühendisliği (MSNE)
- Biyomühendislik (BENG)
- Mimarlık

**Yaşam & Doğa Bilimleri**
- Biyomühendislik
- Moleküler Biyoloji ve Genetik (MBG)

**İktisadi & İdari / Sosyal Bilimler**
- İşletme
- Ekonomi
- Siyaset Bilimi ve Uluslararası İlişkiler
- Psikoloji

**Ortak kaynaklar:** Akademik takvim, Erasmus el kitabı, yatay geçiş yönergesi (tüm bölümlerde paylaşılır).

## Pipeline
1. **Ingest** — `src/ingest_*.py` her bölüm/kaynak için ham dokümanları (docx, pdf, csv, xlsx, json) yapılandırılmış chunk'lara çevirir → `data/processed/*.jsonl`
2. **Embed** — `src/embed.py` tüm chunk'ları `intfloat/multilingual-e5-large` ile embed edip ChromaDB'ye yazar → `data/chroma/`
3. **Retrieval + LLM** — `src/rag.py` hibrit retrieval (vektör + BM25 + RRF füzyon) → cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) → Groq (Llama 4 Scout 17B, bedava) ile Türkçe cevap üretir
4. **UI** — `app.py` Streamlit arayüzü (bölüm seçimi, detay seviyesi, GNO hesaplama, otomatik bölüm tespiti)

> **LLM sağlayıcı:** Varsayılan Groq (`meta-llama/llama-4-scout-17b-16e-instruct`). `LLM_PROVIDER=openrouter` veya `LLM_PROVIDER=auto` ile OpenRouter'a (gpt-oss-120b) geçiş/fallback desteklenir.

## Kurulum
```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
```

## Ortam Değişkeni
API anahtarını buradan bedavaya al: https://console.groq.com/keys

```bash
cp .env.example .env
# .env dosyasını aç, GROQ_API_KEY=gsk_... yaz
# (opsiyonel) OpenRouter için: OPENROUTER_API_KEY=..., LLM_PROVIDER=auto
```

## Çalıştırma
```bash
# 1) Chunks üret (sadece ilgili verinin kaynağı değiştiğinde, o bölümün scripti)
python src/ingest.py                       # Bilgisayar
python src/ingest_me.py                     # Makine
python src/ingest_endustri.py               # Endüstri
python src/ingest_elektrik.py               # Elektrik
python src/ingest_insaat.py                 # İnşaat
python src/ingest_malzeme.py                # Malzeme/MSNE
python src/ingest_biyomuhendislik.py        # Biyomühendislik (+ _staj)
python src/ingest_mimarlik.py               # Mimarlık (+ _secmeli, _staj)
python src/ingest_isletme.py                # İşletme (+ _secmeli, _staj)
python src/ingest_ekonomi.py                # Ekonomi (+ _secmeli, _staj_ders)
python src/ingest_siyaset.py                # Siyaset
python src/ingest_psikoloji.py              # Psikoloji (+ _mufredat, _staj, _secmeli)
python src/ingest_mbg.py                    # Moleküler Biyoloji ve Genetik (+ _staj)
python src/ingest_glb.py                    # Ortak seçmeli
python src/ingest_takvim.py                 # Akademik takvim
python src/ingest_erasmus.py                # Erasmus
python src/ingest_yatay_gecis.py            # Yatay geçiş

# 2) Embed + index (chunks değiştiğinde — tüm data/processed/*.jsonl dosyasını indeksler)
python src/embed.py

# 3a) CLI sorgu
python src/rag.py "2023 girişliyim 3. dönem hangi dersler var"

# 3b) Web UI
streamlit run app.py
```

> **İpucu — artımlı güncelleme:** `embed.py` koleksiyonu sıfırdan kurar (~15 dk). Tek bir bölüme küçük ekleme yaptıysan, sadece o chunk'ları `collection.upsert(...)` ile gömmek saniyeler sürer.

## Chunk İstatistikleri
Bölüm bazlı (chunk metadata'sındaki `bolum` alanına göre):

| Bölüm | Chunk Sayısı |
|---|---|
| Bilgisayar | 357 |
| Endüstri | 315 |
| İnşaat | 282 |
| Ortak (takvim, Erasmus, yatay geçiş) | 240 |
| Elektrik | 229 |
| Siyaset | 218 |
| Mimarlık | 198 |
| Makine | 197 |
| Malzeme/MSNE | 184 |
| İşletme | 157 |
| Biyomühendislik | 154 |
| Ekonomi | 134 |
| Psikoloji | 122 |
| Moleküler Biyoloji ve Genetik (MBG) | 75 |
| **TOPLAM** | **2862** |

## Canlıya Alma (Streamlit Community Cloud — ücretsiz)
Ağır yerel sürüm (`app.py`, torch+chroma) ücretsiz host'lara sığmaz; canlıda **hafif bulut
sürümü** çalışır: `streamlit_app.py` → `src/rag_cloud.py` (Voyage + Pinecone + BM25, torch yok).

**Tek seferlik hazırlık:**
1. Pinecone'a veriyi yükle: `python veri_yukleyici.py` (2862 vektör, voyage-3.5, dim=1024).

**Deploy:**
1. Kodu GitHub'a push'la (gerekli dosyalar repoda: `streamlit_app.py`, `src/rag_cloud.py`,
   `requirements.txt` (hafif), `data/processed/*.jsonl` (BM25 için), `data/term_aliases.json`).
2. [share.streamlit.io](https://share.streamlit.io) → **New app** → repoyu seç →
   **Main file path:** `streamlit_app.py`.
3. **Advanced settings → Secrets:** `.streamlit/secrets.toml.example` içeriğini gerçek
   anahtarlarla yapıştır (`VOYAGE_AI_KEY`, `PINECONE_API_KEY`, `GROQ_API_KEY`, `LLM_PROVIDER`).
4. Deploy. (Anahtarlar `.gitignore` ile repodan korunur; sadece Secrets paneline girilir.)

**Yerel test:** `streamlit run streamlit_app.py` (anahtarlar `.env`'den okunur).

### Bulut API (opsiyonel)
Ayrı bir frontend için: `uvicorn app_cloud:app --port 8000` → `POST /soru-sor {"soru": "..."}`.

## Yeni Bölüm Ekleme
Bir bölüm sisteme tam entegre olmak için şu yerlere dokunulur:
1. `src/ingest_<bolum>.py` — ham dokümandan chunk üretimi
2. `src/rag.py` — `BOLUM_KEYWORDS`, `detect_bolum` kod prefix'i, `BOLUM_ADI_MAP`, `BOLUM_LINKS`, `LATEST_MUFREDAT`, `parse_intent` müfredat-yıl eşlemesi, `SYSTEM_PROMPT` bölüm kuralı
3. `app.py` — bölüm seçim menüsü, `BOLUM_ID_MAP`, `BOLUM_SVG` ikonu, `SUGGESTIONS` örnek soruları
4. `python src/embed.py` (veya artımlı upsert) ile ChromaDB'ye gömme
