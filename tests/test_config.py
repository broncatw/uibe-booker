"""配置加载测试。"""

import pytest

from uibe_booker.config import BookConfig


def test_load_from_env(monkeypatch):
    monkeypatch.setenv("UIBE_USERNAME", "u100")
    monkeypatch.setenv("UIBE_PASSWORD", "p100")
    cfg = BookConfig.load(config_file="/nonexistent/nope.toml")
    assert cfg.username == "u100"
    assert cfg.password == "p100"
    assert cfg.base_url == "http://seat.uibe.edu.cn"


def test_load_from_toml(tmp_path):
    f = tmp_path / "config.local.toml"
    f.write_text('username = "u1"\npassword = "p1"\nauth_header = "Authorization"\n',
                 encoding="utf-8")
    cfg = BookConfig.load(config_file=f)
    assert cfg.username == "u1"
    assert cfg.auth_header == "Authorization"


def test_env_overrides_file(monkeypatch, tmp_path):
    f = tmp_path / "config.local.toml"
    f.write_text('username = "from_file"\npassword = "p"\n', encoding="utf-8")
    monkeypatch.setenv("UIBE_USERNAME", "from_env")
    cfg = BookConfig.load(config_file=f)
    assert cfg.username == "from_env"


def test_missing_credentials_raise(monkeypatch, tmp_path):
    monkeypatch.delenv("UIBE_USERNAME", raising=False)
    monkeypatch.delenv("UIBE_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="缺少学号/密码"):
        BookConfig.load(config_file=tmp_path / "none.toml")


def test_explicit_kwargs_win(monkeypatch, tmp_path):
    f = tmp_path / "config.local.toml"
    f.write_text('username = "f"\npassword = "p"\n', encoding="utf-8")
    monkeypatch.setenv("UIBE_USERNAME", "e")
    cfg = BookConfig.load(config_file=f, username="explicit")
    assert cfg.username == "explicit"
