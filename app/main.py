import os
import shutil
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from dotenv import set_key

logger = logging.getLogger(__name__)

from app.config import settings, BASE_DIR
from app.chunker import TextChunker
from app.embeddings import embedding_service
from app.database import vector_store
from app.agent import ai_agent
from app.tools import AVAILABLE_TOOLS, SUPPORT_TICKETS
from app.presence import presence_manager
from app.cache import rag_cache

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API cho AI Chatbot 3-trong-1: Chitchat + RAG pgvector + Tools Execution"
)

# Thư mục tĩnh chứa UI
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ----------------- PYDANTIC SCHEMAS -----------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    system_prompt: Optional[str] = None

class ChunkPreviewRequest(BaseModel):
    text: str
    doc_name: str
    chunk_size: Optional[int] = 600
    chunk_overlap: Optional[int] = 120
    add_contextual_header: Optional[bool] = True

class SaveRawTextRequest(BaseModel):
    text: str
    doc_name: str
    chunk_size: Optional[int] = 600
    chunk_overlap: Optional[int] = 120
    add_contextual_header: Optional[bool] = True

class ConfigUpdateRequest(BaseModel):
    llm_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    embedding_provider: Optional[str] = None

class PresencePingRequest(BaseModel):
    client_id: Optional[str] = "anon_client"
    is_active: Optional[bool] = False

# ----------------- API ENDPOINTS -----------------

@app.websocket("/ws/presence")
async def websocket_presence(websocket: WebSocket, client_id: str = "anon"):
    """
    True Real-Time WebSocket Channel:
    - Bắt sự kiện kết nối mới trong < 10ms
    - Bắt sự kiện đóng tab (disconnect) trong < 10ms
    - Tự động broadcast số người dùng tức thì tới toàn bộ trình duyệt
    """
    await websocket.accept()
    await presence_manager.connect_ws(client_id, websocket)
    try:
        while True:
            # Lắng nghe ping từ client để giữ kết nối sống
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "active_users": presence_manager.online_count}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await presence_manager.disconnect_ws(client_id, websocket)

