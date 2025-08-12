
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import json, unicodedata, subprocess, shutil

app = FastAPI(title="Ashtadhyayi Kosha Lookup", version="1.0.0")

DATA_DIR = Path("/app/data")
KOSHA_DIR = DATA_DIR / "kosha"
INDEX = {}

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
        return loaded
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".json", ".ndjson", ".tsv"}:
            continue
        src = p.parent.name
        loaded.setdefault(src, [])
        try:
            if p.suffix.lower() == ".json":
                loaded[src].extend(json.loads(p.read_text(encoding="utf-8")))
            elif p.suffix.lower() == ".ndjson":
                lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
                if lines:
                    loaded[src].extend(json.loads("[" + ",".join(lines) + "]"))
            else:
                for line in p.read_text(encoding="utf-8").splitlines():
                    if not line.strip() or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        loaded[src].append({"head": parts[0], "gloss": parts[1]})
        except:
            continue
    return loaded

def _refresh_data(clone: bool = False):
    global INDEX
    if clone or not DATA_DIR.exists():
        tmp = Path("/tmp/data")
        if tmp.exists():
            shutil.rmtree(tmp)
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ashtadhyayi-com/data", str(tmp)], check=True)
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
        shutil.move(str(tmp), str(DATA_DIR))
    INDEX = _load_data_from_dir(KOSHA_DIR)

@app.on_event("startup")
def _on_start():
    if not DATA_DIR.exists():
        _refresh_data(clone=True)
    else:
        _refresh_data(clone=False)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "sources": len(INDEX), "entries": sum(len(v) for v in INDEX.values())}

@app.get("/lookup")
def lookup(q: str = Query(...), sources: str | None = None, limit: int = 25):
    qn = _norm(q)
    if not qn:
        return JSONResponse([], status_code=200)
    chosen = [s for s in (sources.split(",") if sources else INDEX.keys()) if s in INDEX]
    out = []
    for src in chosen:
        for rec in INDEX.get(src, []):
            head = _norm(rec.get("head") or rec.get("key") or "")
            if head and (head == qn or qn in head):
                out.append({
                    "source": src,
                    "head": head,
                    "gloss": rec.get("gloss") or rec.get("meaning") or rec.get("value") or "",
                    "meta": {k: v for k, v in rec.items() if k not in {"head", "gloss"}}
                })
            if len(out) >= limit:
                break
    return JSONResponse(out, status_code=200)

@app.post("/refresh")
def refresh():
    try:
        _refresh_data(clone=True)
        return {"status": "ok", "sources": len(INDEX), "entries": sum(len(v) for v in INDEX.values())}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
