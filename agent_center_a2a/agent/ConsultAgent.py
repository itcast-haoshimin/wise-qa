from datetime import datetime
from agent.BaseAgent import BaseAgent
from agent.prompts import system_prompt_config
from agent.tools import query_course_by_id
from agent.mcp import mcp_service
import asyncio


class ConsultAgent(BaseAgent):
    """
    课程咨询智能体
    """

    def system_prompt(self):
        return system_prompt_config.chat_consult_message

    def system_prompt_params(self):
        return {"now": datetime.now()}

    def tools(self) -> list:
        #return [query_course_by_id]
        tool = asyncio.run(mcp_service.get_tool("query_course_by_id"))
        return [tool]


consult_agent = ConsultAgent()