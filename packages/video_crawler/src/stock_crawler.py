"""
免费素材视频爬虫 - Pexels / Pixabay
无版权、高清、可商用的原始视频素材，适合喂给 AI 混剪
"""

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests


@dataclass
class StockVideo:
    """素材视频信息"""
    id: str
    title: str
    url: str              # 视频页面链接
    download_url: str     # MP4 直链
    width: int
    height: int
    duration: float       # 秒
    source: str           # "pexels" / "pixabay"
    tags: List[str] = field(default_factory=list)


class BaseStockCrawler(ABC):
    """素材爬虫基类"""

    def __init__(self, api_key: str, cache_dir: str = "cache/stock"):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def search(self, keyword: str, max_results: int = 20, min_duration: int = 5, max_duration: int = 300) -> List[StockVideo]:
        """搜索视频素材"""
        ...

    def download(self, videos: List[StockVideo], max_clips: int = 20) -> List[str]:
        """下载视频到本地"""
        downloaded = []
        count = min(len(videos), max_clips)

        print(f"  准备下载 {count} 个素材...")

        for i, video in enumerate(videos[:count]):
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', video.title)[:50]
            filename = f"{video.source}_{video.id}_{safe_name}.mp4"
            output_path = self.cache_dir / filename

            if output_path.exists():
                print(f"  缓存 [{i+1}/{count}]: {video.title[:40]}...")
                downloaded.append(str(output_path))
                continue

            print(f"  下载 [{i+1}/{count}]: {video.title[:40]}... ({video.width}x{video.height}, {video.duration:.0f}s)")

            try:
                resp = requests.get(video.download_url, timeout=60, stream=True)
                resp.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded.append(str(output_path))
            except Exception as e:
                print(f"    下载失败: {e}")

            time.sleep(0.5)

        print(f"  成功下载 {len(downloaded)} 个素材")
        return downloaded

    def search_and_download(self, keyword: str, max_clips: int = 20) -> List[str]:
        """搜索并下载"""
        print(f"\n{'='*50}")
        print(f"素材搜索 [{self.__class__.__name__}]: {keyword}")
        print(f"{'='*50}")

        videos = self.search(keyword, max_results=max_clips * 2)
        if not videos:
            print("  未找到素材")
            return []

        return self.download(videos, max_clips=max_clips)


class PexelsCrawler(BaseStockCrawler):
    """Pexels 素材爬虫

    免费 API Key 注册: https://www.pexels.com/api/
    限额: 200 请求/小时，20,000/月
    """

    API_URL = "https://api.pexels.com/videos/search"

    def search(self, keyword: str, max_results: int = 20, min_duration: int = 5, max_duration: int = 300) -> List[StockVideo]:
        print(f"  搜索 Pexels: {keyword}")

        results = []
        page = 1
        per_page = min(max_results, 80)

        while len(results) < max_results:
            params = {
                "query": keyword,
                "per_page": per_page,
                "page": page,
            }

            try:
                resp = requests.get(
                    self.API_URL,
                    params=params,
                    headers={"Authorization": self.api_key},
                    timeout=10,
                )
                data = resp.json()

                if resp.status_code != 200:
                    print(f"  API 错误: {data.get('message', resp.status_code)}")
                    break

                videos_list = data.get("videos", [])
                if not videos_list:
                    break

                for v in videos_list:
                    duration = v.get("duration", 0)
                    if duration < min_duration or duration > max_duration:
                        continue

                    # 选择合适的分辨率（优先 720p+）
                    video_files = v.get("video_files", [])
                    best_file = self._pick_best_file(video_files)
                    if not best_file:
                        continue

                    results.append(StockVideo(
                        id=str(v.get("id", "")),
                        title=f"pexels_{v.get('id', '')}",
                        url=v.get("url", ""),
                        download_url=best_file.get("link", ""),
                        width=best_file.get("width", 0),
                        height=best_file.get("height", 0),
                        duration=duration,
                        source="pexels",
                    ))

                    if len(results) >= max_results:
                        break

                page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f"  搜索出错: {e}")
                break

        print(f"  找到 {len(results)} 个素材")
        return results

    @staticmethod
    def _pick_best_file(files: list) -> Optional[dict]:
        """选择最佳视频文件（优先 720p mp4）"""
        # 按分辨率排序，优先 720p
        candidates = [f for f in files if f.get("file_type", "").startswith("video/mp4")]
        if not candidates:
            candidates = files

        # 优先 HD
        hd = [f for f in candidates if f.get("quality") == "hd"]
        if hd:
            # 在 HD 中选最接近 720p 的
            hd.sort(key=lambda f: abs(f.get("height", 0) - 720))
            return hd[0]

        # 回退到最大分辨率
        candidates.sort(key=lambda f: f.get("height", 0), reverse=True)
        return candidates[0] if candidates else None


