# To run this code you need to install the following dependencies:
# pip install google-genai

import os
import json
import re
import asyncio
from google import genai
from google.genai import types
from pathlib import Path
from utils.api_key_manager import get_api_key_manager, APIKeyManager
from utils.getEmbedding import _get_embedding

# Đường dẫn đến file instruction.md và skill tags
INSTRUCTION_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "instruction.md"
# Khởi tạo API Key Manager
api_key_manager = get_api_key_manager()
# Đọc file instruction
with open(INSTRUCTION_PATH, "r", encoding="utf-8") as f:
    instruction_content = f.read()

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
    
    # Compose input as required by new prompt: JSON with raw_job_title and raw_job_description
    prompt_input = json.dumps({
        "raw_job_title": job_title,
        "raw_job_description": content
    }, ensure_ascii=False)
    text = None
    
    while retries < max_retries:
        try:
            print(f"Attempting analysis with API key: {current_key[:12]}...")
            client = genai.Client(api_key=current_key)
            model = "gemini-2.5-flash-lite"
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt_input),
                    ],
                ),
            ]
            tools = []
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
            break
        except Exception as e:
            error_message = str(e).lower()
            api_key_error = any(err in error_message for err in ["api key", "quota", "rate limit", "permission", "unauthorized", "authentication", "exhausted"])
            if api_key_error:
                retries += 1
                print(f"API key error ({current_key[:12]}...): {e}")
                if retries < max_retries:
                    current_key = api_key_manager.next_key()
                    print(f"Switching to next API key: {current_key[:12]}...")
                else:
                    print("Exhausted all API keys, returning empty result")
                    return {
                        "company_infomation": None,
                        "job_description": None,
                        "job_requirements": None,
                        "yoe": None,
                        "salary": None,
                        "job_expertise": None,
                        "job_description_embedding": None,
                        "job_requirements_embedding": None
                    }
            else:
                print(f"Non-API key error: {e}")
                return {
                    "company_infomation": None,
                    "job_description": None,
                    "job_requirements": None,
                    "yoe": None,
                    "salary": None,
                    "job_expertise": None,
                    "job_description_embedding": None,
                    "job_requirements_embedding": None
                }

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
            required_keys = [
                "company_infomation",
                "job_description",
                "job_requirements",
                "yoe",
                "salary",
                "job_expertise"
            ]
            for key in required_keys:
                if key not in result or result[key] in ["", [], {}]:
                    result[key] = None
            # Embedding for job description and job requirements
            if result.get("job_description"):
                result["job_description_embedding"] = _get_embedding(result["job_description"], api_key_manager)
            if result.get("job_requirements"):
                result["job_requirements_embedding"] = _get_embedding(result["job_requirements"], api_key_manager)
            # print(f"analyzer - Job Expertise: {result.get('job_expertise', 'N/A')}, YOE: {result.get('yoe', 'N/A')}, Salary: {result.get('salary', 'N/A')}")
            return result
        except Exception as e:
            print(f"Lỗi parse JSON: {e}")
            return {
                "company_infomation": None,
                "job_description": None,
                "job_requirements": None,
                "yoe": None,
                "salary": None,
                "job_expertise": None,
                "job_description_embedding": None,
                "job_requirements_embedding": None
            }
    else:
        print("Không tìm thấy JSON hợp lệ trong output!")
        return {
            "company_infomation": None,
            "job_description": None,
            "job_requirements": None,
            "yoe": None,
            "salary": None,
            "job_expertise": None,
            "job_description_embedding": None,
            "job_requirements_embedding": None
        }




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
            job_title = "Senior Database Administrator (DB2 and PostgreSQL) - Vietnam"
            content = """
            About the job At Globant, we are working to make the world a better place, one step at a time. We enhance business development and enterprise solutions to prepare them for a digital future. With a diverse and talented team present in more than 30 countries, we are strategic partners to leading global companies in their business process transformation. We seek a Senior Database Administrator who shares our passion for innovation and change. This role is critical to helping our business partners evolve and adapt to consumers' personalized expectations in this new technological era. YOU WILL GET THE CHANCE TO: Collaborate with customers, project management, software engineering and network operations teams for database requirements to enhance existing systems and design new systems Install new and upgrade existing systems Enforce database security, standards & guidelines Support and design 24x7 high availability solutions Database and server performance: analyze, configure, and monitor physical server hardware, operating system, and database software for optimal configuration of settings, data access patterns, disk io performance, etc. and recommendations for upgrades and new systems. Database development: queries, stored procedures, ETL, testing, code reviews, code optimizations, and index tuning Validate, plan, and execute database schema and code changes, bottleneck analysis, outage prevention/resolution, server/database performance improvements, database recovery and restores Planning for system growth Ensuring compliance with vendor license agreements Various reporting and data exportation and importation including csv, xml, and unstructured formats Document the database environment, processes, and best practices Provide technical support and problem resolution Production / On Call Support WHAT WILL HELP YOU SUCCEED? Bachelor’s Degree in Information Technology or a similar field At least 5 years of experience with DB2 At least 2 years of experience with PostgreSQL Extensive knowledge of SQL Data modeling Performance analysis tuning Experience with 24x7 transaction processing systems Good problem solving with attention to details, analytical, administrative, organizational, communication and interpersonal skills Good at English (both verbal and written) Additional Assets Experience in NoSQL Experience with Docker and Kubernetes Experience with migration tools (ora2pg/full convert/Sqlines/etc) Experience in in-memory Databases (Redis) This job can be filled in Hanoi/Danang or Ho Chi Minh Create with us digital products that people love. We will bring businesses and consumers together through AI technology and creativity, driving digital transformation to impact the world positively. We may use AI and machine learning technologies in our recruitment process. Globant is an Equal Opportunity employer. All qualified applicants will receive consideration for employment without regard to race, color, religion, sex, national origin, disability, veteran status, or any other characteristic protected by applicable federal, state, or local law. Globant is also committed to providing reasonable accommodations for qualified individuals with disabilities in our job application procedures. If you need assistance or an accommodation due to a disability, please let your recruiter know. Final compensation offered is based on multiple factors such as the specific role, hiring location, as well as individual skills, experience, and qualifications. In addition to competitive salaries, we offer a comprehensive benefits package. Learn more about life at Globant here: Globant Experience Guide .
            """
        
        result = await analyze_job_content(content, job_title)
        # print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(main())
