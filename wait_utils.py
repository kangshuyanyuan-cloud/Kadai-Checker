"""
wait_utils.py - 人間らしい待機処理ユーティリティ

ランダムな待機時間を使って、ボット検知を回避します。
"""

import asyncio
import random
import os
from dotenv import load_dotenv

load_dotenv()

# .envから待機時間を読み込む（デフォルト値付き）
MIN_WAIT = float(os.getenv("MIN_WAIT_SEC", "2"))
MAX_WAIT = float(os.getenv("MAX_WAIT_SEC", "5"))


async def random_wait(min_sec: float = None, max_sec: float = None) -> None:
    """ランダムな時間だけ待機する（人間らしい操作のため）"""
    min_s = min_sec if min_sec is not None else MIN_WAIT
    max_s = max_sec if max_sec is not None else MAX_WAIT
    wait_time = random.uniform(min_s, max_s)
    await asyncio.sleep(wait_time)


async def short_wait() -> None:
    """短い待機（0.3〜0.8秒）- 要素クリック前後など"""
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def medium_wait() -> None:
    """中程度の待機（1〜2.5秒）- ページ遷移後など"""
    await asyncio.sleep(random.uniform(1.0, 2.5))


async def long_wait() -> None:
    """長い待機（3〜7秒）- ログイン後、重いページなど"""
    await asyncio.sleep(random.uniform(3.0, 7.0))


async def think_wait() -> None:
    """人間が「考えている」ように見える待機（0.5〜1.5秒）"""
    await asyncio.sleep(random.uniform(0.5, 1.5))


async def typing_delay() -> float:
    """タイピング1文字あたりの遅延時間を返す（ミリ秒）"""
    # 人間のタイピング速度：50〜150ミリ秒/文字
    return random.uniform(50, 150)
