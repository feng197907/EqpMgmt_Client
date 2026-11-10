"""列表页分页工具。

背景：设备列表和文档检索此前是全量查询 + 整表渲染，
5,000 台设备就有 8 MB HTML，5 万份文档 65 MB / 1.5 秒，
浏览器构建上万个 DOM 节点会直接卡死。数据量和数据库选型无关，
所以统一在这里生成分页数据，模板只负责展示。

翻页链接在后端生成好放进 ``links``，模板不做任何 URL 拼接，
避免 ``url_for`` 的 ``**kwargs`` 在 Jinja 里出现兼容问题。
"""

from flask import url_for

DEFAULT_PER_PAGE = 20
# 页码窗口半径：当前页前后各 2 页。
# 5 万条记录会有 2500 页，渲染全部页码本身就是性能问题。
WINDOW_RADIUS = 2


def build_pagination(endpoint, page, per_page, total, **keep):
    """生成分页数据。

    :param endpoint: 当前列表页的 endpoint，用于生成翻页链接
    :param page: 当前页码（从 1 开始，越界会被夹到 [1, pages]）
    :param per_page: 每页条数
    :param total: 满足筛选条件的总条数
    :param keep: 需要保留的筛选参数（**不要**传 page）

    返回的 dict 可直接传给模板，包含：
    page / per_page / total / pages / window / links /
    first / prev / next / last / start_index / end_index
    """
    try:
        per_page = max(1, int(per_page or DEFAULT_PER_PAGE))
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    try:
        total = max(0, int(total or 0))
    except (TypeError, ValueError):
        total = 0

    pages = max(1, (total + per_page - 1) // per_page)
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    page = min(max(1, page), pages)

    start = max(1, page - WINDOW_RADIUS)
    end = min(pages, page + WINDOW_RADIUS)
    window = list(range(start, end + 1))

    # keep 里值为 None 的会被 url_for 忽略，不会生成 ?q=None 这类脏参数
    def link(target):
        return url_for(endpoint, page=target, **keep)

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "window": window,
        "window_start": start,
        "window_end": end,
        "links": {p: link(p) for p in window},
        "first": link(1) if page > 1 else None,
        "prev": link(page - 1) if page > 1 else None,
        "next": link(page + 1) if page < pages else None,
        "last": link(pages) if page < pages else None,
        "start_index": (page - 1) * per_page + 1 if total else 0,
        "end_index": min(page * per_page, total),
    }


def parse_page(raw, default=1):
    """从 query string 里取页码，非法值回退到默认值，避免 int() 抛 500。"""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= 1 else default