@app.get("/api/presence/stream")
async def presence_stream(client_id: str = "anon_client"):
    """
    True Real-Time SSE Stream: Cập nhật biến động số người dùng (0ms delay)
    tới toàn bộ trình duyệt đang kết nối.
    """
    queue = await presence_manager.register(client_id)

    async def event_generator():
        try:
            # Gửi số lượng hiện tại ngay lập tức khi vừa kết nối
            initial_msg = json.dumps({"active_users": presence_manager.online_count})
            yield f"data: {initial_msg}\n\n"
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await presence_manager.unregister(client_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/presence/leave")
async def presence_leave(payload: Optional[PresencePingRequest] = None):
    """Xử lý sự kiện đóng tab trình duyệt ngay tức thì qua beacon"""
    client_id = payload.client_id if payload else "anon_client"
    await presence_manager.leave(client_id)
    return {"status": "left"}

@app.post("/api/presence/ping")
async def presence_ping(payload: Optional[PresencePingRequest] = None):
    """Client heartbeat ping theo dõi số nhân viên đang trực tuyến theo thời gian thực"""
    client_id = payload.client_id if payload else "anon_client"
    is_active = payload.is_active if payload else False
    active_count = presence_manager.ping(client_id, is_active)
    return {
        "status": "online",
        "active_users": active_count,
        "concurrency_mode": "high_availability"
    }

@app.get("/api/presence/stats")
async def presence_stats():
    """Xem số liệu hiệu năng chịu tải, cache ratio và active users"""
    return {
        "active_users": presence_manager.get_online_count(),
        "cache_stats": rag_cache.get_stats(),
        "database": vector_store.get_status()
    }

@app.post("/api/benchmark/run")
async def run_benchmark_endpoint():
    """Chạy toàn bộ bài test kiểm thử độ chính xác (Benchmark) và trả về báo cáo kết quả"""
    from app.benchmark import run_benchmark_suite
    result = await run_benchmark_suite()
    return result

@app.get("/api/benchmark/latest")
async def get_latest_benchmark_endpoint():
    """Lấy kết quả benchmark gần nhất"""
    from app.benchmark import get_latest_benchmark
    return get_latest_benchmark()

@app.get("/api/status")
async def get_system_status():
    """Kiểm tra trạng thái hệ thống: LLM, Embedding, pgvector"""
    db_status = vector_store.get_status()
    has_gemini = bool(settings.GEMINI_API_KEY)
    has_openai = bool(settings.OPENAI_API_KEY)
    
    current_key_set = False
    if settings.LLM_PROVIDER == "gemini":
        current_key_set = has_gemini
    elif settings.LLM_PROVIDER == "openai":
        current_key_set = has_openai

    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.GEMINI_MODEL if settings.LLM_PROVIDER == "gemini" else settings.OPENAI_MODEL,
        "has_api_key": current_key_set,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_dim": settings.embedding_dim,
        "database": db_status
    }

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Streaming endpoint tương tác hội thoại + gọi Tools theo SSE (Server-Sent Events)"""
    messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]

    async def event_generator():
        async for chunk in ai_agent.stream_chat(messages_payload, request.system_prompt or ""):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/documents/preview")
async def preview_chunking(request: ChunkPreviewRequest):
    """Băm thử chunk để người dùng xem trước và tinh chỉnh thông số (Size, Overlap)"""
    chunker = TextChunker(
        chunk_size=request.chunk_size or settings.DEFAULT_CHUNK_SIZE,
        chunk_overlap=request.chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP,
        add_contextual_header=request.add_contextual_header
    )
    chunks = chunker.chunk_document(request.text, request.doc_name)
    return {
        "doc_name": request.doc_name,
        "total_chunks": len(chunks),
        "chunk_size": chunker.chunk_size,
        "chunk_overlap": chunker.chunk_overlap,
        "chunks": chunks
    }

@app.post("/api/documents/preview-file")
async def preview_file_chunking(
    file: UploadFile = File(...),
    chunk_size: int = Form(600),
    chunk_overlap: int = Form(120),
    add_contextual_header: bool = Form(True)
):
    """Trích xuất text thực tế từ file (kể cả PDF) và băm thử chunk để xem trước"""
    temp_file = UPLOADS_DIR / f"preview_{file.filename}"
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        raw_text = TextChunker.extract_text_from_file(temp_file)
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Không thể trích xuất văn bản từ file này.")

        chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_contextual_header=add_contextual_header
        )
        chunks = chunker.chunk_document(raw_text, file.filename)
        return {
            "doc_name": file.filename,
            "total_chunks": len(chunks),
            "chunk_size": chunker.chunk_size,
            "chunk_overlap": chunker.chunk_overlap,
            "chunks": chunks
        }
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass

@app.post("/api/documents/ingest-text")
async def ingest_raw_text(request: SaveRawTextRequest):
    """Băm chunk và nhúng vector vào Database từ văn bản thô"""
    chunker = TextChunker(
        chunk_size=request.chunk_size or settings.DEFAULT_CHUNK_SIZE,
        chunk_overlap=request.chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP,
        add_contextual_header=request.add_contextual_header
    )
    chunks = chunker.chunk_document(request.text, request.doc_name)
    if not chunks:
        raise HTTPException(status_code=400, detail="Văn bản không có nội dung hợp lệ.")

    # Tạo vector nhúng cho từng chunk (sử dụng contextual_content để tăng độ nhạy ngữ nghĩa)
    texts_to_embed = [c["contextual_content"] for c in chunks]
    try:
        embeddings = embedding_service.embed_texts(texts_to_embed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi sinh vector embedding: {str(e)}")

    # Lưu vào PostgreSQL + pgvector (hoặc memory fallback)
    saved_count = vector_store.save_chunks(chunks, embeddings)

    return {
        "status": "success",
        "message": f"Đã băm và lưu thành công {saved_count} chunks vào {vector_store.get_status()['mode']}.",
        "doc_name": request.doc_name,
        "chunks_indexed": saved_count
    }

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    chunk_size: int = Form(600),
    chunk_overlap: int = Form(120),
    add_contextual_header: bool = Form(True)
):
    """Tải lên file (PDF, TXT, MD), băm chunk và lưu vector vào pgvector"""
    temp_file = UPLOADS_DIR / file.filename
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 1. Trích xuất text từ file
        raw_text = TextChunker.extract_text_from_file(temp_file)
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="Không thể trích xuất văn bản từ file này.")

        # 2. Băm chunk với overlap và contextual prefix
        chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_contextual_header=add_contextual_header
        )
        chunks = chunker.chunk_document(raw_text, file.filename)
        if not chunks:
            raise HTTPException(status_code=400, detail="Không tạo được chunk nào từ tài liệu.")

        # 3. Tạo vector embeddings
        texts_to_embed = [c["contextual_content"] for c in chunks]
        embeddings = embedding_service.embed_texts(texts_to_embed)

        # 4. Xóa các chunk cũ của tài liệu này nếu đã từng nạp để tránh trùng lặp dữ liệu
        vector_store.delete_document(file.filename)
        saved_count = vector_store.save_chunks(chunks, embeddings)

        return {
            "status": "success",
            "file_name": file.filename,
            "chunks_count": saved_count,
            "message": f"Đã nạp file '{file.filename}' thành công ({saved_count} chunks) vào {vector_store.get_status()['mode']}."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý file: {str(e)}")
    finally:
        if temp_file.exists():
            temp_file.unlink()

@app.get("/api/documents")
async def list_documents():
    """Lấy danh sách các tài liệu đã nạp trong hệ thống"""
    return {"documents": vector_store.list_documents()}

@app.delete("/api/documents/{doc_name}")
async def delete_document(doc_name: str):
    """Xóa tài liệu và các chunk của nó khỏi vector store"""
    deleted = vector_store.delete_document(doc_name)
    return {"status": "success", "deleted_chunks": deleted}

@app.post("/api/documents/ingest-sample")
async def ingest_sample_document():
    """Nạp nhanh bộ tài liệu mẫu (Quy chế công ty) để kiểm thử RAG tức thì"""
    sample_file = BASE_DIR / "sample_data" / "quy_che_cong_ty.txt"
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file tài liệu mẫu.")
    
    with open(sample_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    doc_name = "Quy che hoat dong cong ty 2024.txt"
    chunker = TextChunker(chunk_size=500, chunk_overlap=100, add_contextual_header=True)
    chunks = chunker.chunk_document(raw_text, doc_name)
    
    texts_to_embed = [c["contextual_content"] for c in chunks]
    embeddings = embedding_service.embed_texts(texts_to_embed)
    saved_count = vector_store.save_chunks(chunks, embeddings)
    
    return {
        "status": "success",
        "doc_name": doc_name,
        "chunks_count": saved_count,
        "message": f"Đã nạp thành công tài liệu mẫu '{doc_name}' ({saved_count} chunks) vào cơ sở dữ liệu."
    }

@app.get("/api/tickets")
async def list_tickets():
    """Lấy danh sách các phiếu hỗ trợ (Support Tickets) đã tạo"""
    return {"tickets": SUPPORT_TICKETS}

@app.get("/api/tools")
async def list_tools():
    """Danh sách các Tools đang sẵn sàng phục vụ AI Agent"""
    tools_info = []
    for name, func in AVAILABLE_TOOLS.items():
        tools_info.append({
            "name": name,
            "description": func.__doc__.strip().split("\n")[0] if func.__doc__ else "Công cụ hỗ trợ"
        })
    return {"tools": tools_info}

@app.get("/api/settings/status")
async def get_settings_status():
    """Kiểm tra trạng thái cấu hình hệ thống mà không làm lộ API Key"""
    return {
        "llm_provider": settings.LLM_PROVIDER,
        "has_gemini_key": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip()),
        "has_openai_key": bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip()),
        "embedding_provider": settings.EMBEDDING_PROVIDER
    }

@app.post("/api/settings")
async def update_settings(req: ConfigUpdateRequest):
    """Cập nhật nhanh API Key hoặc Provider vào file .env và nạp nóng trực tiếp vào RAM"""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        try:
            env_file.touch()
        except Exception:
            pass

    if req.llm_provider:
        try:
            set_key(str(env_file), "LLM_PROVIDER", req.llm_provider)
        except Exception:
            pass
        settings.LLM_PROVIDER = req.llm_provider

    if req.gemini_api_key is not None and req.gemini_api_key.strip():
        val = req.gemini_api_key.strip()
        try:
            set_key(str(env_file), "GEMINI_API_KEY", val)
        except Exception:
            pass
        settings.GEMINI_API_KEY = val
        os.environ["GEMINI_API_KEY"] = val

    if req.openai_api_key is not None and req.openai_api_key.strip():
        val = req.openai_api_key.strip()
        try:
            set_key(str(env_file), "OPENAI_API_KEY", val)
        except Exception:
            pass
        settings.OPENAI_API_KEY = val
        os.environ["OPENAI_API_KEY"] = val

    if req.embedding_provider:
        try:
            set_key(str(env_file), "EMBEDDING_PROVIDER", req.embedding_provider)
        except Exception:
            pass
        settings.EMBEDDING_PROVIDER = req.embedding_provider

    # Nạp nóng lại AI Agent để client nhận API Key mới ngay tức khắc mà không cần khởi động lại
    try:
        from app.agent import ai_agent
        ai_agent._init_client()
    except Exception as e:
        logger.error(f"Lỗi khi re-init AI Agent: {e}")

    return {"status": "success", "message": "Đã lưu cài đặt và kích hoạt API Key thành công!"}

# Phục vụ thư mục static
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")
