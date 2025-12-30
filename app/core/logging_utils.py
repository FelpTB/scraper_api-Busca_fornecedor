import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for logs.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Include extra attributes passed in extra={}
        if hasattr(record, "extra_data"):
             log_obj["data"] = record.extra_data
        
        # Include all extra attributes from extra={}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'levelno', 'lineno', 'module', 'msecs', 'message',
                          'pathname', 'process', 'processName', 'relativeCreated', 'thread',
                          'threadName', 'exc_info', 'exc_text', 'stack_info', 'extra_data']:
                if not key.startswith('_'):
                    log_obj[key] = value

        return json.dumps(log_obj, ensure_ascii=False)

def setup_logging():
    """
    Configures the root logger to output JSON to stdout and save to file.
    
    Logs são salvos em:
    - Console: stdout (formato JSON)
    - Arquivo: logs/server_YYYYMMDD.log (formato JSON, um arquivo por dia)
    """
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    root_logger.setLevel(logging.INFO)
    
    formatter = JSONFormatter()
    
    # Create console handler writing to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler for logs
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Arquivo de log com data (um arquivo por dia)
    log_filename = logs_dir / f"server_{datetime.now().strftime('%Y%m%d')}.log"
    
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    
    # Log onde os logs estão sendo salvos (após configurar handlers)
    logger = logging.getLogger(__name__)
    logger.info(f"📝 Logs sendo salvos em: {log_filename.absolute()}")
    
    # Set levels for third-party libraries to reduce noise if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

