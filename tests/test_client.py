"""IC 客户端测试：全部 mock，不触网。"""

import pytest
import requests

from uibe_booker.client import ICError, ICSeatClient
from uibe_booker.config import BookConfig


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class FakeSession:
    """记录请求并按队列返回预设响应。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}          # 客户端初始化时会 update 这里

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def make_client(responses, config=None):
    session = FakeSession(list(responses))
    client = ICSeatClient(config or BookConfig(username="u", password="p",
                                               base_url="http://seat.test"),
                          session=session)
    return client, session


def test_login_success_stores_token():
    client, session = make_client(responses=[
        FakeResponse({"code": 200, "message": "成功",
                      "data": {"token": "abc123"}}),
    ])
    assert client.login() == "abc123"
    method, url, kwargs = session.calls[0]
    assert url.endswith("/ic-web/login")
    assert kwargs["json"] == {"logonName": "u", "password": "p"}


def test_login_field_name_configurable():
    """登录字段名可配置（实测系统不认 username，需抓包确认真实字段名）。"""
    from uibe_booker.config import BookConfig
    cfg = BookConfig(username="20230101", password="p",
                     base_url="http://seat.test", login_field="userAccount")
    client, session = make_client(responses=[
        FakeResponse({"code": 200, "data": {"token": "t"}}),
    ], config=cfg)
    client.login()
    _, _, kwargs = session.calls[0]
    assert kwargs["json"]["userAccount"] == "20230101"
    assert "username" not in kwargs["json"]
    # 后续请求带 token 头
    session.responses.append(FakeResponse({"code": 200, "data": {"x": 1}}))
    client.today_stat()
    _, _, kwargs2 = session.calls[1]
    assert kwargs2["headers"]["token"] == "t"


def test_login_wrong_password_raises():
    client, session = make_client(responses=[
        FakeResponse({"code": 300, "message": "用户名或密码错误"}),
    ])
    with pytest.raises(ICError, match="用户名或密码错误"):
        client.login()


def test_not_logged_in_error_surfaced():
    client, session = make_client(responses=[
        FakeResponse({"code": 200, "data": {"token": "t"}}),
        FakeResponse({"code": 300, "message": "用户未登录，请重新登录"}),
    ])
    client.login()
    with pytest.raises(ICError, match="用户未登录"):
        client.today_stat()


def test_reserve_sends_expected_payload():
    client, session = make_client(responses=[
        FakeResponse({"code": 200, "data": {"token": "t"}}),
        FakeResponse({"code": 200, "data": {"id": 9}}),
    ])
    client.login()
    out = client.reserve(seat_id=42, day="2026-09-15", start="08:00", end="12:00")
    method, url, kwargs = session.calls[1]
    assert url.endswith("/ic-web/reserve")
    assert kwargs["json"] == {"seatId": 42, "day": "2026-09-15",
                              "start": "08:00", "end": "12:00"}
    assert out == {"id": 9}


def test_non_json_response_raises():
    class BadJsonResponse:
        status_code = 502

        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("no json")

    client, session = make_client(responses=[BadJsonResponse()])
    with pytest.raises(ICError, match="响应不是 JSON"):
        client.login()


def test_endpoint_override():
    client, session = make_client(responses=[
        FakeResponse({"code": 200, "data": {"token": "t"}}),
        FakeResponse({"code": 200, "data": []}),
    ])
    client.endpoints["today_stat"] = "/ic-web/stat2"
    client.login()
    client.today_stat()
    assert session.calls[1][1].endswith("/ic-web/stat2")
