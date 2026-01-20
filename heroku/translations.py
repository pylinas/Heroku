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

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

import requests
from ruamel.yaml import YAML

from . import utils
from .database import Database
from .tl_cache import CustomTelegramClient
from .types import Module

logger = logging.getLogger(__name__)
yaml = YAML(typ="safe")

PACKS = Path(__file__).parent / "langpacks"
SUPPORTED_LANGUAGES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "ua": "🇺🇦 Український",
    "de": "🇩🇪 Deutsch",
    "jp": "🇯🇵 日本語",
    "fr": "🇫🇷 Français",
}
MEME_LANGUAGES = {
    "leet": "🏴‍☠️ 1337",
    "uwu": "🏴‍☠️ UwU",
    "tiktok": "🏴‍☠️ TikTokKid",
}


def fmt(text: str, kwargs: dict) -> str:
    for key, value in kwargs.items():
        match f"{{{key}}}" in text:
            case True:
                text = text.replace(f"{{{key}}}", str(value))
            case False:
                pass

    return text


class BaseTranslator:
    def _get_pack_content(
        self,
        pack: Path,
        prefix: str = "heroku.modules.",
    ) -> Optional[dict]:
        return self._get_pack_raw(pack.read_text(encoding="utf-8"), pack.suffix, prefix)

    def _get_pack_raw(
        self,
        content: str,
        suffix: str,
        prefix: str = "heroku.modules.",
    ) -> Optional[dict]:
        match suffix:
            case ".json":
                return json.loads(content)
            case _:
                content = yaml.load(content)

        match all(len(key) == 2 for key in content):
            case True:
                return {
                    language: {
                        (
                            f"{module.strip('$')}.{key}"
                            if module.startswith("$")
                            else f"{prefix}{module}.{key}"
                        ): value
                        for module, strings in pack.items()
                        for key, value in strings.items()
                        if key != "name"
                    }
                    for language, pack in content.items()
                }
            case False:
                return {
                    (
                        f"{module.strip('$')}.{key}"
                        if module.startswith("$")
                        else f"{prefix}{module}.{key}"
                    ): value
                    for module, strings in content.items()
                    for key, value in strings.items()
                    if key != "name"
                }

    def getkey(self, key: str) -> Any:
        return self._data.get(key, False)

    def gettext(self, text: str) -> Any:
        return self.getkey(text) or text

    async def load_module_translations(self, pack_url: str) -> Union[bool, dict]:
        try:
            data = yaml.load((await utils.run_sync(requests.get, pack_url)).text)
        except Exception:
            logger.exception("Unable to decode %s", pack_url)
            return False

        match isinstance(data, dict):
            case False:
                return {}
            case True:
                pass

        match any(len(key) != 2 for key in data):
            case True:
                return data
            case False:
                pass

        match lang := self.db.get(__name__, "lang", False):
            case None:
                return data.get("en", {})
            case _:
                return next(
                    (data[language] for language in lang.split() if language in data),
                    data.get("en", {}),
                )


class Translator(BaseTranslator):
    def __init__(self, client: CustomTelegramClient, db: Database) -> None:
        self._client = client
        self.db = db
        self._data = {}
        self.raw_data = {}

    async def init(self) -> bool:
        self._data = self._get_pack_content(PACKS / "en.yml")
        self.raw_data["en"] = self._data.copy()
        any_ = False
        match lang := self.db.get(__name__, "lang", False):
            case None:
                pass
            case _:
                for language in lang.split():
                    match utils.check_url(language):
                        case True:
                            try:
                                data = self._get_pack_raw(
                                    (await utils.run_sync(requests.get, language)).text,
                                    language.split(".")[-1],
                                )
                            except Exception:
                                logger.exception("Unable to decode %s", language)
                                continue

                            self._data.update(data)
                            self.raw_data[language] = data
                            any_ = True
                            continue
                        case False:
                            pass

                    for possible_path in [
                        PACKS / f"{language}.json",
                        PACKS / f"{language}.yml",
                    ]:
                        match possible_path.exists():
                            case True:
                                data = self._get_pack_content(possible_path)
                                self._data.update(data)
                                self.raw_data[language] = data
                                any_ = True
                            case False:
                                pass

        for language in SUPPORTED_LANGUAGES:
            match language not in self.raw_data and (PACKS / f"{language}.yml").exists():
                case True:
                    self.raw_data[language] = self._get_pack_content(
                        PACKS / f"{language}.yml"
                    )
                case False:
                    pass

        return any_


class ExternalTranslator(BaseTranslator):
    def __init__(self) -> None:
        self.data = {}
        for lang in SUPPORTED_LANGUAGES:
            self.data[lang] = self._get_pack_content(PACKS / f"{lang}.yml", prefix="")

    def get(self, key: str, lang: str) -> str:
        return self.data[lang].get(key, False) or key

    def getdict(self, key: str, **kwargs) -> dict:
        return {
            lang: fmt(self.data[lang].get(key, False) or key, kwargs)
            for lang in self.data
        }


class Strings:
    def __init__(self, mod: Module, translator: Translator) -> None:  # skipcq: PYL-W0621
        self._mod = mod
        self._translator = translator

        match translator:
            case None:
                logger.debug("Module %s got empty translator %s", mod, translator)
            case _:
                pass

        self._base_strings = mod.strings  # Back 'em up, bc they will get replaced
        self.external_strings = {}

    def get(self, key: str, lang: Optional[str] = None) -> str:
        try:
            return self._translator.raw_data[lang][f"{self._mod.__module__}.{key}"]
        except KeyError:
            return self[key]

    def __getitem__(self, key: str) -> str:
        return (
            self.external_strings.get(key, None)
            or (
                self._translator.getkey(f"{self._mod.__module__}.{key}")
                if self._translator is not None
                else False
            )
            or (
                getattr(
                    self._mod,
                    next(
                        (
                            f"strings_{lang}"
                            for original_lang in (self._translator.db.get(
                                __name__,
                                "lang",
                                "en",
                            ).split(" ") if self._translator is not None else ["en"])
                            for lang in (
                                [original_lang] + 
                                (["en"] if original_lang in ["leet", "uwu"] else 
                                 ["ru"] if original_lang == "tiktok" else [])
                            )
                            if hasattr(self._mod, f"strings_{lang}")
                            and isinstance(getattr(self._mod, f"strings_{lang}"), dict)
                            and key in getattr(self._mod, f"strings_{lang}")
                        ),
                        utils.rand(32),
                    ),
                    self._base_strings,
                ).get(key)
                if self._translator is not None
                else self._base_strings.get(key)
            )
            or self._base_strings.get(key, "Unknown strings")
        )

    def __call__(
        self,
        key: str,
        _: Optional[Any] = None,  # Compatibility tweak for FTG\GeekTG
    ) -> str:
        return self.__getitem__(key)

    def __iter__(self):
        return self._base_strings.__iter__()


translator = ExternalTranslator()
