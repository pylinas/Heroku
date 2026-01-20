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

import functools
import re
from typing import Any, Callable, List, Optional, Union

import grapheme
from emoji import get_emoji_unicode_dict

from . import utils
from .translations import SUPPORTED_LANGUAGES, translator

ConfigAllowedTypes = Union[tuple, list, str, int, bool, None]

ALLOWED_EMOJIS = set(get_emoji_unicode_dict("en").values())


class ValidationError(Exception):
    """
    Is being raised when config value passed can't be converted properly
    Must be raised with string, describing why value is incorrect
    It will be shown in .config, if user tries to set incorrect value
    """


class Validator:
    """
    Class used as validator of config value
    :param validator: Sync function, which raises `ValidationError` if passed
                      value is incorrect (with explanation) and returns converted
                      value if it is semantically correct.
                      ⚠️ If validator returns `None`, value will always be set to `None`
    :param doc: Docstrings for this validator as string, or dict in format:
                {
                    "en": "docstring",
                    "ru": "докстрингом",
                    "ua": "докстрінгом",
                    "de": "Dokumentation",
                }
                Use instrumental case with lowercase
    :param _internal_id: Do not pass anything here, or things will break
    """

    def __init__(
        self,
        validator: Callable,
        doc: Optional[Union[str, dict]] = None,
        _internal_id: Optional[int] = None,
    ) -> None:
        self.validate = validator

        match isinstance(doc, str):
            case True:
                doc = {lang: doc for lang in SUPPORTED_LANGUAGES}
            case False:
                pass

        self.doc = doc
        self.internal_id = _internal_id


