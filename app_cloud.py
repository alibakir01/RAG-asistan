"""
Bulut RAG backend (FastAPI) — ince sarmalayıcı; tüm mantık src/rag_cloud.py'de.

Çalıştır:  uvicorn app_cloud:app --host 0.0.0.0 --port 8000
Gerekli .env:  VOYAGE_AI_KEY, PINECONE_API_KEY, GROQ_API_KEY (ve/veya OPENROUTER_API_KEY)
"""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src import rag_cloud

app = FastAPI(title="RAG Asistan Bulut API")


class SoruIstegi(BaseModel):
    soru: str
    bolum: str | None = None  # verilmezse soruya göre otomatik tespit


@app.get("/saglik")
async def saglik():
    return {
        "durum": "ok",
        "provider": rag_cloud.LLM_PROVIDER,
        "embed": rag_cloud.EMBED_MODEL,
        "rerank": rag_cloud.RERANK_MODEL,
        "retrieval": "hybrid (dense + BM25 + RRF)",
    }


@app.post("/soru-sor")
async def soru_sor(istek: SoruIstegi):
    soru = (istek.soru or "").strip()
    if not soru:
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")
    try:
        return rag_cloud.answer(soru, bolum=istek.bolum) if istek.bolum else rag_cloud.answer(soru)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
