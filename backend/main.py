"""
A股智能分析工具站 - 后端API
"""
import sys, os
# 将项目根目录加入 path，确保可以 import backend.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.data_fetcher import (
    get_market_sentiment,
    get_sector_data,
    get_concept_sector_data,
    get_hot_stocks,
    search_stocks,
    get_index_history,
    get_market_indices,
)

app = FastAPI(title="A股智能分析", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ API 路由 ============

@app.get("/api/market/sentiment")
async def market_sentiment():
    """大盘情绪"""
    return get_market_sentiment()


@app.get("/api/market/indices")
async def market_indices():
    """主要指数行情"""
    return get_market_indices()


@app.get("/api/market/index-history")
async def index_history(days: int = Query(60, ge=5, le=365)):
    """指数历史数据"""
    return get_index_history(days)


@app.get("/api/sectors/industry")
async def industry_sectors():
    """行业板块行情"""
    return get_sector_data()


@app.get("/api/sectors/concept")
async def concept_sectors():
    """概念板块行情"""
    return get_concept_sector_data()


@app.get("/api/stocks/hot")
async def hot_stocks(top_n: int = Query(30, ge=10, le=100)):
    """热门个股（按成交额）"""
    return get_hot_stocks(top_n)


@app.get("/api/stocks/search")
async def stock_search(keyword: str = Query(..., min_length=1)):
    """搜索个股"""
    return search_stocks(keyword)


# ============ 前端静态文件 ============

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# 处理 SPA 路由：所有未匹配的路径返回 HTML
from fastapi.responses import FileResponse
import os.path

@app.get("/{page_path:path}")
async def serve_frontend(page_path: str):
    # 排除 API 路径
    if page_path.startswith("api/") or page_path in ("api",):
        return FileResponse(os.path.join(frontend_dir, "index.html"), status_code=404)
    # 尝试直接匹配文件
    file_path = os.path.join(frontend_dir, page_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    # 尝试 .html 后缀
    html_path = os.path.join(frontend_dir, f"{page_path}.html")
    if os.path.isfile(html_path):
        return FileResponse(html_path)
    # 回退到 index.html
    return FileResponse(os.path.join(frontend_dir, "index.html"))

# 暂不挂载静态文件（已由上面的路由覆盖）
# app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