class Boolean(Validator):
    """
    Any logical value to be passed
    `1`, `"1"` etc. will be automatically converted to bool
    """

    _TRUE_VALUES = frozenset(
        ("True", "true", "1", 1, True, "yes", "Yes", "on", "On", "y", "Y")
    )
    _FALSE_VALUES = frozenset(
        ("False", "false", "0", 0, False, "no", "No", "off", "Off", "n", "N")
    )
    _ALL_VALUES = _TRUE_VALUES | _FALSE_VALUES

    def __init__(self) -> None:
        super().__init__(
            self._validate,
            translator.getdict("validators.boolean"),
            _internal_id="Boolean",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> bool:
        match value not in Boolean._ALL_VALUES:
            case True:
                raise ValidationError("Passed value must be a boolean")
            case False:
                pass

        return value in Boolean._TRUE_VALUES


class Integer(Validator):
    """
    Checks whether passed argument is an integer value
    :param digits: Digits quantity, which must be passed
    :param minimum: Minimal number to be passed
    :param maximum: Maximum number to be passed
    """

    def __init__(
        self,
        *,
        digits: Optional[int] = None,
        minimum: Optional[int] = None,
        maximum: Optional[int] = None,
    ) -> None:
        _signs = (
            translator.getdict("validators.positive")
            if minimum is not None and minimum == 0
            else (
                translator.getdict("validators.negative")
                if maximum is not None and maximum == 0
                else {}
            )
        )
        _digits = (
            translator.getdict("validators.digits", digits=digits)
            if digits is not None
            else {}
        )

        match True:
            case _ if minimum is not None and minimum != 0:
                doc = (
                    {
                        lang: text.format(
                            sign=_signs.get(lang, ""),
                            digits=_digits.get(lang, ""),
                            minimum=minimum,
                        )
                        for lang, text in translator.getdict(
                            "validators.integer_min"
                        ).items()
                    }
                    if maximum is None and maximum != 0
                    else {
                        lang: text.format(
                            sign=_signs.get(lang, ""),
                            digits=_digits.get(lang, ""),
                            minimum=minimum,
                            maximum=maximum,
                        )
                        for lang, text in translator.getdict(
                            "validators.integer_range"
                        ).items()
                    }
                )
            case _ if maximum is None and maximum != 0:
                doc = {
                    lang: text.format(
                        sign=_signs.get(lang, ""), digits=_digits.get(lang, "")
                    )
                    for lang, text in translator.getdict("validators.integer").items()
                }
            case _:
                doc = {
                    lang: text.format(
                        sign=_signs.get(lang, ""),
                        digits=_digits.get(lang, ""),
                        maximum=maximum,
                    )
                    for lang, text in translator.getdict(
                        "validators.integer_max"
                    ).items()
                }

        super().__init__(
            functools.partial(
                self._validate,
                digits=digits,
                minimum=minimum,
                maximum=maximum,
            ),
            doc,
            _internal_id="Integer",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        digits: int,
        minimum: int,
        maximum: int,
    ) -> Union[int, None]:
        try:
            value = int(str(value).strip())
        except ValueError:
            raise ValidationError(f"Passed value ({value}) must be a number")

        match minimum is not None and value < minimum:
            case True:
                raise ValidationError(f"Passed value ({value}) is lower than minimum one")
            case False:
                pass

        match maximum is not None and value > maximum:
            case True:
                raise ValidationError(f"Passed value ({value}) is greater than maximum one")
            case False:
                pass

        match digits is not None and len(str(value)) != digits:
            case True:
                raise ValidationError(
                    f"The length of passed value ({value}) is incorrect "
                    f"(Must be exactly {digits} digits)"
                )
            case False:
                pass

        return value

class Choice(Validator):
    """
    Check whether entered value is in the allowed list
    :param possible_values: Allowed values to be passed to config param
    """

    def __init__(
        self,
        possible_values: List[ConfigAllowedTypes],
        /,
    ) -> None:
        super().__init__(
            functools.partial(self._validate, possible_values=possible_values),
            translator.getdict(
                "validators.choice",
                possible=" / ".join(list(map(str, possible_values))),
            ),
            _internal_id="Choice",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        possible_values: List[ConfigAllowedTypes],
    ) -> ConfigAllowedTypes:
        match value not in possible_values:
            case True:
                raise ValidationError(
                    f"Passed value ({value}) is not one of the following:"
                    f" {' / '.join(list(map(str, possible_values)))}"
                )
            case False:
                pass

        return value


class MultiChoice(Validator):
    """
    Check whether every entered value is in the allowed list
    :param possible_values: Allowed values to be passed to config param
    """

    def __init__(
        self,
        possible_values: List[ConfigAllowedTypes],
        /,
    ):
        possible = " / ".join(list(map(str, possible_values)))
        super().__init__(
            functools.partial(self._validate, possible_values=possible_values),
            translator.getdict("validators.multichoice", possible=possible),
            _internal_id="MultiChoice",
        )

    @staticmethod
    def _validate(
        value: List[ConfigAllowedTypes],
        /,
        *,
        possible_values: List[ConfigAllowedTypes],
    ) -> List[ConfigAllowedTypes]:
        match not isinstance(value, (list, tuple)):
            case True:
                value = [value]
            case False:
                pass

        for item in value:
            match item not in possible_values:
                case True:
                    raise ValidationError(
                        f"One of passed values ({item}) is not one of the following:"
                        f" {' / '.join(list(map(str, possible_values)))}"
                    )
                case False:
                    pass

        return list(set(value))


class Series(Validator):
    """
    Represents the series of value (simply `list`)
    :param separator: With which separator values must be separated
    :param validator: Internal validator for each sequence value
    :param min_len: Minimal number of series items to be passed
    :param max_len: Maximum number of series items to be passed
    :param fixed_len: Fixed number of series items to be passed
    """

    def __init__(
        self,
        validator: Optional[Validator] = None,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
        fixed_len: Optional[int] = None,
    ) -> None:
        def trans(lang: str) -> str:
            return validator.doc.get(lang, validator.doc["en"])

        _each = (
            {
                lang: text.format(each=trans(lang))
                for lang, text in translator.getdict("validators.each").items()
            }
            if validator is not None
            else {}
        )

        match True:
            case _ if fixed_len is not None:
                _len = translator.getdict("validators.fixed_len", fixed_len=fixed_len)
            case _ if min_len is None:
                match max_len is None:
                    case True:
                        _len = {}
                    case False:
                        _len = translator.getdict("validators.max_len", max_len=max_len)
            case _ if max_len is not None:
                _len = translator.getdict(
                    "validators.len_range", min_len=min_len, max_len=max_len
                )
            case _:
                _len = translator.getdict("validators.min_len", min_len=min_len)

        super().__init__(
            functools.partial(
                self._validate,
                validator=validator,
                min_len=min_len,
                max_len=max_len,
                fixed_len=fixed_len,
            ),
            {
                lang: text.format(each=_each.get(lang, ""), len=_len.get(lang, ""))
                for lang, text in translator.getdict("validators.series").items()
            },
            _internal_id="Series",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        validator: Optional[Validator] = None,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
        fixed_len: Optional[int] = None,
    ) -> List[ConfigAllowedTypes]:
        match not isinstance(value, (list, tuple, set)):
            case True:
                value = str(value).split(",")
            case False:
                pass

        match isinstance(value, (tuple, set)):
            case True:
                value = list(value)
            case False:
                pass

        match min_len is not None and len(value) < min_len:
            case True:
                raise ValidationError(
                    f"Passed value ({value}) contains less than {min_len} items"
                )
            case False:
                pass

        match max_len is not None and len(value) > max_len:
            case True:
                raise ValidationError(
                    f"Passed value ({value}) contains more than {max_len} items"
                )
            case False:
                pass

        match fixed_len is not None and len(value) != fixed_len:
            case True:
                raise ValidationError(
                    f"Passed value ({value}) must contain exactly {fixed_len} items"
                )
            case False:
                pass

        value = [item.strip() if isinstance(item, str) else item for item in value]

        match isinstance(validator, Validator):
            case True:
                for i, item in enumerate(value):
                    try:
                        value[i] = validator.validate(item)
                    except ValidationError:
                        raise ValidationError(
                            f"Passed value ({value}) contains invalid item"
                            f" ({str(item).strip()}), which must be {validator.doc['en']}"
                        )
            case False:
                pass

        value = list(filter(lambda x: x, value))

        return value


class Link(Validator):
    """Valid url must be specified"""

    def __init__(self):
        super().__init__(
            lambda value: self._validate(value),
            translator.getdict("validators.link"),
            _internal_id="Link",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> str:
        try:
            if not utils.check_url(value):
                raise Exception("Invalid URL")
        except Exception:
            raise ValidationError(f"Passed value ({value}) is not a valid URL")

        return value


class String(Validator):
    """
    Checks for length of passed value and automatically converts it to string
    :param length: Exact length of string
    :param min_len: Minimal length of string
    :param max_len: Maximum length of string
    """

    def __init__(
        self,
        length: Optional[int] = None,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
    ):
        if length is not None:
            doc = translator.getdict("validators.string_fixed_len", length=length)
        else:
            match True:
                case _ if min_len is None:
                    if max_len is None:
                        doc = translator.getdict("validators.string")
                    else:
                        doc = translator.getdict(
                            "validators.string_max_len", max_len=max_len
                        )
                case _ if max_len is not None:
                    doc = translator.getdict(
                        "validators.string_len_range", min_len=min_len, max_len=max_len
                    )
                case _:
                    doc = translator.getdict(
                        "validators.string_min_len", min_len=min_len
                    )

        super().__init__(
            functools.partial(
                self._validate,
                length=length,
                min_len=min_len,
                max_len=max_len,
            ),
            doc,
            _internal_id="String",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        length: Optional[int],
        min_len: Optional[int],
        max_len: Optional[int],
    ) -> str:
        if (
            isinstance(length, int)
            and len(list(grapheme.graphemes(str(value)))) != length
        ):
            raise ValidationError(
                f"Passed value ({value}) must be a length of {length}"
            )

        if (
            isinstance(min_len, int)
            and len(list(grapheme.graphemes(str(value)))) < min_len
        ):
            raise ValidationError(
                f"Passed value ({value}) must be a length of at least {min_len}"
            )

        if (
            isinstance(max_len, int)
            and len(list(grapheme.graphemes(str(value)))) > max_len
        ):
            raise ValidationError(
                f"Passed value ({value}) must be a length of up to {max_len}"
            )

        return str(value)


class RegExp(Validator):
    """
    Checks if value matches the regex
    :param regex: Regex to match
    :param flags: Flags to pass to re.compile
    :param description: Description of regex
    """

    def __init__(
        self,
        regex: str,
        flags: Optional[re.RegexFlag] = None,
        description: Optional[Union[dict, str]] = None,
    ) -> None:
        match flags:
            case None:
                flags = 0
            case _:
                pass

        try:
            re.compile(regex, flags=flags)
        except re.error as e:
            raise Exception(f"{regex} is not a valid regex") from e

        match description:
            case None:
                doc = translator.getdict("validators.regex", regex=regex)
            case _:
                match isinstance(description, str):
                    case True:
                        doc = {"en": description}
                    case False:
                        doc = description

        super().__init__(
            functools.partial(self._validate, regex=regex, flags=flags),
            doc,
            _internal_id="RegExp",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        regex: str,
        flags: Optional[re.RegexFlag],
    ) -> str:
        match not re.match(regex, str(value), flags=flags):
            case True:
                raise ValidationError(f"Passed value ({value}) must follow pattern {regex}")
            case False:
                pass

        return str(value)


class Float(Validator):
    """
    Checks whether passed argument is a float value
    :param minimum: Minimal number to be passed
    :param maximum: Maximum number to be passed
    """

    def __init__(
        self,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> None:
        _signs = (
            translator.getdict("validators.positive")
            if minimum is not None and minimum == 0
            else (
                translator.getdict("validators.negative")
                if maximum is not None and maximum == 0
                else {}
            )
        )

        match minimum is not None and minimum != 0:
            case True:
                doc = (
                    {
                        lang: text.format(
                            sign=_signs.get(lang, ""),
                            minimum=minimum,
                        )
                        for lang, text in translator.getdict("validators.float_min").items()
                    }
                    if maximum is None and maximum != 0
                    else {
                        lang: text.format(
                            sign=_signs.get(lang, ""),
                            minimum=minimum,
                            maximum=maximum,
                        )
                        for lang, text in translator.getdict(
                            "validators.float_range"
                        ).items()
                    }
                )
            case False:
                pass

        match maximum is None and maximum != 0:
            case True:
                doc = {
                    lang: text.format(
                        sign=_signs.get(lang, ""),
                        minimum=minimum,
                    )
                    for lang, text in translator.getdict("validators.float").items()
                }
            case False:
                pass

        match maximum is None and maximum != 0:
            case True:
                doc = {
                    lang: text.format(
                        sign=_signs.get(lang, ""),
                        maximum=maximum,
                    )
                    for lang, text in translator.getdict("validators.float_max").items()
                }
            case False:
                pass

        super().__init__(
            functools.partial(
                self._validate,
                minimum=minimum,
                maximum=maximum,
            ),
            doc,
            _internal_id="Float",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None,
    ) -> float:
        try:
            value = float(str(value).strip().replace(",", "."))
        except ValueError:
            raise ValidationError(f"Passed value ({value}) must be a float")

        match minimum is not None and value < minimum:
            case True:
                raise ValidationError(f"Passed value ({value}) is lower than minimum one")
            case False:
                pass

        match maximum is not None and value > maximum:
            case True:
                raise ValidationError(f"Passed value ({value}) is greater than maximum one")
            case False:
                pass

        return value


class TelegramID(Validator):
    def __init__(self):
        super().__init__(
            self._validate,
            "Telegram ID",
            _internal_id="TelegramID",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> int:
        e = ValidationError(f"Passed value ({value}) is not a valid telegram id")

        try:
            value = int(str(value).strip())
        except Exception:
            raise e

        if str(value).startswith("-100"):
            value = int(str(value)[4:])

        if value > 2**64 - 1 or value < 0:
            raise e

        return value


class Union(Validator):
    def __init__(self, *validators):
        doc = translator.getdict("validators.union")

        def case(x: str) -> str:
            return x[0].upper() + x[1:]

        for validator in validators:
            for key in doc:
                doc[key] += f"- {case(validator.doc.get(key, validator.doc['en']))}\n"

        for key, value in doc.items():
            doc[key] = value.strip()

        super().__init__(
            functools.partial(self._validate, validators=validators),
            doc,
            _internal_id="Union",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        validators: list,
    ) -> ConfigAllowedTypes:
        for validator in validators:
            try:
                return validator.validate(value)
            except ValidationError:
                pass

        raise ValidationError(f"Passed value ({value}) is not valid")


class NoneType(Validator):
    def __init__(self):
        super().__init__(
            self._validate,
            translator.getdict("validators.empty"),
            _internal_id="NoneType",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> None:
        if not value:
            raise ValidationError(f"Passed value ({value}) is not None")

        return None


class Hidden(Validator):
    def __init__(self, validator: Optional[Validator] = None) -> None:
        match validator:
            case None:
                validator = String()
            case _:
                pass

        super().__init__(
            functools.partial(self._validate, validator=validator),
            validator.doc,
            _internal_id="Hidden",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        validator: Validator,
    ) -> ConfigAllowedTypes:
        return validator.validate(value)


class Emoji(Validator):
    """
    Checks whether passed argument is a valid emoji
    :param quantity: Number of emojis to be passed
    :param min_len: Minimum number of emojis
    :param max_len: Maximum number of emojis
    """

    def __init__(
        self,
        length: Optional[int] = None,
        min_len: Optional[int] = None,
        max_len: Optional[int] = None,
    ) -> None:
        match True:
            case _ if length is not None:
                doc = translator.getdict("validators.emoji_fixed_len", length=length)
            case _ if min_len is not None and max_len is not None:
                doc = translator.getdict(
                    "validators.emoji_len_range", min_len=min_len, max_len=max_len
                )
            case _ if min_len is not None:
                doc = translator.getdict("validators.emoji_min_len", min_len=min_len)
            case _ if max_len is not None:
                doc = translator.getdict("validators.emoji_max_len", max_len=max_len)
            case _:
                doc = translator.getdict("validators.emoji")

        super().__init__(
            functools.partial(
                self._validate,
                length=length,
                min_len=min_len,
                max_len=max_len,
            ),
            doc,
            _internal_id="Emoji",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        length: Optional[int],
        min_len: Optional[int],
        max_len: Optional[int],
    ) -> str:
        value = str(value)
        passed_length = len(list(grapheme.graphemes(value)))

        match length is not None and passed_length != length:
            case True:
                raise ValidationError(f"Passed value ({value}) is not {length} emojis long")
            case False:
                pass

        match (
            min_len is not None
            and max_len is not None
            and (passed_length < min_len or passed_length > max_len)
        ):
            case True:
                raise ValidationError(
                    f"Passed value ({value}) is not between {min_len} and {max_len} emojis"
                    " long"
                )
            case False:
                pass

        match min_len is not None and passed_length < min_len:
            case True:
                raise ValidationError(
                    f"Passed value ({value}) is not at least {min_len} emojis long"
                )
            case False:
                pass

        match max_len is not None and passed_length > max_len:
            case True:
                raise ValidationError(
                    f"Passed value ({value}) is not no more than {max_len} emojis long"
                )
            case False:
                pass

        match any(emoji not in ALLOWED_EMOJIS for emoji in grapheme.graphemes(value)):
            case True:
                raise ValidationError(
                    f"Passed value ({value}) is not a valid string with emojis"
                )
            case False:
                pass

        return value


class EntityLike(RegExp):
    def __init__(self):
        super().__init__(
            regex=r"^(?:@|https?://t\.me/)?(?:[a-zA-Z0-9_]{5,32}|[a-zA-Z0-9_]{1,32}\?[a-zA-Z0-9_]{1,32})$",
            description=translator.getdict("validators.entity_like"),
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        regex: str,
        flags: Optional[re.RegexFlag],
    ) -> Union[str, int]:
        value = super()._validate(value, regex=regex, flags=flags)

        match value.isdigit():
            case True:
                match value.startswith("-100"):
                    case True:
                        value = value[4:]
                    case False:
                        pass
                value = int(value)
            case False:
                pass

        match value.startswith("https://t.me/"):
            case True:
                value = value.split("https://t.me/")[1]
            case False:
                pass

        match not value.startswith("@"):
            case True:
                value = f"@{value}"
            case False:
                pass

        return value
        
class RandomLinkList(list):
    def __str__(self):
        import random
        if not self:
            return ""
        return str(random.choice(self))

    def __bytes__(self):
        return str(self).encode("utf-8")

    def __repr__(self):
        return super().__repr__()


class RandomLink(Series):
    def __init__(self):
        super().__init__(
            validator=Link(),
            min_len=1
        )
        self.internal_id = "Series"
        self.doc = {
            "en": "A list of links, one of which will be chosen randomly",
            "ru": "Список ссылок, одна из которых будет выбрана случайным образом",
        }

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /, **kwargs) -> RandomLinkList:
        val_args = kwargs.copy()
        if 'validator' not in val_args:
            val_args['validator'] = Link()
        if 'min_len' not in val_args:
            val_args['min_len'] = 1

        clean_list = Series._validate(value, **val_args)
        return RandomLinkList(clean_list)
