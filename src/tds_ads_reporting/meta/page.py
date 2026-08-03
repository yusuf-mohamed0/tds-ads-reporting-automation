from __future__ import annotations

import calendar
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from tds_ads_reporting.meta.ads import parse_float, parse_int

GRAPH = "https://graph.facebook.com"


class MetaGraphError(RuntimeError):
    pass


def _request(access_token: str, api_version: str, path: str, params: dict[str, Any]) -> dict:
    url = f"{GRAPH}/{api_version}/{path}"
    params = {**params, "access_token": access_token}
    resp = requests.get(url, params=params, timeout=60)
    payload = resp.json()
    if "error" in payload:
        err = payload["error"]
        raise MetaGraphError(f"Graph API {err.get('code')} {err.get('error_subcode', '')}: {err.get('message')}")
    return payload


def _paginate(access_token: str, api_version: str, path: str, params: dict[str, Any]) -> list[dict]:
    out: list[dict] = []
    url = f"{GRAPH}/{api_version}/{path}"
    while url:
        params = {**params, "access_token": access_token}
        resp = requests.get(url, params=params, timeout=60)
        payload = resp.json()
        if "error" in payload:
            err = payload["error"]
            raise MetaGraphError(f"Graph API {err.get('code')} {err.get('error_subcode', '')}: {err.get('message')}")
        out.extend(payload.get("data", []))
        url = (payload.get("paging") or {}).get("next")
        time.sleep(0.6)
    return out


def _month_epoch_range(month: str) -> tuple[int, int]:
    year, mon = (int(x) for x in month.split("-"))
    since_dt = datetime(year, mon, 1, tzinfo=timezone.utc)
    if mon == 12:
        until_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        until_dt = datetime(year, mon + 1, 1, tzinfo=timezone.utc)
    return int(since_dt.timestamp()), int(until_dt.timestamp())


def _sum_series(rows: list[dict]) -> float:
    total = 0.0
    for row in rows:
        vals = row.get("values", [])
        for v in vals:
            val = v.get("value")
            if isinstance(val, (int, float)):
                total += val
    return total


def _last_value(rows: list[dict]) -> float:
    for row in reversed(rows or []):
        vals = row.get("values") or []
        if vals:
            val = vals[-1].get("value")
            if isinstance(val, (int, float)):
                return val
    return 0.0


@dataclass
class PageMetrics:
    page_id: str
    media_views: int = 0
    organic_views: int = 0
    paid_views: int = 0
    followers_total: int = 0
    followers_delta: int = 0
    new_conversations: int = 0
    messages_sent: int = 0
    geo: list[dict] = field(default_factory=list)

    @property
    def organic_pct(self) -> int:
        if not self.media_views:
            return 0
        return round(self.organic_views / self.media_views * 100)


@dataclass
class PostRow:
    post_id: str
    created_time: str
    permalink: str
    message: str = ""
    views: int = 0


@dataclass
class InstagramMetrics:
    ig_id: str
    reach: int = 0
    views: int = 0
    accounts_engaged: int = 0
    followers_count: int = 0
    demographics: list[dict] = field(default_factory=list)
    top_media: list[dict] = field(default_factory=list)


def fetch_page_metrics(access_token: str, api_version: str, page_id: str, month: str) -> PageMetrics:
    since, until = month_range(month)
    metrics = PageMetrics(page_id=page_id)

    def get_metric(metric: str, period: str, extra: dict | None = None) -> list[dict]:
        params: dict[str, Any] = {"metric": metric, "period": period}
        if period != "lifetime":
            params["since"] = since
            params["until"] = until
        if extra:
            params.update(extra)
        payload = _request(access_token, api_version, f"{page_id}/insights", params)
        return payload.get("data", [])

    metrics.media_views = int(_sum_series(get_metric("page_total_media_view_unique", "day")))
    split = get_metric("page_media_view", "day", {"breakdown": "is_from_ads"})
    for row in split:
        vals = row.get("values", [])
        for v in vals:
            b = v.get("breakdowns") or []
            is_from_ads = any(
                d.get("dimension") == "is_from_ads" and d.get("value") == "true" for d in b
            )
            val = v.get("value")
            if isinstance(val, (int, float)):
                if is_from_ads:
                    metrics.paid_views += val
                else:
                    metrics.organic_views += val

    metrics.followers_total = int(_last_value(get_metric("page_follows", "lifetime")))
    metrics.followers_delta = int(_sum_series(get_metric("page_follows", "day")))
    metrics.new_conversations = int(
        _sum_series(get_metric("page_messages_new_conversations_unique", "total_over_range"))
    )
    metrics.messages_sent = int(_sum_series(get_metric("page_messages_sent", "day")))
    metrics.geo = get_metric("page_follows_country", "lifetime")
    return metrics


