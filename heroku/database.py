# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import collections
import json
import logging
import os
import re
import time
from typing import Any, List, Optional, Union

try:
    import redis
except ImportError as e:
    if "RAILWAY" in os.environ:
        raise e

from herokutl.errors.rpcerrorlist import ChannelsTooMuchError
from herokutl.tl.types import Message, User, ForumTopic

from . import main, utils
from .pointers import (
    BaseSerializingMiddlewareDict,
    BaseSerializingMiddlewareList,
    NamedTupleMiddlewareDict,
    NamedTupleMiddlewareList,
    PointerDict,
    PointerList,
)
from .tl_cache import CustomTelegramClient
from .types import JSONSerializable

__all__ = [
    "Database",
    "PointerList",
    "PointerDict",
    "NamedTupleMiddlewareDict",
    "NamedTupleMiddlewareList",
    "BaseSerializingMiddlewareDict",
    "BaseSerializingMiddlewareList",
]

logger = logging.getLogger(__name__)


class NoAssetsChannel(Exception):
    """Raised when trying to read/store asset with no asset channel present"""


class Database(dict):
    def __init__(self, client: CustomTelegramClient) -> None:
        super().__init__()
        self._client: CustomTelegramClient = client
        self._next_revision_call: int = 0
        self._revisions: List[dict] = []
        self._assets_topic: Optional[ForumTopic] = None
        self._me: User = None
        self._redis: redis.Redis = None
        self._saving_task: asyncio.Future = None

    def __repr__(self) -> str:
        return object.__repr__(self)

    def _redis_save_sync(self) -> None:
        with self._redis.pipeline() as pipe:
            pipe.set(
                str(self._client.tg_id),
                json.dumps(self, ensure_ascii=True),
            )
            pipe.execute()

    async def remote_force_save(self) -> bool:
        """Force save database to remote endpoint without waiting"""
        match self._redis:
            case None:
                return False
            case _:
                await utils.run_sync(self._redis_save_sync)
                logger.debug("Published db to Redis")
                return True

    async def _redis_save(self) -> bool:
        """Save database to redis"""
        match self._redis:
            case None:
                return False
            case _:
                await asyncio.sleep(5)
                await utils.run_sync(self._redis_save_sync)
                logger.debug("Published db to Redis")
                self._saving_task = None
                return True

    async def redis_init(self) -> bool:
        """Init redis database"""
        match REDIS_URI := (
            os.environ.get("REDIS_URL") or main.get_config_key("redis_uri")
        ):
            case None:
                return False
            case _:
                self._redis = redis.Redis.from_url(REDIS_URI)
                return True

    async def init(self) -> None:
        """Asynchronous initialization unit"""
        match os.environ.get("REDIS_URL") or main.get_config_key("redis_uri"):
            case None:
                pass
            case _:
                await self.redis_init()

        self._db_file = main.BASE_PATH / f"config-{self._client.tg_id}.json"
        self.read()

        try:
            self._content_channel_id = self.get("heroku.forums", "channel_id", None)

            if not self._content_channel_id:
                raise KeyError("Heroku content channel not found in database")

            self._assets_topic = await utils.asset_forum_topic(
                client=self._client,
                db=self,
                peer=self._content_channel_id,
                title="Assets",
                description="🌆 Your Heroku assets will be stored here",
                icon_emoji_id=5877307202888273539,
            )

        except Exception:
            self._assets_topic = None
            logger.error(
                "Can't find and/or create assets topic\n"
                "This may cause several consequences, such as:\n"
                "- Non working assets feature (e.g. notes)\n"
                "- This error will occur every restart\n\n"
                "You can solve this by leaving some channels/groups"
            )

    def read(self) -> None:
        """Read database and stores it in self"""
        match self._redis:
            case None:
                pass
            case _:
                try:
                    self.update(
                        **json.loads(
                            self._redis.get(
                                str(self._client.tg_id),
                            ).decode(),
                        )
                    )
                except Exception:
                    logger.exception("Error reading redis database")
                return

        try:
            db = self._db_file.read_text()
            match re.search(r'"(hikka\.)(\S+":)', db):
                case None:
                    pass
                case _:
                    logging.warning("Converting db after update")
                    db = re.sub(r'(hikka\.)(\S+":)', lambda m: 'heroku.' + m.group(2), db)
            
            match re.search(r'"(legacy\.)(\S+":)', db):
                case None:
                    pass
                case _:
                    logging.warning("Converting db after update")
                    db = re.sub(r'(legacy\.)(\S+":)', lambda m: 'heroku.' + m.group(2), db)
            
            self.update(**json.loads(db))
        except json.decoder.JSONDecodeError:
            logger.warning("Database read failed! Creating new one...")
        except FileNotFoundError:
            logger.debug("Database file not found, creating new one...")

    def process_db_autofix(self, db: dict) -> bool:
        match utils.is_serializable(db):
            case False:
                return False
            case True:
                pass

        for key, value in db.copy().items():
            match isinstance(key, (str, int)):
                case False:
                    logger.warning(
                        "DbAutoFix: Dropped key %s, because it is not string or int",
                        key,
                    )
                    continue
                case True:
                    pass

            match isinstance(value, dict):
                case False:
                    # If value is not a dict (module values), drop it,
                    # otherwise it may cause problems
                    del db[key]
                    logger.warning(
                        "DbAutoFix: Dropped key %s, because it is non-dict, but %s",
                        key,
                        type(value),
                    )
                    continue
                case True:
                    pass

            for subkey in value:
                match isinstance(subkey, (str, int)):
                    case False:
                        del db[key][subkey]
                        logger.warning(
                            (
                                "DbAutoFix: Dropped subkey %s of db key %s, because it is"
                                " not string or int"
                            ),
                            subkey,
                            key,
                        )
                        continue
                    case True:
                        pass

        return True

    def save(self) -> bool:
        """Save database"""
        match self.process_db_autofix(self):
            case False:
                try:
                    rev = self._revisions.pop()
                    while not self.process_db_autofix(rev):
                        rev = self._revisions.pop()
                except IndexError:
                    raise RuntimeError(
                        "Can't find revision to restore broken database from "
                        "database is most likely broken and will lead to problems, "
                        "so its save is forbidden."
                    )

                self.clear()
                self.update(**rev)

                raise RuntimeError(
                    "Rewriting database to last revision because new one destructed it"
                )
            case True:
                pass

        if self._next_revision_call < time.time():
            self._revisions += [dict(self)]
            self._next_revision_call = time.time() + 3

        while len(self._revisions) > 15:
            self._revisions.pop()

        match self._redis:
            case None:
                pass
            case _:
                match self._saving_task:
                    case None:
                        self._saving_task = asyncio.ensure_future(self._redis_save())
                    case _:
                        pass
                return True

        try:
            self._db_file.write_text(json.dumps(self, indent=4))
        except Exception:
            logger.exception("Database save failed!")
            return False

        return True

    async def store_asset(self, message: Message) -> int:
        """
        Save assets
        returns asset_id as integer
        """
        match self._assets_topic:
            case None:
                raise NoAssetsChannel("Tried to save asset to non-existing asset topic")
            case _:
                pass

        match isinstance(message, Message):
            case True:
                return (await self._client.send_message(self._content_channel_id, message, reply_to=self._assets_topic.id)).id
            case False:
                return (
                    await self._client.send_message(
                        self._content_channel_id,
                        file=message,
                        force_document=True,
                        message_thread_id=self._assets_topic.id
                    )
                ).id

    async def fetch_asset(self, asset_id: int) -> Optional[Message]:
        """Fetch previously saved asset by its asset_id"""
        match self._assets_topic:
            case None:
                raise NoAssetsChannel(
                    "Tried to fetch asset from non-existing asset topic"
                )
            case _:
                pass

        asset = await self._client.get_messages(self._content_channel_id, ids=[asset_id])

        return asset[0] if asset else None

    def get(
        self,
        owner: str,
        key: str,
        default: Optional[JSONSerializable] = None,
    ) -> JSONSerializable:
        """Get database key"""
        try:
            return self[owner][key]
        except KeyError:
            return default

    def set(self, owner: str, key: str, value: JSONSerializable) -> bool:
        """Set database key"""
        match utils.is_serializable(owner):
            case False:
                raise RuntimeError(
                    "Attempted to write object to "
                    f"{owner=} ({type(owner)=}) of database. It is not "
                    "JSON-serializable key which will cause errors"
                )
            case True:
                pass

        match utils.is_serializable(key):
            case False:
                raise RuntimeError(
                    "Attempted to write object to "
                    f"{key=} ({type(key)=}) of database. It is not "
                    "JSON-serializable key which will cause errors"
                )
            case True:
                pass

        match utils.is_serializable(value):
            case False:
                raise RuntimeError(
                    "Attempted to write object of "
                    f"{key=} ({type(value)=}) to database. It is not "
                    "JSON-serializable value which will cause errors"
                )
            case True:
                pass

        super().setdefault(owner, {})[key] = value
        return self.save()

    def pointer(
        self,
        owner: str,
        key: str,
        default: Optional[JSONSerializable] = None,
        item_type: Optional[Any] = None,
    ) -> Union[JSONSerializable, PointerList, PointerDict]:
        """Get a pointer to database key"""
        value = self.get(owner, key, default)
        mapping = {
            list: PointerList,
            dict: PointerDict,
            collections.abc.Hashable: lambda v: v,
        }

        pointer_constructor = next(
            (pointer for type_, pointer in mapping.items() if isinstance(value, type_)),
            None,
        )

        current_value = self.get(owner, key, None)
        match current_value and type(current_value) is not type(default):
            case True:
                raise ValueError(
                    f"Can't switch type of pointer in database (current: {type(current_value)}, requested: {type(default)})"
                )
            case False:
                pass

        match pointer_constructor:
            case None:
                raise ValueError(
                    f"Pointer for type {type(value).__name__} is not implemented"
                )
            case _:
                pass

        match item_type:
            case None:
                return pointer_constructor(self, owner, key, default)
            case _:
                match isinstance(value, list):
                    case True:
                        for item in self.get(owner, key, default):
                            match isinstance(item, dict):
                                case False:
                                    raise ValueError(
                                        "Item type can only be specified for dedicated keys and"
                                        " can't be mixed with other ones"
                                    )
                                case True:
                                    pass

                        return NamedTupleMiddlewareList(
                            pointer_constructor(self, owner, key, default),
                            item_type,
                        )
                    case False:
                        match isinstance(value, dict):
                            case True:
                                for item in self.get(owner, key, default).values():
                                    match isinstance(item, dict):
                                        case False:
                                            raise ValueError(
                                                "Item type can only be specified for dedicated keys and"
                                                " can't be mixed with other ones"
                                            )
                                        case True:
                                            pass

                                return NamedTupleMiddlewareDict(
                                    pointer_constructor(self, owner, key, default),
                                    item_type,
                                )
                            case False:
                                pass