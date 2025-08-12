
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path
import json, unicodedata, logging

app = FastAPI(title="Ashtadhyayi Kosha Lookup", version="1.0.3")

DATA_DIR = Path("/app/data")
KOSHA_DIR = DATA_DIR / "kosha"
INDEX = {}

# Logger
logger = logging.getLogger("kosha")
logging.basicConfig(level=logging.INFO)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", (s or "").strip())

def _load_data_from_dir(base: Path):
    loaded = {}
    if not base.exists():
        logger.warning("KOSHA_DIR not found: %s", base)
        return loaded
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".json", ".ndjson", ".tsv"}:
            continue
        src = p.parent.name
        loaded.setdefault(src, [])
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            if p.suffix.lower() == ".json":
                loaded[src].extend(json.loads(text))
            elif p.suffix.lower() == ".ndjson":
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                if lines:
                    loaded[src].extend(json.loads("[" + ",".join(lines) + "]"))
            else:
                for line in text.splitlines():
                    if not line.strip() or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        loaded[src].append({"head": parts[0], "gloss": parts[1]})
        except Exception as e:
            logger.exception("Failed parsing %s: %s", p, e)
            continue
    return loaded

@app.on_event("startup")
def _on_start():
    global INDEX
    INDEX = _load_data_from_dir(KOSHA_DIR)
    logger.info("Loaded sources: %s (total entries=%d)", list(INDEX.keys()), sum(len(v) for v in INDEX.values()))

@app.get("/", response_class=HTMLResponse)
def root():
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Kosha Lookup API</title>
  <style>
    body{font-family:sans-serif;max-width:780px;margin:40px auto;padding:0 20px;line-height:1.6}
    code{background:#f4f4f4;padding:2px 6px;border-radius:4px}
    .card{border:1px solid #eee;border-radius:10px;padding:16px;margin:14px 0;background:#fff}
    a{color:#0366d6;text-decoration:none}
  </style>
</head>
<body>
  <h1>Ashtadhyayi Kosha Lookup API</h1>
  <div class="card">
    <p>Endpoints:</p>
    <ul>
      <li><a href="./healthz"><code>/healthz</code></a></li>
      <li><a href="./sources"><code>/sources</code></a></li>
      <li><a href="./lookup?q=varaha&limit=5"><code>/lookup?q=varaha&limit=5</code></a> (example)</li>
      <li><a href="./lookup?q=%E0%A4%AF%E0%A4%9C%E0%A5%8D%E0%A4%9E&limit=5"><code>/lookup?q=यज्ञ&limit=5</code></a> (Devanāgarī example)</li>
    </ul>
    <p>Use these endpoints from your Custom GPT Action. If nothing is found, your GPT should then browse the web.</p>
  </div>
</body>
</html>"""

@app.get("/healthz")
def healthz():
    return {"status": "ok", "sources": len(INDEX), "entries": sum(len(v) for v in INDEX.values())}

@app.get("/sources")
def sources():
    return {"sources": sorted(list(INDEX.keys()))}

@app.get("/lookup")
def lookup(q: str = Query(...), sources: str | None = None, limit: int = 25):
    try:
        qn = _norm(q)
        if not qn:
            return JSONResponse([], status_code=200)
        chosen = [s for s in (sources.split(",") if sources else INDEX.keys()) if s in INDEX]
        out = []
        for src in chosen:
            for rec in INDEX.get(src, []):
                head = _norm((rec.get("head") or rec.get("key") or "")) if isinstance(rec, dict) else ""
                gloss = ""
                if isinstance(rec, dict):
                    gloss = rec.get("gloss") or rec.get("meaning") or rec.get("value") or ""
                if head and (head == qn or qn in head):
                    meta = {}
                    if isinstance(rec, dict):
                        for k, v in rec.items():
                            if k not in {"head", "gloss"}:
                                meta[k] = v
                    out.append({"source": src, "head": head, "gloss": gloss, "meta": meta})
                if len(out) >= limit:
                    break
        return JSONResponse(out, status_code=200)
    except Exception as e:
        logger.exception("Lookup error for q=%r sources=%r", q, sources)
        return JSONResponse([], status_code=200)
