"""
BGM 爬虫 - 搜索并下载背景音乐

支持：
- B站音频搜索 + 提取 MP3（主力，国内可用）
- 任意 URL 音频提取（yt-dlp 支持的站点均可）

用法：
    crawler = BgmCrawler()
    path = crawler.search_and_download("epic cinematic BGM")
    path = crawler.download_url("https://www.bilibili.com/video/BV1xx411c7mD")
"""

import json
import re
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class BgmInfo:
    """BGM 信息"""
    bvid: str
    title: str
    duration: float  # 秒
    url: str
    author: str = ""


class BgmCrawler:
    """BGM 爬虫"""

    def __init__(self, cache_dir: str = "cache/bgm"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search(self, keyword: str, max_results: int = 10) -> List[BgmInfo]:
        """在 B站搜索 BGM/音乐

        自动尝试多个关键词变体，按优先级排序。
        """
        # 生成搜索关键词变体
        kw_lower = keyword.lower()
        has_bgm = "bgm" in kw_lower or "音乐" in keyword
        has_pure = "纯音乐" in keyword

        search_variants = []
        if has_bgm or has_pure:
            search_variants.append(keyword)
        else:
            search_variants.append(f"{keyword} BGM")
            search_variants.append(f"{keyword} 纯音乐")
            search_variants.append(keyword)

        for search_kw in search_variants:
            print(f"  搜索 BGM: {search_kw}")
            results = self._search_bilibili(search_kw, max_results * 3)
            if results:
                # 按时长排序，优先选取 30s~5min 的短 BGM
                results.sort(key=lambda r: r.duration)
                # 过滤掉极端时长
                good = [r for r in results if 15 <= r.duration <= 1800]
                if good:
                    print(f"  找到 {len(good)} 个 BGM")
                    return good[:max_results]
                # 如果过滤后没有，放宽条件返回全部
                print(f"  找到 {len(results)} 个 BGM（未过滤）")
                return results[:max_results]
            print(f"  未找到结果，尝试下一个关键词...")

        print("  所有关键词均未找到 BGM")
        return []

    def _search_bilibili(self, keyword: str, page_size: int = 30) -> List[BgmInfo]:
        """执行一次 B站搜索"""
        import requests

        api_url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://search.bilibili.com/",
        }
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": 1,
            "page_size": min(page_size, 50),
        }

        try:
            resp = requests.get(api_url, params=params, headers=headers, timeout=10,
                                proxies={"http": None, "https": None})
            data = resp.json()
            if data.get("code") != 0:
                print(f"  搜索失败: {data.get('message', 'unknown')}")
                return []

            results = []
            for v in data.get("data", {}).get("result", []):
                dur_str = v.get("duration", "0:00")
                dur_sec = self._parse_duration(dur_str)
                if dur_sec < 15:
                    continue

                results.append(BgmInfo(
                    bvid=v.get("bvid", ""),
                    title=self._strip_html(v.get("title", "")),
                    duration=dur_sec,
                    url=f"https://www.bilibili.com/video/{v.get('bvid', '')}",
                    author=v.get("author", ""),
                ))

            return results

        except Exception as e:
            print(f"  搜索出错: {e}")
            return []

    def search_and_download(self, keyword: str, max_clips: int = 5) -> List[str]:
        """搜索并下载 BGM（返回 MP3 路径列表）"""
        print(f"\n{'='*50}")
        print(f"BGM 搜索下载: {keyword}")
        print(f"{'='*50}")

        bgms = self.search(keyword, max_results=max_clips * 2)
        if not bgms:
            print("  未找到 BGM")
            return []

        downloaded = []
        for i, bgm in enumerate(bgms):
            if len(downloaded) >= max_clips:
                break

            # 用 bvid 作为文件名，避免中文路径导致 librosa 读取失败
            cache_path = self.cache_dir / f"{bgm.bvid}.mp3"

            if cache_path.exists():
                print(f"  [{i+1}] 已缓存: {bgm.title[:40]}")
                downloaded.append(str(cache_path))
                continue

            print(f"  [{i+1}] 下载: {bgm.title[:40]}... ({self._format_dur(bgm.duration)})")
            path = self._extract_audio(bgm.url, str(cache_path))
            if path:
                downloaded.append(path)
                print(f"       -> {Path(path).name}")
            time.sleep(1)

        print(f"  下载完成: {len(downloaded)} 个 BGM")
        return downloaded

    def download_url(self, url: str) -> Optional[str]:
        """从任意 URL 提取音频（yt-dlp 支持的站点均可）"""
        # 用 URL hash 作为文件名
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
        cache_path = self.cache_dir / f"url_{url_hash}.mp3"

        if cache_path.exists():
            print(f"  已缓存: {cache_path.name}")
            return str(cache_path)

        print(f"  提取音频: {url[:60]}...")
        return self._extract_audio(url, str(cache_path))

    def _extract_audio(self, url: str, output_path: str) -> Optional[str]:
        """用 yt-dlp 提取音频为 MP3"""
        cmd = [
            "yt-dlp", "--js-runtimes", "node",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",  # 最高音质
            "-o", output_path,
            "--no-playlist",
            "--no-post-overwrites",
            url,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path

            # yt-dlp 有时输出到 .m4a 然后转 .mp3
            mp3_path = Path(output_path).with_suffix(".mp3")
            if mp3_path.exists():
                return str(mp3_path)

            stderr = result.stderr[:200] if result.stderr else ""
            print(f"       提取失败: {stderr}")
            return None
        except subprocess.TimeoutExpired:
            print("       提取超时")
            return None
        except FileNotFoundError:
            print("       yt-dlp 未安装")
            return None

    @staticmethod
    def _parse_duration(dur_str: str) -> float:
        parts = dur_str.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0.0
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def _format_dur(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r'<[^>]+>', '', text)