def fetch_top_posts(access_token: str, api_version: str, page_id: str, month: str, limit: int = 20) -> list[PostRow]:
    since, until = month_range(month)
    since_ts = int(datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    until_ts = int(datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())

    posts = _paginate(
        access_token,
        api_version,
        f"{page_id}/posts",
        {"fields": "id,created_time,permalink_url,message", "limit": 100},
    )
    in_month = [
        p
        for p in posts
        if p.get("created_time") and since_ts <= _ts(p["created_time"]) < until_ts
    ]

    rows: list[PostRow] = []
    for p in in_month[:limit]:
        try:
            payload = _request(
                access_token,
                api_version,
                f"{p['id']}/insights",
                {"metric": "post_total_media_view_unique", "period": "lifetime"},
            )
            views = 0
            for row in payload.get("data", []):
                for v in row.get("values", []):
                    val = v.get("value")
                    if isinstance(val, (int, float)):
                        views += val
        except MetaGraphError:
            views = 0
        rows.append(
            PostRow(
                post_id=p["id"],
                created_time=p.get("created_time", ""),
                permalink=p.get("permalink_url", ""),
                message=(p.get("message") or "")[:120],
                views=int(views),
            )
        )
        time.sleep(0.6)
    rows.sort(key=lambda r: r.views, reverse=True)
    return rows[:10]


def fetch_instagram_metrics(access_token: str, api_version: str, ig_id: str, month: str) -> InstagramMetrics:
    since_ts, until_ts = _month_epoch_range(month)
    m = InstagramMetrics(ig_id=ig_id)

    def get_metric(metric: str) -> list[dict]:
        payload = _request(
            access_token,
            api_version,
            f"{ig_id}/insights",
            {"metric": metric, "period": "day", "since": since_ts, "until": until_ts},
        )
        return payload.get("data", [])

    m.reach = int(_sum_series(get_metric("reach")))
    m.views = int(_sum_series(get_metric("views")))
    m.accounts_engaged = int(_sum_series(get_metric("accounts_engaged")))

    profile = _request(access_token, api_version, ig_id, {"fields": "followers_count"})
    m.followers_count = parse_int(profile.get("followers_count"))

    try:
        demo = _request(
            access_token,
            api_version,
            f"{ig_id}/insights",
            {
                "metric": "follower_demographics",
                "period": "this_month",
                "metric_type": "total_value",
                "breakdown": "gender,age",
            },
        )
        m.demographics = demo.get("data", [])
    except MetaGraphError:
        m.demographics = []

    media = _paginate(access_token, api_version, f"{ig_id}/media", {"fields": "id,timestamp", "limit": 100})
    in_month = [me for me in media if since_ts <= _ts(me.get("timestamp")) < until_ts]
    tops: list[dict] = []
    for me in in_month[:30]:
        try:
            payload = _request(
                access_token,
                api_version,
                f"{me['id']}/insights",
                {"metric": "reach,saved,comments,likes,views,total_interactions"},
            )
            vals: dict[str, float] = {}
            for row in payload.get("data", []):
                name = row.get("name", "")
                for v in row.get("values", []):
                    val = v.get("value")
                    if isinstance(val, (int, float)):
                        vals[name] = vals.get(name, 0) + val
            tops.append({"id": me["id"], "timestamp": me.get("timestamp", ""), **vals})
        except MetaGraphError:
            continue
        time.sleep(0.6)
    tops.sort(key=lambda t: t.get("reach", 0), reverse=True)
    m.top_media = tops[:10]
    return m


def _ts(iso: str) -> int:
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except (ValueError, TypeError):
        return 0


def month_range(month: str) -> tuple[str, str]:
    from tds_ads_reporting.meta.ads import month_range as _mr

    return _mr(month)
