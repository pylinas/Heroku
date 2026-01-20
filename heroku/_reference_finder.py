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

import gc as _gc
import inspect
import logging
import types as _types
from typing import Any

logger = logging.getLogger(__name__)


def proxy0(data: Any) -> Any:
    def proxy1() -> Any:
        return data

    return proxy1


_CELLTYPE = type(proxy0(None).__closure__[0])


def replace_all_refs(replace_from: Any, replace_to: Any) -> Any:
    """
    :summary: Uses :mod:`gc` module to replace all references to obj
              :attr:`replace_from` with :attr:`replace_to` (it tries it's best,
              anyway).
    :param replace_from: The obj you want to replace.
    :param replace_to: The new objject you want in place of old one.
    :returns: The replace_from
    """
    # https://github.com/cart0113/pyjack/blob/dd1f9b70b71f48335d72f53ee0264cf70dbf4e28/pyjack.py

    _gc.collect()

    hit = False
    for referrer in _gc.get_referrers(replace_from):
        # FRAMES -- PASS THEM UP
        if isinstance(referrer, _types.FrameType):
            continue

        match referrer:
            # DICTS
            case dict():
                cls = None

                # THIS CODE HERE IS TO DEAL WITH DICTPROXY TYPES
                if "__dict__" in referrer and "__weakref__" in referrer:
                    for cls in _gc.get_referrers(referrer):
                        if inspect.isclass(cls) and cls.__dict__ == referrer:
                            break

                for key, value in list(referrer.items()):
                    # REMEMBER TO REPLACE VALUES ...
                    if value is replace_from:
                        hit = True
                        referrer[key] = replace_to
                        if cls:  # AGAIN, CLEANUP DICTPROXY PROBLEM
                            setattr(cls, key, replace_to)
                    # AND KEYS.
                    if key is replace_from:
                        hit = True
                        del referrer[key]
                        referrer[replace_to] = value

            case list():
                for i, value in enumerate(referrer):
                    if value is replace_from:
                        hit = True
                        referrer[i] = replace_to

            case set():
                if replace_from in referrer:
                    referrer.remove(replace_from)
                    referrer.add(replace_to)
                    hit = True

            case (tuple() | frozenset()):
                new_tuple = [
                    replace_to if obj is replace_from else obj
                    for obj in referrer
                ]
                replace_all_refs(referrer, type(referrer)(new_tuple))

            case _CELLTYPE():
                def _proxy0(data: Any) -> Any:
                    def proxy1() -> Any:
                        return data

                    return proxy1

                proxy = _proxy0(replace_to)
                newcell = proxy.__closure__[0]
                replace_all_refs(referrer, newcell)

            case _types.FunctionType():
                localsmap = {}
                for key in ["code", "globals", "name", "defaults", "closure"]:
                    orgattr = getattr(referrer, f"__{key}__")
                    localsmap[key] = replace_to if orgattr is replace_from else orgattr
                localsmap["argdefs"] = localsmap["defaults"]
                del localsmap["defaults"]
                newfn = _types.FunctionType(**localsmap)
                replace_all_refs(referrer, newfn)

            case _:
                logger.debug("%s is not supported.", referrer)

    if not hit:
        raise AttributeError(f"Object '{replace_from}' not found")

    return replace_from
