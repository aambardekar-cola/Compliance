import logging
import sys
import traceback
from typing import Any, Dict, Optional

from shared.db import get_db_session
from shared.models import PipelineLog

# Standard Python logger
logger = logging.getLogger("pco.pipeline")
logger.setLevel(logging.INFO)

# Console handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class PipelineLogger:
    """Utility to log both to CloudWatch (via stdout) and the database."""
    
    def __init__(self, component: str):
        self.component = component
        self.logger = logger

    async def _log_to_db(self, level: str, message: str, details: Optional[Dict[str, Any]] = None, stack_trace: Optional[str] = None):
        """Asynchronously write a log entry to the database."""
        try:
            async with get_db_session() as session:
                new_log = PipelineLog(
                    component=self.component,
                    level=level,
                    message=message,
                    details=details,
                    stack_trace=stack_trace
                )
                session.add(new_log)
                await session.commit()
        except Exception as e:
            # Fallback to standard logging if DB write fails to avoid infinite loops
            self.logger.error(f"Failed to write log to DB: {e}")

    async def info(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.logger.info(f"[{self.component}] {message}")
        await self._log_to_db("INFO", message, details)

    async def warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.logger.warning(f"[{self.component}] {message}")
        await self._log_to_db("WARNING", message, details)

    async def error(self, message: str, details: Optional[Dict[str, Any]] = None, exc_info: bool = False):
        stack_trace = traceback.format_exc() if exc_info else None
        self.logger.error(f"[{self.component}] {message}", exc_info=exc_info)
        await self._log_to_db("ERROR", message, details, stack_trace)

def get_pipeline_logger(component: str) -> PipelineLogger:
    return PipelineLogger(component)
