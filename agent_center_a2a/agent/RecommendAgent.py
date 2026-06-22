from agent.BaseAgent import BaseAgent
from agent.prompts import system_prompt_config
from agent.tools import query_course_by_id
from agent.mcp import mcp_service
import asyncio

class RecommendAgent(BaseAgent):
    """
    课程推荐智能体
    """

    def system_prompt(self):
        return system_prompt_config.chat_recommend_message

    def tools(self) -> list:
        #return [query_course_by_id]
        tool = asyncio.run(mcp_service.get_tool("query_course_by_id"))
        return [tool]
recommend_agent = RecommendAgent()