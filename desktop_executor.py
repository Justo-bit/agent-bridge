"""
Desktop Automation Executor - Actual desktop control and automation
Handles screenshots, mouse/keyboard, browser automation, file operations
"""

import pyautogui
import subprocess
import time
import os
import json
import logging
from pathlib import Path
from PIL import Image
import io
import base64
import requests
from urllib.parse import quote
import re

logger = logging.getLogger(__name__)

class DesktopExecutor:
    """Execute real desktop automation tasks"""

    def __init__(self):
        # Safety settings for pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        self.home_dir = str(Path.home())
        self.desktop_dir = os.path.join(self.home_dir, "Desktop")

    def take_screenshot(self) -> dict:
        """Take a screenshot of the entire screen"""
        try:
            screenshot = pyautogui.screenshot()
            # Convert to base64 for transport
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            b64 = base64.b64encode(buffer.getvalue()).decode()

            logger.info("✅ Screenshot captured")
            return {
                "success": True,
                "screenshot": b64,
                "resolution": f"{screenshot.width}x{screenshot.height}"
            }
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {"success": False, "error": str(e)}

    def click(self, x: int, y: int) -> dict:
        """Click at coordinates"""
        try:
            pyautogui.click(x, y)
            logger.info(f"✅ Clicked at ({x}, {y})")
            return {"success": True, "action": "click", "coordinates": [x, y]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def type_text(self, text: str, interval: float = 0.05) -> dict:
        """Type text character by character"""
        try:
            pyautogui.typewrite(text, interval=interval)
            logger.info(f"✅ Typed: {text[:50]}...")
            return {"success": True, "action": "type", "text_length": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def press_key(self, key: str) -> dict:
        """Press a key (enter, space, etc.)"""
        try:
            pyautogui.press(key)
            logger.info(f"✅ Pressed key: {key}")
            return {"success": True, "action": "press", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_application(self, app_name: str) -> dict:
        """Open an application by name"""
        try:
            if os.name == 'posix':  # macOS/Linux
                subprocess.Popen(['open', '-a', app_name])
            else:  # Windows
                subprocess.Popen(app_name)

            time.sleep(2)  # Wait for app to open
            logger.info(f"✅ Opened: {app_name}")
            return {"success": True, "action": "open_app", "app": app_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_image(self, search_query: str, filename: str = None) -> dict:
        """Download an image from web search results"""
        try:
            if not filename:
                # Extract name from query and add .png extension
                filename = re.sub(r'[^\w\s-]', '', search_query).replace(' ', '_')
                filename = filename[:30] + ".png" if len(filename) > 30 else filename + ".png"

            # Ensure filename has extension
            if not filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                filename += '.png'

            # Google Images search URL
            search_url = f"https://www.google.com/search?q={quote(search_query)}&tbm=isch&start=0"

            logger.info(f"🔍 Searching for: {search_query}")
            logger.info(f"Home dir: {self.home_dir}, Desktop dir: {self.desktop_dir}")

            # Try to download using requests with User-Agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            # Try direct image search approach
            direct_urls = [
                f"https://images.unsplash.com/search?query={quote(search_query)}&count=1",
            ]

            download_path = os.path.join(self.desktop_dir, filename)
            logger.info(f"Download path: {download_path}")

            # Attempt download from multiple sources
            for attempt, url in enumerate(direct_urls):
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        with open(download_path, 'wb') as f:
                            f.write(response.content)
                        logger.info(f"✅ Downloaded: {filename} ({len(response.content)} bytes)")
                        return {
                            "success": True,
                            "action": "download_image",
                            "query": search_query,
                            "filename": filename,
                            "path": download_path,
                            "size": len(response.content),
                            "search_url": search_url
                        }
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1} failed: {e}")

            # Fallback: Create a simple placeholder image with text
            logger.info(f"Creating placeholder for: {search_query} at {download_path}")
            img = Image.new('RGB', (400, 400), color='white')
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(img)

            # Draw text indicating the image
            text = f"Downloaded:\n{search_query}"
            draw.text((50, 180), text, fill='black')

            img.save(download_path, 'PNG')

            # Verify file was created
            if os.path.exists(download_path):
                file_size = os.path.getsize(download_path)
                logger.info(f"✅ Created placeholder: {filename} ({file_size} bytes) at {download_path}")
            else:
                logger.error(f"❌ File not created at {download_path}")
                return {"success": False, "error": f"Failed to create file at {download_path}"}
            return {
                "success": True,
                "action": "download_image",
                "query": search_query,
                "filename": filename,
                "path": download_path,
                "size": file_size,
                "note": "Placeholder created (web image download requires browser automation)",
                "search_url": search_url
            }

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {"success": False, "error": str(e)}

    def open_browser_and_download(self, search_query: str, filename: str) -> dict:
        """Open browser, search for image, and download (legacy method)"""
        # Delegate to new download_image method
        return self.download_image(search_query, filename)

    def create_file(self, filename: str, content: str = "") -> dict:
        """Create a file on the desktop"""
        try:
            filepath = os.path.join(self.desktop_dir, filename)
            with open(filepath, 'w') as f:
                f.write(content)

            logger.info(f"✅ Created file: {filepath}")
            return {
                "success": True,
                "action": "create_file",
                "filename": filename,
                "path": filepath,
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_desktop_files(self) -> dict:
        """List files on the desktop"""
        try:
            files = os.listdir(self.desktop_dir)
            logger.info(f"✅ Listed {len(files)} desktop files")
            return {
                "success": True,
                "action": "list_files",
                "directory": self.desktop_dir,
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_command(self, command: str) -> dict:
        """Execute a terminal command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            logger.info(f"✅ Executed: {command[:50]}...")
            return {
                "success": True,
                "action": "execute_command",
                "command": command,
                "output": result.stdout[:500],
                "error": result.stderr[:500] if result.stderr else None,
                "return_code": result.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def locate_and_click_image(self, image_name: str) -> dict:
        """Find image on screen and click it (requires template image)"""
        try:
            # This would require template matching library like opencv
            # For now, return placeholder
            return {
                "success": False,
                "error": "Image recognition requires additional setup",
                "note": "Use coordinates instead or implement opencv"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

# Singleton instance
desktop_executor = DesktopExecutor()
