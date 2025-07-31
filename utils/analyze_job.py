# To run this code you need to install the following dependencies:
# pip install google-genai

import os
import json
import re
import asyncio
from google import genai
from google.genai import types
from pathlib import Path
from .api_key_manager import get_api_key_manager

# Đường dẫn đến file instruction.md và skill tags
INSTRUCTION_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "instruction.md"
SKILL_TAGS_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "it_skill_tags.txt"

# Khởi tạo API Key Manager
api_key_manager = get_api_key_manager()

# Đọc file instruction
with open(INSTRUCTION_PATH, "r", encoding="utf-8") as f:
    instruction_content = f.read()

# Đọc file skill tags
skill_tags = []
if SKILL_TAGS_PATH.exists():
    with open(SKILL_TAGS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lower()
            # Bỏ qua các dòng trống, tiêu đề hoặc ký hiệu markdown
            if line and not line.startswith('#') and not line.startswith('---') and not line.startswith('|'):
                # Loại bỏ ký hiệu markdown không cần thiết
                if not line.startswith("##"):  # Không phải tiêu đề danh mục
                    skill_tags.append(line)

print(f"Loaded {len(skill_tags)} skill tags from {SKILL_TAGS_PATH}")

def format_skill_tags(tags):
    """Format skill tags thành prompt dễ đọc cho LLM."""
    result = "\n\nAvailable skill tags:\n"
    for tag in tags:
        result += f"- {tag}\n"
    return result

async def analyze_job_content(content: str, job_title: str = "") -> dict:
    """
    Hàm bất đồng bộ, nhận vào string content JD và job title, trả về dict JSON kết quả phân tích.
    
    Args:
        content (str): Nội dung mô tả công việc cần phân tích
        job_title (str): Tiêu đề công việc (tùy chọn)
        
    Returns:
        dict: Dictionary chứa thông tin về skills, yoe, salary được trích xuất
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _analyze_job_content_sync, content, job_title)

def _analyze_job_content_sync(content: str, job_title: str = "") -> dict:
    """
    Hàm đồng bộ để gọi API Gemini và xử lý kết quả.
    Không nên gọi trực tiếp - hãy dùng analyze_job_content thay thế.
    """
    global api_key_manager
    
    # Lấy API key từ manager
    current_key = api_key_manager.get_current_key()
    
    # Số lần thử lại tối đa bằng số lượng key
    max_retries = len(api_key_manager.api_keys)
    retries = 0
    
    # Combine job title and content for better analysis
    combined_content = content
    if job_title.strip():
        combined_content = f"Job Title: {job_title.strip()}\n\nJob Description:\n{content}"
    
    # Thêm danh sách skill tags vào nội dung gửi đi nếu có
    if skill_tags:
        content_with_tags = combined_content + format_skill_tags(skill_tags)
    else:
        content_with_tags = combined_content
    
    text = None
    
    while retries < max_retries:
        try:
            print(f"Attempting analysis with API key: {current_key[:12]}...")
            
            # Khởi tạo client với key hiện tại
            client = genai.Client(api_key=current_key)
            
            model = "gemini-2.0-flash"
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=content_with_tags),
                    ],
                ),
            ]
            tools = [
                types.Tool(googleSearch=types.GoogleSearch()),
            ]
            generate_content_config = types.GenerateContentConfig(
                system_instruction=instruction_content,
                tools=tools,
            )

            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=generate_content_config,
            )
            text = response.text
            
            # Nếu thành công, thoát khỏi vòng lặp
            break
            
        except Exception as e:
            error_message = str(e).lower()
            
            # Kiểm tra nếu đây là lỗi API key
            api_key_error = any(err in error_message for err in ["api key", "quota", "rate limit", "permission", "unauthorized", "authentication"])
            
            if api_key_error:
                retries += 1
                print(f"API key error ({current_key[:12]}...): {e}")
                
                if retries < max_retries:
                    # Thử với key tiếp theo
                    current_key = api_key_manager.next_key()
                    print(f"Switching to next API key: {current_key[:12]}...")
                else:
                    print("Exhausted all API keys, returning empty result")
                    return {"skills": [], "yoe": "Not Specified", "salary": "Not Specified"}
            else:
                # Lỗi khác không liên quan đến API key
                print(f"Non-API key error: {e}")
                return {"skills": [], "yoe": "Not Specified", "salary": "Not Specified"}
    
    # Không tìm thấy phản hồi
    if not text:
        return {"skills": [], "yoe": "Not Specified", "salary": "Not Specified"}

    # Regex lấy phần JSON nằm giữa ```json và ``` hoặc '''json và '''
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if not match:
        match = re.search(r"'''json\s*([\s\S]*?)\s*'''", text)
    if not match:
        # Nếu không có markdown, thử bắt block JSON đầu tiên trong text
        match = re.search(r"\{[\s\S]*\}", text)
    
    if match:
        json_str = match.group(1) if match.lastindex else match.group(0)
        try:
            result = json.loads(json_str)
            
            # Đảm bảo kết quả trả về đúng định dạng mong muốn
            if "skills" in result and isinstance(result["skills"], list):
                # Đảm bảo skills là một mảng string
                if all(isinstance(skill, dict) and "name" in skill for skill in result["skills"]):
                    # Trường hợp cũ: list các dict có trường name
                    result["skills"] = [skill["name"] for skill in result["skills"]]
                # Giữ nguyên nếu đã đúng định dạng (list các string)
            else:
                result["skills"] = []
            
            if "yoe" not in result:
                result["yoe"] = "Not Specified"
                
            if "salary" not in result:
                result["salary"] = "Not Specified"
                
            return result
        except Exception as e:
            print(f"Lỗi parse JSON: {e}\nNội dung JSON: {json_str}")
            return {"skills": [], "yoe": "Not Specified", "salary": "Not Specified"}
    else:
        print("Không tìm thấy JSON hợp lệ trong output!")
        return {"skills": [], "yoe": "Not Specified", "salary": "Not Specified"}

# Ví dụ sử dụng
if __name__ == "__main__":
    import sys
    
    async def main():
        # Đọc nội dung JD từ file hoặc command line
        if len(sys.argv) > 1:
            # Nếu có tham số từ command line
            with open(sys.argv[1], "r", encoding="utf-8") as f:
                content = f.read()
        else:
            # Demo content
            job_title = "DevOps Engineer"
            content = """
            Giới thiệu việc làm: DevOps Engineer
            
            We are looking for a skilled DevOps Engineer with experience in AWS, Docker, and Kubernetes.
            You will be responsible for maintaining our cloud infrastructure and implementing CI/CD pipelines.
            
            Required skills:
            - Linux system administration
            - Python scripting 
            - Docker containerization
            - AWS cloud services
            - Kubernetes orchestration
            
            Must be fluent in English for team communication.
            """
        
        result = await analyze_job_content(content, job_title)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(main())
