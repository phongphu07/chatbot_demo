import datetime
import math
import re
import random
from typing import Dict, Any, List
from app.embeddings import embedding_service
from app.database import vector_store

# Bộ lưu trữ phiếu hỗ trợ (In-Memory + có thể xem trên giao diện Admin)
SUPPORT_TICKETS: List[Dict[str, Any]] = []

def tra_cuu_tai_lieu(query: str, top_k: int = 3) -> str:
    """
    Tra cứu thông tin từ cơ sở dữ liệu tri thức / tài liệu nội bộ (RAG) qua pgvector.
    Sử dụng công cụ này khi người dùng hỏi các câu hỏi liên quan đến chính sách, tài liệu nội bộ, quy chế, sản phẩm, dữ liệu đã nạp.
    
    Args:
        query: Câu hỏi hoặc từ khóa ngữ nghĩa cần tìm kiếm trong tài liệu.
        top_k: Số lượng đoạn trích liên quan nhất cần lấy (mặc định 3).
    """
    try:
        # Lấy danh sách các tài liệu hiện có trong DB để AI biết ngữ cảnh
        existing_docs = [d["doc_name"] for d in vector_store.list_documents()]
        if not existing_docs:
            return "Cơ sở dữ liệu tài liệu hiện tại đang trống (chưa có tài liệu nào được nạp vào hệ thống). Hãy hướng dẫn người dùng nạp tài liệu vào kho tham khảo."

        query_vector = embedding_service.embed_query(query)
        chunks = vector_store.search_similar_chunks(query_vector, top_k=top_k, min_similarity=0.45)
        
        if not chunks:
            docs_str = ", ".join(f"'{d}'" for d in existing_docs)
            return (
                f"Không tìm thấy đoạn trích nào có độ tương đồng đủ cao với câu hỏi '{query}'.\n"
                f"Các tài liệu hiện có trong hệ thống bao gồm: {docs_str}.\n"
                f"Hãy thông báo rõ ràng cho người dùng biết câu hỏi này không có trong các tài liệu hiện có và hỏi họ có muốn bổ sung tài liệu liên quan không."
            )

        formatted_results = []
        for i, c in enumerate(chunks, 1):
            formatted_results.append(
                f"[Đoạn trích #{i} - Nguồn: '{c['doc_name']}', Đoạn {c['chunk_index']}, Độ tương đồng: {c['similarity'] * 100:.1f}%]:\n"
                f"{c['content']}"
            )
        return "\n\n---\n\n".join(formatted_results)
    except Exception as e:
        return f"Lỗi trong quá trình tra cứu tài liệu: {str(e)}"

def tra_cuu_thoi_gian() -> str:
    """
    Lấy ngày giờ hiện tại theo giờ Việt Nam (UTC+7).
    Sử dụng khi người dùng hỏi thời gian, ngày tháng hiện tại, hoặc các câu hỏi cần mốc thời gian thực.
    """
    now = datetime.datetime.now()
    days_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    weekday = days_vi[now.weekday()]
    return f"Hiện tại là {now.strftime('%H:%M:%S')}, {weekday}, ngày {now.strftime('%d/%m/%Y')} (Giờ Việt Nam UTC+7)."

def tao_phieu_ho_tro(tieu_de: str, noi_dung: str, muc_do: str = "Bình thường") -> str:
    """
    Tạo phiếu yêu cầu hỗ trợ (Support Ticket) hoặc nhiệm vụ mới trong hệ thống.
    Sử dụng khi người dùng yêu cầu gửi ticket, báo cáo sự cố, lỗi hệ thống hoặc tạo yêu cầu công việc.
    
    Args:
        tieu_de: Tóm tắt ngắn gọn yêu cầu hoặc sự cố.
        noi_dung: Chi tiết nội dung cần hỗ trợ.
        muc_do: Mức độ ưu tiên ('Thấp', 'Bình thường', 'Khẩn cấp').
    """
    ticket_id = f"TK-{random.randint(10000, 99999)}"
    created_at = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    
    ticket = {
        "id": ticket_id,
        "title": tieu_de,
        "description": noi_dung,
        "priority": muc_do,
        "status": "Đang tiếp nhận",
        "created_at": created_at
    }
    SUPPORT_TICKETS.insert(0, ticket)
    
    return (
        f"✅ Đã tạo thành công Phiếu hỗ trợ #{ticket_id}!\n"
        f"- Tiêu đề: {tieu_de}\n"
        f"- Chi tiết: {noi_dung}\n"
        f"- Mức độ ưu tiên: {muc_do}\n"
        f"- Trạng thái: Đang tiếp nhận xử lý\n"
        f"- Thời gian tạo: {created_at}\n"
        f"Phiếu đã được lưu trữ và chuyển đến bộ phận chuyên trách. Bạn có thể tra cứu tình trạng bằng mã '{ticket_id}' bất kỳ lúc nào."
    )

def tra_cuu_phieu_ho_tro(ma_ticket: str) -> str:
    """
    Tra cứu tiến độ và thông tin của một Phiếu hỗ trợ (Support Ticket) đã tạo theo mã ID.
    Sử dụng khi người dùng hỏi về tình trạng một phiếu ticket (ví dụ: 'Kiểm tra phiếu TK-12345').
    
    Args:
        ma_ticket: Mã định danh của phiếu hỗ trợ (ví dụ: 'TK-12345').
    """
    clean_id = ma_ticket.strip().upper()
    found = next((t for t in SUPPORT_TICKETS if t["id"] == clean_id), None)
    if not found:
        return f"Không tìm thấy phiếu hỗ trợ nào có mã '{ma_ticket}'. Vui lòng kiểm tra lại mã phiếu."
    
    return (
        f"📄 Thông tin Phiếu hỗ trợ #{found['id']}:\n"
        f"- Tiêu đề: {found['title']}\n"
        f"- Nội dung: {found['description']}\n"
        f"- Mức độ ưu tiên: {found['priority']}\n"
        f"- Trạng thái hiện tại: {found['status']}\n"
        f"- Thời gian tạo: {found['created_at']}"
    )

def may_tinh(bieu_thuc: str) -> str:
    """
    Thực hiện tính toán biểu thức số học chính xác.
    Sử dụng khi cần tính toán con số, công thức, phần trăm, tài chính.
    
    Args:
        bieu_thuc: Biểu thức toán học dạng chuỗi, ví dụ: '(15000000 * 0.12) / 12'
    """
    try:
        # Chỉ cho phép ký tự an toàn
        cleaned = re.sub(r"[^0-9\+\-\*\/\(\)\.\,\s\%]", "", bieu_thuc).replace(",", ".").replace("%", "*0.01")
        result = eval(cleaned, {"__builtins__": None, "math": math})
        # Định dạng số đẹp
        if isinstance(result, float) and result.is_integer():
            formatted = f"{int(result):,}".replace(",", ".")
        elif isinstance(result, (int, float)):
            formatted = f"{result:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            formatted = str(result)
        return f"Kết quả phép tính '{bieu_thuc}' là: {formatted}"
    except Exception as e:
        return f"Không thể tính toán biểu thức '{bieu_thuc}': {str(e)}"

# Danh sách tool schemas và functions mapping
AVAILABLE_TOOLS = {
    "tra_cuu_tai_lieu": tra_cuu_tai_lieu,
    "tra_cuu_thoi_gian": tra_cuu_thoi_gian,
    "tao_phieu_ho_tro": tao_phieu_ho_tro,
    "tra_cuu_phieu_ho_tro": tra_cuu_phieu_ho_tro,
    "may_tinh": may_tinh
}
