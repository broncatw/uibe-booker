"""uibe-booker：对外经济贸易大学图书馆 IC 预约系统命令行助手。"""

from uibe_booker.config import BookConfig
from uibe_booker.client import ICSeatClient

__all__ = ["BookConfig", "ICSeatClient"]
__version__ = "0.1.0"
