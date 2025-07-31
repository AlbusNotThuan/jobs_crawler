# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types
import json

import re
import asyncio

with open(os.path.join(os.path.dirname(__file__), "instruction.md"), "r", encoding="utf-8") as f:
    instruction_content = f.read()

async def analyze_job_content(content: str, job_title: str = "") -> dict:
    """
    Hàm bất đồng bộ, nhận vào string content JD và job title, trả về dict JSON kết quả phân tích.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _analyze_job_content_sync, content, job_title)

def _analyze_job_content_sync(content: str, job_title: str = "") -> dict:
    client = genai.Client(
        api_key="AIzaSyA1E3GLPaTRvSpJTF7iIReVP2wYDZj7K0U",
    )

    model = "gemini-2.0-flash"
    
    # Combine job title and content for better analysis
    combined_content = content
    if job_title.strip():
        combined_content = f"Job Title: {job_title.strip()}\n\nJob Description:\n{content}"
    
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=combined_content),
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
            return result
        except Exception as e:
            print(f"Lỗi parse JSON: {e}\nNội dung JSON: {json_str}")
            return {}
    else:
        print("Không tìm thấy JSON hợp lệ trong output!")
        return {}

# Ví dụ sử dụng async
if __name__ == "__main__":
    import sys
    async def main():
        # Đọc nội dung JD từ file hoặc truyền trực tiếp
        job_title = """<Job Title>"""
        content = """<JD content here>"""
        result = await analyze_job_content(content, job_title)
        print(result)
    asyncio.run(main())
