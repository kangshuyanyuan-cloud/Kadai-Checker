"""
human_behavior.py - 人間らしいブラウザ操作クラス

ボット検知を回避するため、マウス移動・クリック・スクロールを
人間らしく見せる処理をまとめたモジュールです。
"""

import asyncio
import random
import math
from playwright.async_api import Page, Locator
from wait_utils import short_wait, think_wait, typing_delay


class HumanBehavior:
    """
    人間らしいブラウザ操作を提供するクラス。
    直接このクラスを使って操作することで、ボット検知を回避できます。
    """

    def __init__(self, page: Page):
        self.page = page

    async def human_move_to(self, x: int, y: int) -> None:
        """
        マウスをなめらかに指定座標まで移動する。
        ベジェ曲線風の動きで人間らしさを再現。
        """
        # 現在位置を取得（わからない場合はランダムな位置から）
        start_x = random.randint(100, 800)
        start_y = random.randint(100, 600)

        # 中間点をランダムに設定（曲線的な動き）
        mid_x = (start_x + x) / 2 + random.randint(-50, 50)
        mid_y = (start_y + y) / 2 + random.randint(-50, 50)

        # ステップを減らして高速化
        steps = random.randint(3, 5)
        for i in range(steps + 1):
            t = i / steps
            # 2次ベジェ曲線の計算
            bx = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * mid_x + t ** 2 * x
            by = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * mid_y + t ** 2 * y
            await self.page.mouse.move(bx, by)
            # ステップ間の待機
            delay = random.uniform(0.001, 0.005)
            await asyncio.sleep(delay)

    async def human_click(self, locator: Locator) -> None:
        """
        要素をクリック前に少し待って、ランダム位置をクリックする。
        """
        await think_wait()

        # 要素の位置とサイズを取得
        try:
            box = await locator.bounding_box()
            if box:
                # 要素内のランダムな位置をクリック（端は避ける）
                margin = 5
                click_x = box["x"] + random.uniform(margin, box["width"] - margin)
                click_y = box["y"] + random.uniform(margin, box["height"] - margin)

                # マウスをなめらかに移動
                await self.human_move_to(click_x, click_y)
                await asyncio.sleep(random.uniform(0.01, 0.05))

                # クリック
                await self.page.mouse.click(click_x, click_y)
            else:
                # bounding_boxが取れない場合は通常クリック
                await locator.click()
        except Exception:
            # エラーが出ても通常クリックにフォールバック
            await locator.click()

        await short_wait()

    async def human_type(self, locator: Locator, text: str) -> None:
        """
        1文字ずつランダムな速度でテキストを入力する（人間のタイピング再現）。
        """
        await self.human_click(locator)
        await asyncio.sleep(random.uniform(0.05, 0.1))

        # 1文字ずつ入力
        for char in text:
            await locator.press(char)
            delay_ms = await typing_delay()
            await asyncio.sleep(delay_ms / 1000)

            # たまに少し長く止まる
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.05, 0.1))

    async def human_scroll(self, direction: str = "down", amount: int = None) -> None:
        """
        自然なスクロール動作を再現する。
        direction: "down" or "up"
        amount: スクロール量（ピクセル）、Noneならランダム
        """
        if amount is None:
            amount = random.randint(200, 500)

        if direction == "up":
            amount = -amount

        # 数回に分けてスクロール
        scroll_steps = random.randint(1, 2)
        step_amount = amount // scroll_steps

        for _ in range(scroll_steps):
            await self.page.mouse.wheel(0, step_amount)
            await asyncio.sleep(random.uniform(0.01, 0.05))

        await asyncio.sleep(random.uniform(0.05, 0.1))

    async def random_mouse_movement(self) -> None:
        """
        ランダムにマウスを動かす（ページ読み込み中の自然な動作）。
        """
        for _ in range(random.randint(2, 5)):
            x = random.randint(200, 1000)
            y = random.randint(100, 700)
            await self.human_move_to(x, y)
            await asyncio.sleep(random.uniform(0.01, 0.05))

    async def simulate_reading(self) -> None:
        """
        ページを読んでいるように見せる（スクロールしながら待機）。
        """
        read_time = random.uniform(0.1, 0.5)
        scroll_count = random.randint(1, 2)

        for _ in range(scroll_count):
            await asyncio.sleep(read_time / scroll_count)
            await self.human_scroll("down", random.randint(100, 300))
