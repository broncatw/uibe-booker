"""IC（Information Commons）预约系统客户端。

系统：对外经济贸易大学图书馆座位/研讨间预约（http://seat.uibe.edu.cn，
Vue 单页应用 + /ic-web JSON API）。

已实测确认（2026-09-14 探测，未登录响应）：
* 所有接口返回 JSON 信封 {"code": 200/300, "message", "data", "vals"}；
  code=300 表示业务失败（如未登录）。
* /ic-web/todayStat、/ic-web/building/list、/ic-web/space/list 等端点存在，
  未登录一律返回 code=300「用户未登录」。
* 登录契约：POST /ic-web/login，用户名+密码（本工具默认 JSON 提交），
  成功后从 data.token 取令牌，后续请求放入 ``token`` 请求头。
  若学校调整了登录参数名或鉴权头，请用浏览器开发者工具抓一次真实
  登录请求，修改 config.local.toml 的 auth_header / endpoints 即可，
  无需改代码。

模块代号（来自系统前端配置）：1=研讨间（研修间），8=座位，
32=考研座位，16=活动。
"""

from __future__ import annotations

from typing import Any

import requests

from uibe_booker.config import BookConfig

#: 默认端点表（相对 base_url；可在 config.local.toml 的 [endpoints] 覆盖）
DEFAULT_ENDPOINTS = {
    "login": "/ic-web/login",
    "today_stat": "/ic-web/todayStat",
    "building_list": "/ic-web/building/list",
    "space_list": "/ic-web/space/list",
    "seat_list": "/ic-web/space/seatList",
    "reserve": "/ic-web/reserve",
    "cancel": "/ic-web/cancel",
    "my_reservations": "/ic-web/myReservations",
}

#: 模块代号（系统前端 config.js sortedNav 注释）
MODULE_SEAT = 8
MODULE_ROOM = 1
MODULE_KAOYAN = 32


class ICError(RuntimeError):
    """IC 系统业务失败（code != 200）。"""


class ICSeatClient:
    """IC 预约系统客户端（登录态管理 + 常用操作）。"""

    def __init__(self, config: BookConfig, endpoints: dict | None = None,
                 session: requests.Session | None = None):
        self.config = config
        self.endpoints = {**DEFAULT_ENDPOINTS, **(endpoints or {})}
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (uibe-booker)",
            "Content-Type": "application/json",
        })
        self.token: str | None = None

    # ------------------------------------------------------------------ #
    # 基础请求
    # ------------------------------------------------------------------ #
    def _url(self, key: str) -> str:
        return self.config.base_url.rstrip("/") + self.endpoints[key]

    def _request(self, method: str, key: str, **kwargs) -> dict:
        """发请求并解包 JSON 信封；code != 200 抛 ICError。"""
        headers = kwargs.pop("headers", {})
        if self.token:
            headers[self.config.auth_header] = self.token
        resp = self.session.request(
            method, self._url(key), timeout=self.config.timeout,
            headers=headers, **kwargs)
        resp.raise_for_status()
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ICError(f"响应不是 JSON（{resp.status_code}）") from exc
        code = payload.get("code")
        if code != 200:
            raise ICError(f"IC 系统 code={code}: {payload.get('message')}")
        return payload

    # ------------------------------------------------------------------ #
    # 登录与账号
    # ------------------------------------------------------------------ #
    def login(self) -> str:
        """登录并缓存令牌。

        登录请求体为 JSON，用户名字段名由 config.login_field 决定
        （实测系统不认 username/loginName，抓包后配置正确字段名即可）。
        """
        body = {
            self.config.login_field: self.config.username,
            "password": self.config.password,
        }
        payload = self._request("POST", "login", json=body)
        data = payload.get("data") or {}
        self.token = data.get("token") or payload.get("token")
        if not self.token:
            raise ICError("登录成功但响应中未找到 token，请抓包核对字段名")
        return self.token

    def _ensure_login(self) -> None:
        if not self.token:
            self.login()

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def today_stat(self) -> Any:
        """今日预约/在馆统计。"""
        self._ensure_login()
        return self._request("GET", "today_stat").get("data")

    def buildings(self) -> Any:
        """楼栋/区域列表。"""
        self._ensure_login()
        return self._request("GET", "building_list").get("data")

    def spaces(self, building_id: str | int) -> Any:
        """某楼栋下的空间列表（阅览区 / 研讨间等）。"""
        self._ensure_login()
        return self._request("GET", "space_list",
                             params={"buildingId": building_id}).get("data")

    def seats(self, space_id: str | int, day: str) -> Any:
        """某空间某日的座位列表。day 格式 YYYY-MM-DD。"""
        self._ensure_login()
        return self._request("GET", "seat_list",
                             params={"spaceId": space_id, "day": day}).get("data")

    # ------------------------------------------------------------------ #
    # 预约操作
    # ------------------------------------------------------------------ #
    def reserve(self, seat_id: str | int, day: str, start: str, end: str) -> Any:
        """预约座位/研讨间（时间段格式 HH:MM）。"""
        self._ensure_login()
        return self._request("POST", "reserve", json={
            "seatId": seat_id, "day": day, "start": start, "end": end,
        }).get("data")

    def cancel(self, reservation_id: str | int) -> Any:
        """取消预约。"""
        self._ensure_login()
        return self._request("POST", "cancel",
                             json={"id": reservation_id}).get("data")

    def my_reservations(self) -> Any:
        """我的当前预约列表。"""
        self._ensure_login()
        return self._request("GET", "my_reservations").get("data")
