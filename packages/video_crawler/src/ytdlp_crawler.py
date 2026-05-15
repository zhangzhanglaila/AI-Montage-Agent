"""
通用 yt-dlp 爬虫 - 支持 YouTube/Dailymotion/抖音/西瓜视频等

基于 yt-dlp，支持所有 yt-dlp 能解析的网站。
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class YtdlpVideoInfo:
    """视频信息"""
    id: str
    title: str
    duration: float  # 秒
    url: str
    uploader: str = ""
    description: str = ""


class YtdlpCrawler:
    """基于 yt-dlp 的通用视频爬虫"""

    # yt-dlp 支持的常用站点
    SUPPORTED_SITES = {
        "youtube": "https://www.youtube.com",
        "dailymotion": "https://www.dailymotion.com",
        "douyin": "https://www.douyin.com",
        "ixigua": "https://www.ixigua.com",
        "acfun": "https://www.acfun.cn",
        "微博": "https://weibo.com",
        "tiktok": "https://www.tiktok.com",
        "vimeo": "https://vimeo.com",
        "twitch": "https://www.twitch.tv",
    }

    def __init__(
        self,
        output_dir: str = "cache/ytdlp",
        max_duration: float = 600.0,
        min_duration: float = 5.0,
        proxy: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_duration = max_duration
        self.min_duration = min_duration
        self.proxy = proxy

    def _get_ytdlp_cmd(self) -> list:
        """获取 yt-dlp 命令"""
        return ["yt-dlp"]

    def search_and_download(
        self,
        keyword: str,
        max_clips: int = 20,
        site: str = "youtube",
    ) -> List[str]:
        """搜索并下载视频

        Args:
            keyword: 搜索关键词
            max_clips: 最大下载数
            site: 站点 (youtube/dailymotion/douyin/ixigua/acfun/vimeo)

        Returns:
            本地文件路径列表
        """
        base_url = self.SUPPORTED_SITES.get(site)
        if not base_url:
            print(f"不支持的站点: {site}")
            print(f"支持的站点: {', '.join(self.SUPPORTED_SITES.keys())}")
            return []

        # 构建搜索 URL
        if site == "youtube":
            search_url = f"ytsearch{max_clips}:{keyword}"
        elif site == "dailymotion":
            search_url = f"https://www.dailymotion.com/search/{keyword}/videos"
        elif site == "vimeo":
            search_url = f"vimeosearch{max_clips}:{keyword}"
        elif site == "douyin":
            search_url = f"https://www.douyin.com/search/{keyword}"
        elif site == "ixigua":
            search_url = f"https://www.ixigua.com/search/{keyword}"
        elif site == "acfun":
            search_url = f"https://www.acfun.cn/search?keyword={keyword}"
        else:
            search_url = f"{base_url}/search?q={keyword}"

        print(f"  搜索 {site}: {keyword}")

        # 先获取视频列表
        videos = self._search_videos(search_url, max_clips)
        if not videos:
            print(f"  未找到视频")
            return []

        print(f"  找到 {len(videos)} 个视频")

        # 下载
        downloaded = []
        for i, video in enumerate(videos):
            if len(downloaded) >= max_clips:
                break

            # 检查缓存
            cache_path = self.output_dir / f"{video.id}.mp4"
            if cache_path.exists():
                print(f"  [{i+1}/{len(videos)}] 已缓存: {video.title[:30]}")
                downloaded.append(str(cache_path))
                continue

            # 时长过滤
            if video.duration < self.min_duration or video.duration > self.max_duration:
                continue

            print(f"  [{i+1}/{len(videos)}] 下载: {video.title[:40]}...")
            path = self._download_video(video.url, str(cache_path))
            if path:
                downloaded.append(path)
            time.sleep(1)  # 下载间隔

        print(f"  下载完成: {len(downloaded)}/{len(videos)}")
        return downloaded

    def _search_videos(self, search_url: str, max_results: int) -> List[YtdlpVideoInfo]:
        """搜索视频列表"""
        cmd = self._get_ytdlp_cmd() + [
            "--flat-playlist",
            "--dump-json",
            "--no-download",
            "--playlist-end", str(max_results),
        ]
        if self.proxy:
            cmd.extend(["--proxy", self.proxy])
        cmd.append(search_url)

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="ignore")
                print(f"  yt-dlp 搜索失败: {stderr[:200]}")
                return []

            videos = []
            for line in result.stdout.decode("utf-8", errors="ignore").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    vid = YtdlpVideoInfo(
                        id=data.get("id", ""),
                        title=data.get("title", ""),
                        duration=data.get("duration", 0) or 0,
                        url=data.get("url") or data.get("webpage_url") or "",
                        uploader=data.get("uploader", ""),
                    )
                    if vid.url:
                        videos.append(vid)
                except json.JSONDecodeError:
                    continue
            return videos
        except subprocess.TimeoutExpired:
            print("  yt-dlp 搜索超时")
            return []
        except FileNotFoundError:
            print("  yt-dlp 未安装，请运行: pip install yt-dlp")
            return []

    def _download_video(self, url: str, output_path: str) -> Optional[str]:
        """下载单个视频"""
        cmd = self._get_ytdlp_cmd() + [
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", output_path,
            "--no-playlist",
        ]
        if self.proxy:
            cmd.extend(["--proxy", self.proxy])
        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path
            return None
        except subprocess.TimeoutExpired:
            return None


class DouyinCrawler(YtdlpCrawler):
    """抖音视频爬虫"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def search_and_download(self, keyword: str, max_clips: int = 20) -> List[str]:
        return super().search_and_download(keyword, max_clips, site="douyin")


class IxiguaCrawler(YtdlpCrawler):
    """西瓜视频爬虫"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def search_and_download(self, keyword: str, max_clips: int = 20) -> List[str]:
        return super().search_and_download(keyword, max_clips, site="ixigua")


class AcfunCrawler(YtdlpCrawler):
    """AcFun 视频爬虫"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def search_and_download(self, keyword: str, max_clips: int = 20) -> List[str]:
        return super().search_and_download(keyword, max_clips, site="acfun")


class VimeoCrawler(YtdlpCrawler):
    """Vimeo 视频爬虫"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def search_and_download(self, keyword: str, max_clips: int = 20) -> List[str]:
        return super().search_and_download(keyword, max_clips, site="vimeo")


def create_crawler(source: str, **kwargs) -> YtdlpCrawler:
    """工厂函数 - 创建对应源的爬虫"""
    crawlers = {
        "youtube": YtdlpCrawler,
        "dailymotion": YtdlpCrawler,
        "douyin": DouyinCrawler,
        "ixigua": IxiguaCrawler,
        "acfun": AcfunCrawler,
        "vimeo": VimeoCrawler,
    }
    cls = crawlers.get(source)
    if not cls:
        raise ValueError(f"不支持的源: {source}，支持: {', '.join(crawlers.keys())}")
    return cls(**kwargs)
