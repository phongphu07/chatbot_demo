import sys
import uvicorn
import webbrowser
import threading
import time

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.config import settings

def open_browser():
    time.sleep(1.5)
    url = f"http://localhost:{settings.PORT}"
    print(f"\n[Browser] Dang mo trinh duyet tai: {url}\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    print("=" * 65)
    print("AI ASSISTANT 3-TRONG-1 (CHITCHAT + RAG PGVECTOR + TOOLS)")
    print(f"May chu dang khoi dong tai: http://localhost:{settings.PORT}")
    print(f"LLM Provider: {settings.LLM_PROVIDER.upper()}")
    print(f"Vector Store: PostgreSQL + pgvector (hoac In-Memory fallback)")
    print("=" * 65)

    # Mo trinh duyet tu dong
    threading.Thread(target=open_browser, daemon=True).start()

    # Chay uvicorn server
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)

