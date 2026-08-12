"""Album downloading module.

This module provides the `AlbumDownloader` class for downloading image albums from a
given URL. It handles page crawling, image extraction, and downloading with progress
tracking.
"""

import random
import time
import zipfile
from pathlib import Path

import requests
from requests import Response, Session

from src.config import (
    CHUNK_SIZE,
    DOWNLOAD_FOLDER,
    HTTP_RATE_LIMIT,
    RATE_LIMIT_SLEEPING_TIME,
)
from src.crawler.crawler import Crawler
from src.crawler.crawler_utils import get_picture_pages
from src.file_utils import create_download_directory, write_on_session_log
from src.general_utils import fetch_page
from src.managers.live_manager import LiveManager

from .download_utils import fetch_with_retries, prepare_headers


class AlbumDownloader:
    """Handles the process of downloading an image album.

    This class fetches the album's pages, extracts image links, and downloads the images
    while tracking progress.
    """

    def __init__(self, url: str, live_manager: LiveManager) -> None:
        """Initialize the AlbumDownloader with album URL and live manager."""
        self.url = url
        self.live_manager = live_manager
        self.initial_soup = fetch_page(self.url)
        self.crawler = Crawler(
            url=self.url,
            initial_soup=self.initial_soup,
            live_manager=self.live_manager,
        )
        self.album_name = self.crawler.get_album_name()
        self.download_path = create_download_directory(self.album_name)

    def download_album(self) -> None:
        """Download all images from the album while tracking progress."""
        album_pages_soups = self.crawler.collect_album_pages_soups()
        session = requests.Session()
        num_pages = len(album_pages_soups)
        self.live_manager.add_overall_task(
            description=self.album_name,
            num_tasks=num_pages,
        )

        for current_task, soup in enumerate(album_pages_soups):
            containers = soup.find_all("a", {"href": True})
            picture_pages = get_picture_pages(containers)
            reloaded_pages = self.crawler.get_reloaded_pages(picture_pages)

            failed_downloads = self._extract_and_download(
                session, reloaded_pages, current_task,
            )

            if failed_downloads:
                self.live_manager.update_log(
                    "Failed downloads",
                    f"Failed downloads for page {current_task + 1}. "
                    "Check the log file.",
                )

            if current_task < num_pages - 1:
                self.live_manager.update_log(
                    "Preparing to resume",
                    "Pausing before resuming the download...",
                )
                time.sleep(random.uniform(1, 5))  # noqa: S311

        self._create_cbz()

    def _create_cbz(self) -> None:
        """Create a CBZ archive from downloaded images in order."""
        image_files = sorted(
            p for p in Path(self.download_path).glob("*")
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        )
        if not image_files:
            self.live_manager.update_log("CBZ creation", "No images found to archive")
            return

        cbz_name = f"{self.album_name}.cbz"
        cbz_path = Path(DOWNLOAD_FOLDER) / cbz_name

        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as cbz:
            for i, img_path in enumerate(image_files):
                # Use zero-padded index for correct ordering in CBZ
                arcname = f"{i:03d}{img_path.suffix}"
                cbz.write(img_path, arcname)

        self.live_manager.update_log(
            "CBZ created", f"Archive saved to {cbz_path}"
        )

    def download_picture(
            self,
            response: Response,
            filename: str,
            task: int,
        ) -> None:
        """Save an image response to a file and update the progress."""
        final_path = Path(self.download_path) / filename
        with Path(final_path).open("wb") as file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                file.write(chunk)

        self.live_manager.update_task(task, advance=1)

    # Private methods
    def _extract_and_download(
        self,
        session: Session,
        reloaded_pages: list[str],
        current_task: int,
    ) -> list[str]:
        """Extract image links and download them."""
        failed_downloads = []
        num_pictures = len(reloaded_pages)
        task = self.live_manager.add_task(current_task=current_task, total=num_pictures)

        for reloaded_page in reloaded_pages:
            soup = fetch_page(reloaded_page)
            download_link_container = soup.find("img", {"id": "img", "src": True})
            download_link = download_link_container.get("src")
            filename = download_link.split("/")[-1]

            final_path = Path(self.download_path) / filename
            if final_path.is_file():
                self.live_manager.update_task(task, advance=1)
                continue

            headers = prepare_headers(download_link)
            session.headers.update(headers)
            response = fetch_with_retries(session, download_link, self.live_manager)

            if response is None:
                self.live_manager.update_log(
                    "Failed download",
                    f"None response from {download_link}, check the log file",
                )
                failed_downloads.append(download_link)
                write_on_session_log(download_link)
                continue

            if response.status_code == HTTP_RATE_LIMIT:
                self.live_manager.update_log(
                    "Rate limit",
                    "Rate limit hit. Sleeping for a while...",
                )
                time.sleep(RATE_LIMIT_SLEEPING_TIME)

            self.download_picture(response, filename, task)
            time.sleep(random.uniform(1.5, 4.0))  # noqa: S311

        return failed_downloads
