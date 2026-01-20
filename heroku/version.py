"""Represents current userbot version"""
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

__version__ = (2, 0, 0)

from pathlib import Path

import git
from ._internal import (
    get_branch_name,
    check_commit_ancestor,
    reset_to_master,
    restore_worktree,
    restart,
)

repo_path = Path(__file__).parent.absolute()

try:
    branch = git.Repo(path=repo_path).active_branch.name
except Exception:
    branch = "master"


async def check_branch(me_id: int, allowed_ids: list[int]) -> None:
    repo_path = Path(__file__).parent.absolute()

    match me_id:
        case _ if me_id in allowed_ids:
            return
        case _:
            try:
                repo = git.Repo(path=repo_path)
            except Exception:
                return

            branch_name = get_branch_name(repo_path)
            is_ancestor = check_commit_ancestor(repo, branch_name)
            
            match is_ancestor:
                case True:
                    return
                case False:
                    try:
                        reset_to_master(repo_path)
                        restore_worktree(repo_path)
                    except Exception:
                        pass

    restart()
