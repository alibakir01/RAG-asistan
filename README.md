# AGÜ Bilgisayar Mühendisliği RAG Asistanı

Abdullah Gül Üniversitesi Bilgisayar Mühendisliği öğrencileri için Türkçe RAG asistanı.
Müfredat, ders içerikleri, staj yönergesi ve internship handbook sorularını cevaplar.

## Pipeline
1. `src/ingest.py` — ham dokümanları (docx, pdf) yapılandırılmış chunk'lara çevirir → `data/processed/chunks.jsonl`
2. `src/embed.py` — chunk'ları `multilingual-e5-large` ile embed edip ChromaDB'ye yazar → `data/chroma/`
3. `src/rag.py` — retrieval + Groq (Llama 3.3 70B, bedava) ile cevap üretir
4. `app.py` — Streamlit UI

## Kurulum
```bash
pip install --user python-docx pdfplumber chromadb sentence-transformers groq streamlit
```

## Ortam Değişkeni
API anahtarını buradan bedavaya al: https://console.groq.com/keys
```bash
setx GROQ_API_KEY "gsk_..."   # Windows (yeni terminal aç)
export GROQ_API_KEY="gsk_..." # bash
```

## Çalıştırma
```bash
# 1) Chunks üret (sadece veri değiştiğinde)
python src/ingest.py

# 2) Embed + index (sadece chunks değiştiğinde)
python src/embed.py

# 3a) CLI sorgu
python src/rag.py "2023 girişliyim 3. dönem hangi dersler var"

# 3b) Web UI
streamlit run app.py
```

## Veri Kaynakları (`data/raw/`)
- CMP_Liste_2016/2021/2023/2025.docx — müfredat tabloları
- AGU_Bilgisayar_Staj_Yonergesi_2026.docx — staj yönergesi (MADDE 1-21)
- AGU-COMP-Internship-Handbook.docx — internship handbook (EN)
- DERS_KATALOG_COMP_v1.pdf — ders kataloğu (84 sayfa, 52 ders kaydı)

## Chunk İstatistikleri
- mufredat: 302
- ders_katalog: 52
- yonerge: 21
- handbook: 6
- **TOPLAM: 381**
