#!/usr/bin/env python3
"""
网页长截图工具 - 基于 Playwright
功能：支持完整页面截图、自定义视口、延迟加载等
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, ViewportSize
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class ImageInfo(BaseModel):
    """图片信息"""
    src: str = Field(description="图片链接")
    alt: str = Field(default="", description="图片alt文本")
    width: str = Field(default="", description="图片宽度")
    height: str = Field(default="", description="图片高度")


class WebPageContent(BaseModel):
    """网页内容数据模型"""
    screenshot_path: str = Field(description="截图保存路径")
    url: str = Field(description="最终URL（可能重定向）")
    title: str = Field(description="页面标题")
    text_content: str = Field(description="纯文本内容（可见内容）")
    html: str = Field(description="完整HTML源码")
    meta: dict[str, str] = Field(default_factory=dict, description="Meta标签信息")
    images: list[ImageInfo] = Field(default_factory=list, description="图片列表")
    headings: dict[str, list[str]] = Field(default_factory=dict, description="标题结构 {h1: [...], h2: [...]}")

    class Config:
        json_schema_extra = {
            "example": {
                "screenshot_path": "screenshots/example.png",
                "url": "https://example.com",
                "title": "Example Domain",
                "text_content": "This domain is for use in illustrative examples...",
                "html": "<!doctype html>...",
                "meta": {"description": "Example domain", "viewport": "width=device-width"},
                "images": [{"src": "https://example.com/logo.png", "alt": "Logo", "width": "100", "height": "50"}],
                "headings": {"h1": ["Example Domain"], "h2": ["More Information"]}
            }
        }


class WebScreenshot:
    """网页截图工具类"""

    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        """
        初始化截图工具

        Args:
            headless: 是否使用无头模式
            browser_type: 浏览器类型 ("chromium", "firefox", "webkit")
        """
        self.headless = headless
        self.browser_type = browser_type

    def capture(
        self,
        url: str,
        output_path: str,
        full_page: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_time: int = 3,
        scroll_delay: float = 0.5,
        timeout: int = 30000,
    ) -> bool:
        """
        截取网页截图

        Args:
            url: 目标网页 URL
            output_path: 输出文件路径
            full_page: 是否截取完整页面（True=长截图，False=仅可视区域）
            viewport_width: 视口宽度
            viewport_height: 视口高度
            wait_time: 页面加载后等待时间（秒）
            scroll_delay: 滚动延迟（秒），用于触发懒加载
            timeout: 页面加载超时时间（毫秒）

        Returns:
            bool: 是否成功
        """
        try:
            with sync_playwright() as p:
                browser = self._launch_browser(p)
                page = browser.new_page(
                    viewport=ViewportSize(
                        width=viewport_width, height=viewport_height
                    )
                )
                page.set_default_timeout(timeout)

                # 加载页面
                self._load_page(page, url, wait_time, full_page, scroll_delay)

                # 截图
                print(f"正在截图: {output_path}")
                page.screenshot(
                    path=output_path,
                    full_page=full_page,
                    animations="disabled",
                    scale="device",
                    type="png",
                )

                browser.close()
                print("✅ 截图成功！")
                return True

        except PlaywrightTimeout:
            print(f"❌ 错误: 页面加载超时 ({timeout}ms)")
            return False
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return False

    def capture_full(
        self,
        url: str,
        output_path: str,
        full_page: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_time: int = 3,
        scroll_delay: float = 0.5,
        timeout: int = 30000,
    ) -> Optional[WebPageContent]:
        """
        一次性获取网页截图和内容（避免重复访问）

        Args:
            url: 目标网页 URL
            output_path: 输出文件路径
            full_page: 是否截取完整页面
            viewport_width: 视口宽度
            viewport_height: 视口高度
            wait_time: 页面加载后等待时间（秒）
            scroll_delay: 滚动延迟（秒）
            timeout: 页面加载超时时间（毫秒）

        Returns:
            WebPageContent: 包含截图路径和页面内容的数据模型，失败返回 None
        """
        try:
            with sync_playwright() as p:
                browser = self._launch_browser(p)
                page = browser.new_page(
                    viewport=ViewportSize(
                        width=viewport_width, height=viewport_height
                    )
                )
                page.set_default_timeout(timeout)

                # 加载页面
                self._load_page(page, url, wait_time, full_page, scroll_delay)

                # 截图
                print(f"正在截图: {output_path}")
                page.screenshot(
                    path=output_path,
                    full_page=full_page,
                    animations="disabled",
                    scale="device",
                    type="png",
                )

                # 提取内容
                print("正在提取页面内容...")
                content = self._extract_content(page, output_path)

                browser.close()
                print("✅ 截图和内容提取成功！")
                return content

        except PlaywrightTimeout:
            print(f"❌ 错误: 页面加载超时 ({timeout}ms)")
            return None
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return None

    def _launch_browser(self, playwright):
        """启动浏览器"""
        if self.browser_type == "firefox":
            return playwright.firefox.launch(headless=self.headless)
        elif self.browser_type == "webkit":
            return playwright.webkit.launch(headless=self.headless)
        else:
            return playwright.chromium.launch(headless=self.headless)

    def _load_page(self, page, url: str, wait_time: int, full_page: bool, scroll_delay: float):
        """加载页面并触发懒加载"""
        print(f"正在访问: {url}")
        page.goto(url, wait_until="load")

        # 额外等待时间
        if wait_time > 0:
            print(f"等待 {wait_time} 秒...")
            time.sleep(wait_time)

        # 如果需要完整截图，模拟滚动以触发懒加载
        if full_page and scroll_delay > 0:
            print("触发懒加载内容...")
            self._trigger_lazy_load(page, scroll_delay)

    def _extract_content(self, page, screenshot_path: str) -> WebPageContent:
        """
        从页面提取所有内容

        Args:
            page: Playwright 页面对象
            screenshot_path: 截图保存路径

        Returns:
            WebPageContent: 包含页面所有内容的数据模型
        """
        # 基础信息
        url = page.url
        title = page.title()

        # 文本内容
        text_content = page.inner_text('body')
        html = page.content()

        # Meta 标签
        meta = self._extract_meta(page)

        # 图片信息
        images = self._extract_images(page)

        # 标题结构
        headings = self._extract_headings(page)

        return WebPageContent(
            screenshot_path=screenshot_path,
            url=url,
            title=title,
            text_content=text_content,
            html=html,
            meta=meta,
            images=images,
            headings=headings,
        )

    def _extract_meta(self, page) -> dict:
        """提取 meta 标签信息"""
        meta = {}

        # 常见 meta 标签
        meta_names = ['description', 'keywords', 'author', 'viewport']
        for name in meta_names:
            try:
                element = page.query_selector(f'meta[name="{name}"]')
                if element:
                    content = element.get_attribute('content')
                    if content:
                        meta[name] = content
            except Exception:
                pass

        # Open Graph 标签
        og_tags = page.query_selector_all('meta[property^="og:"]')
        for tag in og_tags:
            try:
                prop = tag.get_attribute('property')
                content = tag.get_attribute('content')
                if prop and content:
                    meta[prop] = content
            except Exception:
                pass

        return meta

    def _extract_images(self, page) -> list[ImageInfo]:
        """提取所有图片信息"""
        images = []
        img_elements = page.query_selector_all('img')

        for img in img_elements:
            try:
                src = img.get_attribute('src') or ''
                # 只保存有 src 的图片
                if src:
                    images.append(ImageInfo(
                        src=src,
                        alt=img.get_attribute('alt') or '',
                        width=img.get_attribute('width') or '',
                        height=img.get_attribute('height') or '',
                    ))
            except Exception:
                pass

        return images

    def _extract_headings(self, page) -> dict:
        """提取标题结构 (h1-h6)"""
        headings = {}

        for level in range(1, 7):
            tag = f'h{level}'
            elements = page.query_selector_all(tag)
            texts = []

            for element in elements:
                try:
                    text = element.inner_text().strip()
                    if text:
                        texts.append(text)
                except Exception:
                    pass

            if texts:
                headings[tag] = texts

        return headings

    def _trigger_lazy_load(self, page, delay: float, max_scrolls: int = 50):
        """
        通过滚动触发懒加载内容

        Args:
            page: Playwright 页面对象
            delay: 每次滚动的延迟时间
            max_scrolls: 最大滚动次数，防止无限滚动
        """
        # 获取页面总高度
        total_height = page.evaluate("document.body.scrollHeight")
        viewport_height = page.viewport_size["height"]

        # 分步滚动
        current_position = 0
        scroll_count = 0
        while current_position < total_height and scroll_count < max_scrolls:
            page.evaluate(f"window.scrollTo(0, {current_position})")
            time.sleep(delay)
            current_position += viewport_height
            scroll_count += 1

            # 重新获取高度（内容可能动态加载）
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height > total_height:
                total_height = new_height

        # 滚动回顶部
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(delay)

        # 等待网络空闲，确保所有资源加载完成
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass  # 超时也继续，不阻断流程


def main():
    """示例：多种使用场景"""

    # 创建输出目录
    output_dir = Path("screenshots")
    output_dir.mkdir(exist_ok=True)

    screenshot = WebScreenshot(headless=True, browser_type="chromium")

    # 示例1: 只截图（原有功能）
    # url = "https://example.com"
    # screenshot.capture(
    #     url=url,
    #     output_path=str(output_dir / "example_screenshot.png"),
    #     full_page=True,
    # )

    # 示例2: 一次性获取截图和内容（推荐，节省资源）
    url = "https://example.com"
    url = "https://www.linkedin.com/in/andrewyng/"
    result = screenshot.capture_full(
        url=url,
        output_path=str(output_dir / f"example_full_{int(time.time())}.png"),
        full_page=True,
    )

    if result:
        print("\n" + "="*60)
        print("页面信息摘要:")
        print("="*60)
        print(f"URL: {result.url}")
        print(f"标题: {result.title}")
        print(f"截图: {result.screenshot_path}")
        print(f"\nMeta标签: {len(result.meta)} 个")
        for key, value in result.meta.items():
            print(f"  - {key}: {value[:100]}..." if len(value) > 100 else f"  - {key}: {value}")
        print(f"\n图片数量: {len(result.images)} 张")
        if result.images:
            print("  前3张图片:")
            for img in result.images[:3]:
                print(f"    - {img.src[:80]}..." if len(img.src) > 80 else f"    - {img.src}")
        print(f"\n标题结构:")
        for tag, texts in result.headings.items():
            print(f"  {tag.upper()}: {len(texts)} 个")
            for text in texts[:3]:  # 只显示前3个
                print(f"    - {text}")
        print(f"\n文本内容长度: {len(result.text_content)} 字符")
        print(f"文本内容预览:\n{result.text_content[:300]}...")
        print("="*60)

        # 演示: 可以轻松转换为 JSON 或字典
        # print("\n转换为字典:")
        # print(result.model_dump())
        # print("\n转换为 JSON:")
        # print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
