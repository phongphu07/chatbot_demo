import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI
from app.config import settings
from app.tools import AVAILABLE_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là Trợ lý AI Thông minh Đa Năng (3-trong-1) có khả năng:
1. Trò chuyện tự nhiên, thân thiện, giải đáp kiến thức tổng quát (Chitchat).
2. Tra cứu cơ sở dữ liệu tài liệu nội bộ qua pgvector (RAG) khi được hỏi về chính sách, tài liệu, quy chế, hoặc kiến thức riêng đã nạp.
3. Thực thi tác vụ tự động bằng cách gọi các công cụ (Tools) phù hợp: tra cứu tài liệu, tra cứu thời gian thực, tạo phiếu hỗ trợ, tính toán số học.

NGUYÊN TẮC QUAN TRỌNG:
- Nếu người dùng chào hỏi, hỏi thăm, trò chuyện thông thường: Trả lời trực tiếp, thân thiện, không cần gọi tool.
- Nếu người dùng hỏi câu hỏi cần dữ liệu, chính sách, tài liệu nội bộ: BẮT BUỘC gọi tool `tra_cuu_tai_lieu`. Sau khi có kết quả, tổng hợp lại câu trả lời và trích dẫn rõ nguồn gốc (tên file, đoạn trích, độ tương đồng).
- Khi tổng hợp câu trả lời từ tài liệu: Hãy đọc kỹ toàn bộ chi tiết (tên, chức danh, email, số điện thoại, học vấn, dự án, kỹ năng). Với những thông tin gián tiếp (ví dụ: người dùng hỏi năm sinh/tuổi nhưng trong CV chỉ có email 'phongphu.07072001@gmail.com' hoặc niên khóa đại học), hãy suy luận thông minh và chỉ ra dấu hiệu đó (ví dụ: 'Theo email phongphu.07072001@gmail.com trong CV, có thể thấy Phú sinh ngày 07/07/2001...') thay vì vội vã kết luận là không có.
- Nếu người dùng yêu cầu hành động (tạo phiếu hỗ trợ, tra cứu ngày giờ hiện tại, tính toán số học phức tạp): Gọi tool tương ứng để thực thi chính xác.
- Luôn trả lời bằng tiếng Việt lịch thiệp, định dạng Markdown rõ ràng, chuyên nghiệp.
"""

# Định nghĩa Tool Schema chuẩn OpenAI Function Calling
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "tra_cuu_tai_lieu",
            "description": "Tra cứu thông tin từ cơ sở dữ liệu tài liệu nội bộ (RAG qua pgvector). BẮT BUỘC sử dụng khi người dùng hỏi về bất kỳ ai, thông tin cá nhân/hồ sơ CV (ví dụ: Phú, Trần Phong Phú), dự án, kinh nghiệm, năm sinh, quy chế, chính sách, hoặc bất kỳ dữ liệu nào đã nạp vào hệ thống.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu hỏi hoặc từ khóa ngữ nghĩa cần tìm trong tài liệu"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Số đoạn trích liên quan nhất cần lấy (1-5)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tra_cuu_thoi_gian",
            "description": "Lấy ngày giờ hiện tại theo giờ Việt Nam (UTC+7). Dùng khi người dùng hỏi giờ, ngày tháng hôm nay, hoặc cần mốc thời gian thực.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tao_phieu_ho_tro",
            "description": "Tạo phiếu yêu cầu hỗ trợ (Support Ticket) hoặc nhiệm vụ mới trong hệ thống.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tieu_de": {
                        "type": "string",
                        "description": "Tóm tắt ngắn gọn yêu cầu hoặc sự cố"
                    },
                    "noi_dung": {
                        "type": "string",
                        "description": "Chi tiết yêu cầu hỗ trợ"
                    },
                    "muc_do": {
                        "type": "string",
                        "enum": ["Thấp", "Bình thường", "Khẩn cấp"],
                        "description": "Mức độ ưu tiên"
                    }
                },
                "required": ["tieu_de", "noi_dung"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tra_cuu_phieu_ho_tro",
            "description": "Tra cứu thông tin và tiến độ của một Phiếu hỗ trợ (Support Ticket) đã tạo theo mã phiếu (ví dụ: 'TK-12345').",
            "parameters": {
                "type": "object",
                "properties": {
                    "ma_ticket": {
                        "type": "string",
                        "description": "Mã định danh phiếu hỗ trợ (ví dụ: 'TK-12345')"
                    }
                },
                "required": ["ma_ticket"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "may_tinh",
            "description": "Thực hiện phép tính số học, phần trăm, công thức tài chính chính xác.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bieu_thuc": {
                        "type": "string",
                        "description": "Biểu thức toán học (ví dụ: '(12000000 * 0.15) / 12')"
                    }
                },
                "required": ["bieu_thuc"]
            }
        }
    }
]

class AIAgent:
    def __init__(self):
        self._init_client()

    def _init_client(self):
        """Khởi tạo Client LLM tùy theo cấu hình provider (Gemini hoặc OpenAI)"""
        if settings.LLM_PROVIDER == "gemini":
            if not settings.GEMINI_API_KEY:
                self.client = None
                return
            # Kết nối tới Google Gemini thông qua OpenAI-compatible endpoint chính thức của Google
            self.client = AsyncOpenAI(
                api_key=settings.GEMINI_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            self.model = settings.GEMINI_MODEL
        else:
            if not settings.OPENAI_API_KEY:
                self.client = None
                return
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        custom_system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        """
        Xử lý hội thoại đa vòng (multi-turn) với cơ chế Streaming + Function Calling.
        Yield ra các event dạng JSON String (SSE).
        """
        self._init_client()
        if not self.client:
            yield json.dumps({
                "type": "error",
                "content": f"Chưa cấu hình API Key cho provider '{settings.LLM_PROVIDER}'. Vui lòng thêm key vào file .env!"
            })
            return

        # Lấy danh sách các tài liệu hiện có trong vector store để cung cấp ngữ cảnh cho AI
        try:
            from app.database import vector_store
            existing_docs = [d["doc_name"] for d in vector_store.list_documents()]
        except Exception:
            existing_docs = []

        if existing_docs:
            docs_list_text = "\n".join([f"- {name}" for name in existing_docs])
            kb_context = (
                f"\n\nDANH SÁCH TÀI LIỆU HIỆN CÓ TRONG KHO DỮ LIỆU NỘI BỘ:\n"
                f"{docs_list_text}\n\n"
                f"NGUYÊN TẮC BẮT BUỘC KHI XỬ LÝ CÂU HỎI:\n"
                f"1. Hệ thống ĐÃ ĐƯỢC CUNG CẤP các tài liệu trên trong cơ sở dữ liệu nội bộ.\n"
                f"2. Bất cứ khi nào người dùng hỏi về bất kỳ thông tin, cá nhân, hồ sơ CV (ví dụ: Phú, Trần Phong Phú, kinh nghiệm, kỹ năng, năm sinh, liên hệ...), chính sách, quy chế hoặc bất kỳ chủ đề nào có thể nằm trong các tài liệu trên:\n"
                f"   BẮT BUỘC PHẢI GỌI CÔNG CỤ `tra_cuu_tai_lieu` ĐỂ TÌM KIẾM TRƯỚC KHI ĐƯA RA CÂU TRẢ LỜI.\n"
                f"3. TUYỆT ĐỐI KHÔNG ĐƯỢC từ chối hoặc nói rằng 'tôi là mô hình AI không có quyền truy cập thông tin cá nhân/CV' hay 'tôi chưa được cung cấp tài liệu' khi chưa gọi công cụ `tra_cuu_tai_lieu`!\n"
            )
        else:
            kb_context = "\n\n(Hiện tại kho dữ liệu chưa có tài liệu nào)."

        base_prompt = custom_system_prompt or SYSTEM_PROMPT
        system_msg = base_prompt + kb_context
        conversation = [{"role": "system", "content": system_msg}] + messages

        try:
            # 1. Gọi LLM lần đầu để kiểm tra xem có cần kích hoạt Tool hay không
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=conversation,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.3
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # TRƯỜNG HỢP 1: AI quyết định gọi một hoặc nhiều Tools
            if tool_calls:
                conversation.append(response_message)

                for tool_call in tool_calls:
                    fn_name = tool_call.function.name
                    fn_args_raw = tool_call.function.arguments
                    try:
                        fn_args = json.loads(fn_args_raw)
                    except Exception:
                        fn_args = {}

                    # Phát tín hiệu tool_start cho giao diện
                    yield json.dumps({
                        "type": "tool_call_start",
                        "tool_name": fn_name,
                        "tool_args": fn_args
                    })

                    # Thực thi hàm tương ứng
                    if fn_name in AVAILABLE_TOOLS:
                        try:
                            tool_result = AVAILABLE_TOOLS[fn_name](**fn_args)
                        except Exception as ex:
                            tool_result = f"Lỗi khi thực thi công cụ {fn_name}: {str(ex)}"
                    else:
                        tool_result = f"Không tìm thấy công cụ {fn_name}."

                    # Phát tín hiệu tool_result cho giao diện
                    yield json.dumps({
                        "type": "tool_call_result",
                        "tool_name": fn_name,
                        "result": tool_result
                    })

                    # Đưa kết quả của tool vào lịch sử để LLM đọc và tổng hợp
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": str(tool_result)
                    })

                # Gọi lần 2 để streaming câu trả lời hoàn chỉnh dựa trên kết quả của tool
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=conversation,
                    stream=True,
                    temperature=0.3
                )

                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else ""
                    if delta:
                        yield json.dumps({
                            "type": "content_delta",
                            "delta": delta
                        })

            # TRƯỜNG HỢP 2: Chitchat / Trả lời trực tiếp không cần tool
            else:
                # Nếu đã có content từ lần gọi đầu
                first_content = response_message.content or ""
                if first_content:
                    yield json.dumps({
                        "type": "content_delta",
                        "delta": first_content
                    })

            yield json.dumps({"type": "done"})

        except Exception as e:
            logger.error(f"Lỗi stream_chat: {e}", exc_info=True)
            yield json.dumps({
                "type": "error",
                "content": f"Đã xảy ra lỗi khi gọi AI: {str(e)}"
            })

ai_agent = AIAgent()
