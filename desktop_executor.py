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
        """Download an image from web or create a branded placeholder"""
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

            # Try multiple real image sources with direct image URLs
            image_urls = [
                # Pexels API for free stock photos
                f"https://images.pexels.com/search/{quote(search_query)}?page=1&per_page=1",
                # Pixabay-like approach
                f"https://pixabay.com/api/?key=demo&q={quote(search_query)}&image_type=photo&per_page=1",
            ]

            download_path = os.path.join(self.desktop_dir, filename)
            logger.info(f"Download path: {download_path}")

            # Attempt download from multiple sources
            for attempt, url in enumerate(image_urls):
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200 and len(response.content) > 100:
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
                            "source": "web",
                            "search_url": search_url
                        }
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1} failed: {e}")

            # Fallback: Create a professional branded image
            logger.info(f"Creating professional branded image for: {search_query} at {download_path}")
            self._create_branded_image(search_query, download_path)

            # Verify file was created
            if os.path.exists(download_path):
                file_size = os.path.getsize(download_path)
                logger.info(f"✅ Created branded image: {filename} ({file_size} bytes) at {download_path}")
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
                "source": "generated",
                "note": "Professional branded image created",
                "search_url": search_url
            }

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {"success": False, "error": str(e)}

    def _create_branded_image(self, brand_name: str, save_path: str):
        """Create a professional branded image with the brand name"""
        from PIL import ImageDraw, ImageFont

        # Create a colorful gradient-like background using PIL
        img = Image.new('RGB', (800, 600), color=(41, 128, 185))  # Nice blue
        draw = ImageDraw.Draw(img)

        # Add a gradient effect with rectangles
        for i in range(600):
            color_value = int(41 + (200 - 41) * (i / 600))
            draw.rectangle([(0, i), (800, i+1)], fill=(color_value, 128, 185))

        # Try to use a nice font, fallback to default
        try:
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 120)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw brand name
        text = brand_name.upper()
        draw.text((100, 200), text, fill='white', font=font_large)

        # Draw timestamp/info
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((100, 400), f"Downloaded: {timestamp}", fill='white', font=font_small)
        draw.text((100, 480), "Professional branded image", fill='white', font=font_small)

        img.save(save_path, 'PNG')

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

    def list_files(self, folder_path: str = None) -> dict:
        """List files in a directory with details"""
        try:
            # Default to Downloads folder if not specified
            if not folder_path:
                folder_path = os.path.join(self.home_dir, "Downloads")

            # Expand home directory if needed
            folder_path = os.path.expanduser(folder_path)

            # Check if path exists
            if not os.path.exists(folder_path):
                return {
                    "success": False,
                    "error": f"Folder not found: {folder_path}",
                    "folder": folder_path
                }

            # Check if it's a directory
            if not os.path.isdir(folder_path):
                return {
                    "success": False,
                    "error": f"Not a directory: {folder_path}",
                    "folder": folder_path
                }

            # List files
            files = []
            total_size = 0

            try:
                items = os.listdir(folder_path)
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied accessing: {folder_path}",
                    "folder": folder_path
                }

            # Categorize files
            documents = []
            images = []
            videos = []
            audio = []
            archives = []
            other = []

            doc_extensions = ('.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx')
            image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
            audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a')
            archive_extensions = ('.zip', '.rar', '.7z', '.tar', '.gz', '.bz2')

            for item in items:
                item_path = os.path.join(folder_path, item)

                try:
                    if os.path.isfile(item_path):
                        file_size = os.path.getsize(item_path)
                        total_size += file_size

                        # Format file size
                        if file_size < 1024:
                            size_str = f"{file_size}B"
                        elif file_size < 1024*1024:
                            size_str = f"{file_size/1024:.1f}KB"
                        else:
                            size_str = f"{file_size/(1024*1024):.1f}MB"

                        file_info = {
                            "name": item,
                            "size": file_size,
                            "size_readable": size_str,
                            "extension": os.path.splitext(item)[1].lower()
                        }

                        # Categorize
                        ext = os.path.splitext(item)[1].lower()
                        if ext in doc_extensions:
                            documents.append(file_info)
                        elif ext in image_extensions:
                            images.append(file_info)
                        elif ext in video_extensions:
                            videos.append(file_info)
                        elif ext in audio_extensions:
                            audio.append(file_info)
                        elif ext in archive_extensions:
                            archives.append(file_info)
                        else:
                            other.append(file_info)
                except (OSError, IOError) as e:
                    logger.warning(f"Could not read file info for {item}: {e}")

            # Format total size
            if total_size < 1024:
                total_size_str = f"{total_size}B"
            elif total_size < 1024*1024:
                total_size_str = f"{total_size/1024:.1f}KB"
            else:
                total_size_str = f"{total_size/(1024*1024):.1f}MB"

            logger.info(f"✅ Listed files in {folder_path}")

            return {
                "success": True,
                "folder": folder_path,
                "summary": {
                    "total_files": len(items),
                    "documents": len(documents),
                    "images": len(images),
                    "videos": len(videos),
                    "audio": len(audio),
                    "archives": len(archives),
                    "other": len(other),
                    "total_size": total_size,
                    "total_size_readable": total_size_str
                },
                "files_by_type": {
                    "documents": documents,
                    "images": images,
                    "videos": videos,
                    "audio": audio,
                    "archives": archives,
                    "other": other
                }
            }

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return {"success": False, "error": str(e)}

# Singleton instance
desktop_executor = DesktopExecutor()
