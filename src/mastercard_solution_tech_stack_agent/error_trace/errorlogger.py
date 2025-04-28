import inspect
import sys
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from src.mastercard_solution_tech_stack_agent.config.appconfig import env_config


class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Logger:
    def __init__(self, log_dir: str = "src/mastercard_solution_tech_stack_agent/logs"):
        self.log_dir = Path(log_dir)
        self.log_files = {
            LogLevel.INFO: self.log_dir / "info.log",
            LogLevel.WARNING: self.log_dir / "warning.log",
            LogLevel.ERROR: self.log_dir / "error.log",
        }
        self._ensure_log_directory()
        self._log_cache = set()  # To prevent duplicate logs

    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_caller_info(self, tb=None) -> tuple[str, str]:
        """
        Get information about the calling function and its parent.
        Skips logger frames to get actual caller.
        """
        stack = inspect.stack()
        # Skip logger frames
        caller_frame = next(
            (frame for frame in stack if frame.filename != __file__),
            stack[2] if len(stack) > 2 else None,
        )
        current_function = caller_frame.function if caller_frame else "Unknown"
        parent_function = stack[3].function if len(stack) > 3 else "Unknown"
        return current_function, parent_function

    def _format_message(
        self,
        level: LogLevel,
        message: str,
        error: Optional[Exception] = None,
        additional_info: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> str:
        """Format the complete log message with all metadata."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(error, Exception):
            current_function, parent_function = self._get_caller_info(
                error.__traceback__
            )
        else:
            current_function, parent_function = self._get_caller_info(None)

        log_msg = [
            "=" * 80,
            f"TIMESTAMP: {timestamp}",
            f"LEVEL: {level.value}",
            f"FUNCTION: {current_function}",
            f"PARENT FUNCTION: {parent_function}",
            "-" * 80,
            f"MESSAGE: {message}",
        ]

        if error:
            log_msg.extend(
                [
                    f"ERROR TYPE: {type(error).__name__}",
                    f"ERROR MESSAGE: {str(error)}",
                    "-" * 80,
                ]
            )

            if exc_info and isinstance(error, Exception):
                try:
                    trace_lines = traceback.format_exception(
                        type(error), error, error.__traceback__
                    )
                    log_msg.extend(["FULL TRACEBACK:", "".join(trace_lines)])
                except (TypeError, ValueError) as e:
                    log_msg.append(f"Failed to format traceback: {e}")

        default_context = {
            "ai_engineer": "Muhammad",
            "environment": env_config.env,
        }

        if additional_info and isinstance(additional_info, dict):
            default_context.update(additional_info)

        log_msg.extend(
            [
                "-" * 80,
                "CONTEXT:",
                "\n".join(f"{k}: {v}" for k, v in default_context.items()),
                "=" * 80 + "\n",
            ]
        )

        return "\n".join(log_msg)

    def _write_log(self, level: LogLevel, message: str) -> None:
        """Write message to log file with duplicate prevention."""
        log_hash = hash(message)
        if log_hash in self._log_cache:
            return

        try:
            self._ensure_log_directory()
            with open(self.log_files[level], "a", encoding="utf-8") as f:
                f.write(message)
            self._log_cache.add(log_hash)
        except OSError as e:
            print(f"Failed to write log: {e}", file=sys.stderr)

    def info(
        self, message: str, additional_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an informational message."""
        log_message = self._format_message(
            LogLevel.INFO, message, additional_info=additional_info
        )
        self._write_log(LogLevel.INFO, log_message)

    def warning(
        self, message: str, additional_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a warning message."""
        log_message = self._format_message(
            LogLevel.WARNING, message, additional_info=additional_info
        )
        self._write_log(LogLevel.WARNING, log_message)

    def error(
        self,
        error: Exception,
        additional_info: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """
        Log an error with optional traceback.

        Args:
            error: Exception to log
            additional_info: Optional context dictionary
            exc_info: Whether to include full traceback
        """
        log_message = self._format_message(
            LogLevel.ERROR, "An error occurred", error, additional_info, exc_info
        )
        self._write_log(LogLevel.ERROR, log_message)

    def clear_logs(self, level: Optional[LogLevel] = None) -> None:
        """Clear log files for specified level or all levels."""
        try:
            targets = [self.log_files[level]] if level else self.log_files.values()
            for log_file in targets:
                try:
                    with open(log_file, "w", encoding="utf-8") as f:
                        f.write("")
                    self._log_cache.clear()
                except FileNotFoundError:
                    pass
        except OSError as e:
            print(f"Failed to clear logs: {str(e)}", file=sys.stderr)


# Initialize the logger
system_logger = Logger()
