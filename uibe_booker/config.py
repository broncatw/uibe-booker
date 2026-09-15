"""配置加载：优先环境变量，其次本地 TOML（config.local.toml，不入库）。

⚠️ 学号密码等凭据只保存在本机，config.local.toml 已被 .gitignore 排除。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:                                    # Python 3.11+ 内置
    import tomllib
except ModuleNotFoundError:             # pragma: no cover
    tomllib = None

DEFAULT_BASE_URL = "http://seat.uibe.edu.cn"
DEFAULT_CONFIG_FILE = "config.local.toml"


@dataclass(frozen=True)
class BookConfig:
    """IC 预约系统的连接配置。"""

    username: str
    password: str
    base_url: str = DEFAULT_BASE_URL
    #: 登录后携带 token 的请求头名称（该系统家族通常直接用 "token"）
    auth_header: str = "token"
    #: 登录请求体里用户名的字段名。2026-09-14 实测：JSON 提交下
    # "username"/"loginName" 均提示「登录名称不能为空」，说明真实字段名
    # 不同（如 userName/account/userAccount）。请 F12 抓一次真实登录，
    # 把请求体里的用户名字段名填到这里。
    login_field: str = "username"
    timeout: float = 10.0

    @classmethod
    def load(cls, config_file: str | Path | None = None,
             **overrides) -> "BookConfig":
        """加载配置：文件 < 环境变量 < 显式参数（优先级依次升高）。

        环境变量：UIBE_USERNAME / UIBE_PASSWORD / UIBE_BASE_URL
        """
        file_values: dict = {}
        path = Path(config_file or os.environ.get(
            "UIBE_CONFIG", DEFAULT_CONFIG_FILE))
        if path.exists() and tomllib is not None:
            with path.open("rb") as f:
                file_values = tomllib.load(f)

        def pick(key: str, env: str) -> str:
            return str(overrides.get(key)
                       or os.environ.get(env)
                       or file_values.get(key)
                       or "")

        cfg = cls(
            username=pick("username", "UIBE_USERNAME"),
            password=pick("password", "UIBE_PASSWORD"),
            base_url=pick("base_url", "UIBE_BASE_URL") or DEFAULT_BASE_URL,
            auth_header=str(file_values.get("auth_header", "token")),
            login_field=str(file_values.get("login_field", "username")),
            timeout=float(file_values.get("timeout", 10.0)),
        )
        if not cfg.username or not cfg.password:
            raise ValueError(
                "缺少学号/密码：请设置环境变量 UIBE_USERNAME/UIBE_PASSWORD，"
                f"或创建 {DEFAULT_CONFIG_FILE}（参考 config.example.toml）")
        return cfg
