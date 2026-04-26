# AGÜ Mühendislik RAG Asistanı

Abdullah Gül Üniversitesi mühendislik öğrencileri için Türkçe RAG asistanı.
Müfredat, ders içerikleri, staj yönergesi ve internship handbook sorularını cevaplar.

## Desteklenen Bölümler
- Bilgisayar Mühendisliği
- Makine Mühendisliği
- Endüstri Mühendisliği
- Elektrik-Elektronik Mühendisliği
- İnşaat Mühendisliği

## Pipeline
1. `src/ingest.py` (+ `ingest_me.py`, `ingest_elektrik.py`, `ingest_endustri.py`, `ingest_insaat.py`, `ingest_glb.py`) — ham dokümanları (docx, pdf, csv, xlsx) yapılandırılmış chunk'lara çevirir → `data/processed/*.jsonl`
2. `src/embed.py` — tüm chunk'ları `multilingual-e5-large` ile embed edip ChromaDB'ye yazar → `data/chroma/`
3. `src/rag.py` — retrieval + Groq (Llama 3.3 70B, bedava) ile cevap üretir
4. `app.py` — Streamlit UI (bölüm seçimi + detay seviyesi)

## Kurulum
```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

pip install python-docx pdfplumber chromadb sentence-transformers groq streamlit python-dotenv pandas openpyxl
```

## Ortam Değişkeni
API anahtarını buradan bedavaya al: https://console.groq.com/keys

```bash
cp .env.example .env
# .env dosyasını aç, GROQ_API_KEY=gsk_... yaz
```

## Çalıştırma
```bash
# 1) Chunks üret (sadece veri değiştiğinde — her bölüm için ayrı script)
python src/ingest.py
python src/ingest_me.py
python src/ingest_elektrik.py
python src/ingest_endustri.py
python src/ingest_insaat.py
python src/ingest_glb.py

# 2) Embed + index (chunks değiştiğinde — tüm jsonl dosyalarını birden indeksler)
python src/embed.py

# 3a) CLI sorgu
python src/rag.py "2023 girişliyim 3. dönem hangi dersler var"

# 3b) Web UI
streamlit run app.py
```

## Veri Kaynakları (`data/raw/`)
- **Bilgisayar:** CMP_Liste_2016/2021/2023/2025.docx, AGU_Bilgisayar_Staj_Yonergesi_2026.docx, AGU-COMP-Internship-Handbook.docx, DERS_KATALOG_COMP_v1.pdf
- **Makine:** Makine Mühendisliği/ klasörü (mufredat xlsx, kataloglar, staj akışı)
- **Endüstri:** IE*_Syllabus.docx, IE_STAJ_PROGRAMI_KILAVUZU, ie_*_temiz.csv
- **Elektrik:** AGU-EE-Curriculum-2019/2021.pdf, EE_staj_yonergesi_2019.pdf, EE_Capsule_Rules_TR.pdf, ee_*_temiz.csv
- **İnşaat:** CE_Curriculum_2016/2021/2025.pdf, CE_Course_Catalogue.pdf, CE_Staj_Uygulamali_Egitim_Yonergesi.pdf, ce_*_temiz.csv

## Chunk İstatistikleri
| Bölüm | Chunk Sayısı |
|---|---|
| Bilgisayar (`chunks.jsonl`) | 352 |
| Makine (`me_chunks.jsonl`) | 192 |
| Endüstri (`chunks_endustri.jsonl`) | 310 |
| Elektrik (`chunks_elektrik.jsonl`) | 224 |
| İnşaat (`chunks_insaat.jsonl`) | 277 |
| Genel/Ortak Seçmeli (`chunks_glb.jsonl`) | 25 |
| **TOPLAM** | **1380** |
