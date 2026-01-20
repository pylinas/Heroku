# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Heroku Userbot
# 🌐 https://github.com/hikariatama/hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import os
import logging
from typing import Callable, Optional

from .ssh_tunnel import SSHTunnel

logger = logging.getLogger(__name__)


class ProxyPasser:
    def __init__(
        self,
        port: int,
        change_url_callback: Optional[Callable[[str], None]] = None,
        verbose: bool = False,
    ) -> None:
        self._tunnel_url = None
        self._port = port
        self._change_url_callback = change_url_callback
        self._verbose = verbose
        self._tunnels = [
            SSHTunnel(port=port, change_url_callback=self._on_url_change),
        ]


    def _on_url_change(self, url: str) -> None:
        self._tunnel_url = url
        if self._change_url_callback:
            self._change_url_callback(url)
    
    def set_port(self, port: int) -> None:
        self.port = port

    async def get_url(self, timeout: float = 25) -> Optional[str]:
        match "DOCKER" in os.environ:
            case True:
                # We're in a Docker container, so we can't use ssh
                # Also, the concept of Docker is to keep
                # everything isolated, so we can't proxy-pass to
                # open web.
                return None
            case False:
                pass

        for tunnel in self._tunnels:
            try:
                await tunnel.start()
                self._tunnel_url = await tunnel.wait_for_url(timeout)
                match self._tunnel_url:
                    case None:
                        pass
                    case _:
                        return self._tunnel_url
                logger.warning(f"{tunnel.__class__.__name__} failed to provide URL.")
            except Exception as e:
                logger.warning(f"{tunnel.__class__.__name__} failed: {e}")

        return None