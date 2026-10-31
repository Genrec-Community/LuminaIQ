"""Backend enforcement of the tool switches (services/levels.py).

    @router.post("/generate", dependencies=[Depends(require_tool("quiz"))])
"""

from fastapi import Depends, HTTPException

from api.deps import get_current_user
from services.tools_catalog import TOOLS


async def assert_tool(user_id: str, tool: str) -> None:
    from services.levels import effective_for

    eff = await effective_for(user_id)
    if tool not in eff["tools"]:
        raise HTTPException(status_code=403, detail={
            "code": "tool_disabled", "tool": tool,
            "message": f"{TOOLS.get(tool, tool)} isn't turned on for your account. "
                       "Ask your teacher or school admin if you need it.",
        })


def require_tool(tool: str):
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool: {tool}")

    async def require_tool_dependency(current_user: dict = Depends(get_current_user)) -> None:
        await assert_tool(current_user["id"], tool)

    require_tool_dependency.__qualname__ = f"require_tool.{tool}"
    return require_tool_dependency
