"""错误日志：写入 <配置目录>/logs/cleaner.log，方便事后排查与开源反馈。

只在错误/警告时写入，不影响正常使用。
"""

from __future__ import annotations

import logging

from .config import config_dir

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """获取全局 logger（懒初始化：首次调用时创建日志文件）。"""
    global _logger
    if _logger is None:
        log_dir = config_dir() / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        logger = logging.getLogger("agent_cleaner")
        logger.setLevel(logging.WARNING)
        for h in logger.handlers:  # 重新初始化时关闭旧 handler，避免文件句柄泄漏
            h.close()
        logger.handlers.clear()
        handler = logging.FileHandler(
            log_dir / "cleaner.log",
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        _logger = logger
    return _logger
