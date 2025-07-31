import logging
import os
from datetime import datetime
from typing import Optional

class CrawlerLogger:
    """
    Centralized logging utility for job crawler operations.
    Creates separate log files for different crawler types and operations.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize the logger with a specified log directory.
        
        Args:
            log_dir (str): Directory to store log files
        """
        self.log_dir = log_dir
        self.ensure_log_directory()
        self.loggers = {}
        
    def ensure_log_directory(self):
        """Create log directory if it doesn't exist."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            print(f"✓ Created log directory: {self.log_dir}")
    
    def get_logger(self, logger_name: str, log_file: Optional[str] = None) -> logging.Logger:
        """
        Get or create a logger with the specified name.
        
        Args:
            logger_name (str): Name of the logger
            log_file (str, optional): Custom log file name. If None, uses logger_name
            
        Returns:
            logging.Logger: Configured logger instance
        """
        if logger_name in self.loggers:
            return self.loggers[logger_name]
        
        # Create logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        if log_file is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            log_file = f"{logger_name}_{timestamp}.log"
        
        log_path = os.path.join(self.log_dir, log_file)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Store logger
        self.loggers[logger_name] = logger
        
        logger.info(f"Logger '{logger_name}' initialized - Log file: {log_path}")
        return logger
    
    def get_linkedin_logger(self) -> logging.Logger:
        """Get logger specifically for LinkedIn crawler operations."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return self.get_logger("linkedin_crawler", f"linkedin_crawler_{timestamp}.log")
    
    def get_itviec_logger(self) -> logging.Logger:
        """Get logger specifically for ITviec crawler operations."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return self.get_logger("itviec_crawler", f"itviec_crawler_{timestamp}.log")
    
    def get_database_logger(self) -> logging.Logger:
        """Get logger specifically for database operations."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return self.get_logger("database_operations", f"database_{timestamp}.log")
    
    def get_ai_logger(self) -> logging.Logger:
        """Get logger specifically for AI analysis operations."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return self.get_logger("ai_analysis", f"ai_analysis_{timestamp}.log")
    
    def log_crawler_start(self, logger: logging.Logger, crawler_type: str, config: dict):
        """Log the start of a crawler operation with configuration details."""
        logger.info("=" * 60)
        logger.info(f"🚀 Starting {crawler_type} Crawler Operation")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        for key, value in config.items():
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for sub_key, sub_value in value.items():
                    logger.info(f"    {sub_key}: {sub_value}")
            else:
                logger.info(f"  {key}: {value}")
        logger.info("=" * 60)
    
    def log_crawler_end(self, logger: logging.Logger, crawler_type: str, stats: dict):
        """Log the end of a crawler operation with statistics."""
        logger.info("=" * 60)
        logger.info(f"🏁 {crawler_type} Crawler Operation Completed")
        logger.info("=" * 60)
        logger.info("Final Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 60)
    
    def log_job_processing(self, logger: logging.Logger, job_index: int, total_jobs: int, job_title: str, status: str):
        """Log individual job processing status."""
        logger.info(f"[{job_index}/{total_jobs}] {status}: {job_title}")
    
    def log_error(self, logger: logging.Logger, operation: str, error: Exception, context: dict = None):
        """Log errors with context information."""
        logger.error(f"❌ Error in {operation}: {str(error)}")
        if context:
            logger.error(f"Context: {context}")
        logger.exception("Full stack trace:")
    
    def log_warning(self, logger: logging.Logger, message: str, context: dict = None):
        """Log warnings with optional context."""
        logger.warning(f"⚠️  {message}")
        if context:
            logger.warning(f"Context: {context}")
    
    def log_success(self, logger: logging.Logger, message: str, details: dict = None):
        """Log successful operations with optional details."""
        logger.info(f"✅ {message}")
        if details:
            for key, value in details.items():
                logger.info(f"  {key}: {value}")
    
    def close_all_loggers(self):
        """Close all logger handlers and clear the loggers dict."""
        for logger_name, logger in self.loggers.items():
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        self.loggers.clear()
        print("✓ All loggers closed")


# Global logger instance
crawler_logger = CrawlerLogger()

# Convenience functions for quick access
def get_linkedin_logger():
    """Quick access to LinkedIn logger."""
    return crawler_logger.get_linkedin_logger()

def get_itviec_logger():
    """Quick access to ITviec logger."""
    return crawler_logger.get_itviec_logger()

def get_database_logger():
    """Quick access to database logger."""
    return crawler_logger.get_database_logger()

def get_ai_logger():
    """Quick access to AI analysis logger."""
    return crawler_logger.get_ai_logger()


# Example usage
if __name__ == "__main__":
    # Test the logger
    logger = get_linkedin_logger()
    
    logger.info("Testing LinkedIn logger")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test database logger
    db_logger = get_database_logger()
    db_logger.info("Testing database logger")
    
    # Close all loggers
    crawler_logger.close_all_loggers()
