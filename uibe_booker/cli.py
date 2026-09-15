"""命令行入口：uibe login-test / areas / seats / book / cancel / mine。"""

from __future__ import annotations

import argparse
import json
import sys

from uibe_booker.client import ICSeatClient
from uibe_booker.config import BookConfig


def _client(args) -> ICSeatClient:
    cfg = BookConfig.load(getattr(args, "config", None))
    endpoints = {}
    if getattr(args, "endpoints", None):
        import tomllib
        with open(args.endpoints, "rb") as f:
            endpoints = tomllib.load(f).get("endpoints", {})
    return ICSeatClient(cfg, endpoints=endpoints)


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uibe",
        description="对外经济贸易大学图书馆 IC 预约系统命令行助手")
    parser.add_argument("--config", help="配置文件路径（默认 config.local.toml）")
    parser.add_argument("--endpoints", help="端点覆盖表 TOML（可选）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login-test", help="测试登录是否成功")
    p.set_defaults(func=lambda c, a: _print({"token_prefix": c.login()[:8]}))

    p = sub.add_parser("areas", help="楼栋/区域列表")
    p.set_defaults(func=lambda c, a: _print(c.buildings()))

    p = sub.add_parser("spaces", help="某楼栋下的空间列表")
    p.add_argument("building_id")
    p.set_defaults(func=lambda c, a: _print(c.spaces(a.building_id)))

    p = sub.add_parser("seats", help="某空间某日的座位列表")
    p.add_argument("space_id")
    p.add_argument("day", help="YYYY-MM-DD")
    p.set_defaults(func=lambda c, a: _print(c.seats(a.space_id, a.day)))

    p = sub.add_parser("book", help="预约座位/研讨间")
    p.add_argument("seat_id")
    p.add_argument("day", help="YYYY-MM-DD")
    p.add_argument("start", help="HH:MM")
    p.add_argument("end", help="HH:MM")
    p.set_defaults(func=lambda c, a: _print(c.reserve(a.seat_id, a.day,
                                                      a.start, a.end)))

    p = sub.add_parser("cancel", help="取消预约")
    p.add_argument("reservation_id")
    p.set_defaults(func=lambda c, a: _print(c.cancel(a.reservation_id)))

    p = sub.add_parser("mine", help="我的当前预约")
    p.set_defaults(func=lambda c, a: _print(c.my_reservations()))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = _client(args)
        args.func(client, args)
    except Exception as exc:                 # noqa: BLE001 — CLI 统一错误出口
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
