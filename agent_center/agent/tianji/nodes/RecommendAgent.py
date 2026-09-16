import asyncio

from agent.mcp import mcp_service
from agent.tianji.nodes.BaseNodeAgent import BaseNodeAgent
from agent.tianji.tools import query_course_by_id
from agent.prompts import system_prompt_config

class RecommendAgent(BaseNodeAgent):
    """
    课程推荐智能体
    """

    def system_prompt(self):
        return system_prompt_config.chat_recommend_message

    def tools(self):
        #return [query_course_by_id]
        tool = asyncio.run(mcp_service.get_tool("query_course_by_id"))
        return [tool]