class PixabayCrawler(BaseStockCrawler):
    """Pixabay 素材爬虫

    免费 API Key 注册: https://pixabay.com/api/docs/
    限额: 5,000 请求/天
    """

    API_URL = "https://pixabay.com/api/videos/"

    def search(self, keyword: str, max_results: int = 20, min_duration: int = 5, max_duration: int = 300) -> List[StockVideo]:
        print(f"  搜索 Pixabay: {keyword}")

        results = []
        page = 1
        per_page = min(max_results, 200)

        while len(results) < max_results:
            params = {
                "key": self.api_key,
                "q": keyword,
                "per_page": per_page,
                "page": page,
                "video_type": "all",
            }

            try:
                resp = requests.get(self.API_URL, params=params, timeout=10)
                data = resp.json()

                if resp.status_code != 200:
                    print(f"  API 错误: {data.get('message', resp.status_code)}")
                    break

                hits = data.get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    duration = hit.get("duration", 0)
                    if duration < min_duration or duration > max_duration:
                        continue

                    # 选择视频文件
                    videos_dict = hit.get("videos", {})
                    best = self._pick_best(videos_dict)
                    if not best:
                        continue

                    tags = hit.get("tags", "")
                    results.append(StockVideo(
                        id=str(hit.get("id", "")),
                        title=tags.replace(",", " ")[:60],
                        url=hit.get("pageURL", ""),
                        download_url=best.get("url", ""),
                        width=best.get("width", 0),
                        height=best.get("height", 0),
                        duration=duration,
                        source="pixabay",
                        tags=[t.strip() for t in tags.split(",")],
                    ))

                    if len(results) >= max_results:
                        break

                page += 1
                time.sleep(0.5)

            except Exception as e:
                print(f"  搜索出错: {e}")
                break

        print(f"  找到 {len(results)} 个素材")
        return results

    @staticmethod
    def _pick_best(videos: dict) -> Optional[dict]:
        """选择最佳视频（优先 large，其次 medium，最后 small）"""
        for quality in ["large", "medium", "small", "tiny"]:
            v = videos.get(quality)
            if v and v.get("url"):
                return v
        return None


def create_stock_crawler(source: str = "pexels", api_key: Optional[str] = None, cache_dir: str = "cache/stock") -> BaseStockCrawler:
    """工厂方法：创建素材爬虫

    Args:
        source: 数据源 "pexels" 或 "pixabay"
        api_key: API Key，不传则从环境变量读取
        cache_dir: 缓存目录
    """
    if source == "pexels":
        key = api_key or os.environ.get("PEXELS_API_KEY", "")
        if not key:
            raise ValueError("Pexels 需要 API Key。免费注册: https://www.pexels.com/api/  设置环境变量 PEXELS_API_KEY")
        return PexelsCrawler(api_key=key, cache_dir=cache_dir)

    elif source == "pixabay":
        key = api_key or os.environ.get("PIXABAY_API_KEY", "")
        if not key:
            raise ValueError("Pixabay 需要 API Key。免费注册: https://pixabay.com/api/docs/  设置环境变量 PIXABAY_API_KEY")
        return PixabayCrawler(api_key=key, cache_dir=cache_dir)

    else:
        raise ValueError(f"不支持的数据源: {source}，可选: pexels, pixabay")
