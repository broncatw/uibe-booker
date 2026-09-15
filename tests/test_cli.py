"""CLI 测试（mock 客户端，验证参数解析与错误出口）。"""

import pytest

from uibe_booker.cli import build_parser, main


def test_parser_requires_command(capsys):
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_book_command_parses(monkeypatch, capsys):
    captured = {}

    class FakeClient:
        def reserve(self, seat_id, day, start, end):
            captured.update(seat_id=seat_id, day=day, start=start, end=end)
            return {"ok": True}

    monkeypatch.setattr(
        "uibe_booker.cli._client", lambda args: FakeClient())
    code = main(["--config", "nope.toml", "book", "42",
                 "2026-09-15", "08:00", "12:00"])
    assert code == 0
    assert captured == {"seat_id": "42", "day": "2026-09-15",
                        "start": "08:00", "end": "12:00"}


def test_error_returns_exit_code_1(monkeypatch, capsys):
    class BoomClient:
        def buildings(self):
            raise RuntimeError("网络不可达")

    monkeypatch.setattr(
        "uibe_booker.cli._client", lambda args: BoomClient())
    code = main(["--config", "nope.toml", "areas"])
    assert code == 1
    assert "网络不可达" in capsys.readouterr().err
