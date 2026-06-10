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
MIN_WAIT = float(os.getenv("MIN_WAIT_SEC", "0.1"))
MAX_WAIT = float(os.getenv("MAX_WAIT_SEC", "0.3"))


async def random_wait(min_sec: float = None, max_sec: float = None) -> None:
    """ランダムな時間だけ待機する（人間らしい操作のため）"""
    min_s = min_sec if min_sec is not None else MIN_WAIT
    max_s = max_sec if max_sec is not None else MAX_WAIT
    wait_time = random.uniform(min_s, max_s)
    await asyncio.sleep(wait_time)


async def short_wait() -> None:
    """短い待機"""
    await asyncio.sleep(random.uniform(0.1, 0.2))


async def medium_wait() -> None:
    """中程度の待機"""
    await asyncio.sleep(random.uniform(0.2, 0.4))


async def long_wait() -> None:
    """長い待機"""
    await asyncio.sleep(random.uniform(0.3, 0.5))


async def think_wait() -> None:
    """考えている待機"""
    await asyncio.sleep(random.uniform(0.1, 0.3))


async def typing_delay() -> float:
    """タイピング1文字あたりの遅延時間を返す（ミリ秒）"""
    return random.uniform(10, 30)
