from a2a.server.agent_execution import AgentExecutor

from agent import consult_agent
from app.BaseApp import BaseApp
from executor.MyExecutor import MyExecutor


class ConsultApp(BaseApp):
    """
    课程咨询应用
    """

    def app_type(self):
        return "consult"

    def agent_executor(self) -> AgentExecutor:
        return MyExecutor(consult_agent)

consult_app = ConsultApp()