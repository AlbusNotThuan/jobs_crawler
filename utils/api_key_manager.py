"""
API Key Manager - Quản lý API keys cho Google API
Tự động xoay vòng key khi có lỗi
"""

import os
from pathlib import Path

class APIKeyManager:
    def __init__(self, key_file_path=None):
        """
        Khởi tạo API Key Manager
        
        Args:
            key_file_path (str): Đường dẫn đến file chứa API keys
        """
        if not key_file_path:
            # Mặc định sử dụng file key.txt ở thư mục gốc
            self.key_file_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "key.txt"
        else:
            self.key_file_path = Path(key_file_path)
            
        self.api_keys = []
        self.current_index = 0
        self.load_keys()
    
    def load_keys(self):
        """Load tất cả API keys từ file"""
        if not self.key_file_path.exists():
            raise FileNotFoundError(f"API key file not found: {self.key_file_path}")
            
        with open(self.key_file_path, 'r') as file:
            # Đọc tất cả các dòng, loại bỏ khoảng trắng và dòng trống
            self.api_keys = [line.strip() for line in file if line.strip()]
            
        if not self.api_keys:
            raise ValueError("No API keys found in the file")
            
        print(f"Loaded {len(self.api_keys)} API keys")
    
    def get_current_key(self):
        """Lấy API key hiện tại"""
        if not self.api_keys:
            raise ValueError("No API keys available")
        return self.api_keys[self.current_index]
    
    def next_key(self):
        """Chuyển sang API key tiếp theo và trả về key đó"""
        if not self.api_keys:
            raise ValueError("No API keys available")
            
        # Tăng chỉ số và quay vòng nếu cần
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        return self.get_current_key()

# Singleton instance
_instance = None

def get_api_key_manager(key_file_path=None):
    """
    Hàm lấy instance của APIKeyManager (singleton pattern)
    """
    global _instance
    if _instance is None:
        _instance = APIKeyManager(key_file_path)
    return _instance
