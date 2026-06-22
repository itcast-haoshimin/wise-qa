from dataclasses import asdict

from a2a.helpers import new_text_artifact
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskArtifactUpdateEvent, TaskStatusUpdateEvent, TaskStatus, TaskState

from agent.BaseAgent import BaseAgent
from agent.result import CourseInfo, PrePlaceOrder
from util import JsonUtil


class MyExecutor(AgentExecutor):
    """
    MyExecutor 执行器（面向 A2A 执行框架）。

    功能：
        - 接收 RequestContext 中的用户消息
        - 调用 agent 执行逻辑（通常是 LLM 流式响应）
        - 将 agent 产生的事件逐条推送到前端（EventQueue）
        - 在消息流结束后，检查并返回工具执行结果（tool result）
        - 发送最终 Task 状态（completed）

    """

    def __init__(self, agent: BaseAgent):
        """
        初始化执行器。

        参数:
            agent (BaseAgent): 业务层的智能体对象，必须实现 execute(message) 方法，
                               且返回一个异步生成器，按流式输出内容。
        """
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        执行主流程（核心逻辑）。

        步骤：
            1. 校验输入 message
            2. 调用 agent.execute() 获取流式返回数据
            3. 将每个事件作为 TaskArtifactUpdateEvent 推送到客户端
            4. 如果是工具事件，进行判断类型，将结果metadata方式传递会客户端
            5. 发送最终 TaskStatusUpdateEvent（标记任务完成）

        参数:
            context (RequestContext): 请求上下文（包含 message、task_id、context_id 等）
            event_queue (EventQueue): 用于向 A2A 系统发送事件
        """
        if not context.message:
            raise Exception('No message provided')

        tool_result = {}
        # 使用 agent 的异步生成器流式输出结果
        async for event in self.agent.execute(context.message):
            # 构建并发送 artifact 更新事件（发送给客户端）
            if not event.get("tool", False):
                #不是工具调用事件，正常的数据返回给客户端
                message = TaskArtifactUpdateEvent(
                    context_id=context.context_id,
                    task_id=context.task_id,
                    artifact=new_text_artifact(
                        name="current_result",  # 客户端可根据 name 识别当前内容
                        text=event.get("content"),  # LLM 产生的文本
                    ),
                )
                await event_queue.enqueue_event(message)
            else:
                _content = event.get("content")
                if _content:
                    #在这里处理的是工具调用的结果，需要返回给客户端，先把结果收集起来
                    #在最后，以元数据的方式返回给客户端
                    if event.get("name") == "query_course_by_id":
                        course_info = JsonUtil.to_obj(_content, CourseInfo)
                        tool_result[f"courseInfo_{course_info.id}"] = {k: v for k, v in asdict(course_info).items() if v is not None}
                    elif event.get("name") == "pre_place_order":
                        order = JsonUtil.to_obj(_content, PrePlaceOrder)
                        tool_result["prePlaceOrder"] = {k: v for k, v in asdict(order).items() if v is not None}

            # 如果 agent 返回 done=True，则结束流式输出
            if event["done"]:
                break

        # 定义元数据，将请求id和工具调用结果一起返回给客户端
        metadata = context.message.metadata if hasattr(context.message,
                                                       'metadata') and context.message.metadata is not None else {}
        request_id = metadata.get("request_id", "") if isinstance(metadata, dict) else ""
        metadata = {"request_id": request_id}

        if tool_result:
            # 如果存在工具调用结果，则写入 metadata，随最终事件输出
            metadata["tool_result"] = tool_result

            # -----------------------------------------------
            # 推送任务最终状态（completed）
            # -----------------------------------------------

        status = TaskStatusUpdateEvent(
            context_id=context.context_id,
            task_id=context.task_id,
            status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            #final=True,  # 表示最后一个事件
            metadata=metadata  # 附带元数据返回
        )
        await event_queue.enqueue_event(status)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        取消任务（当前不支持）。

        A2A 框架可能调用此接口取消任务，当前场景不支持，因此直接抛出异常。
        """
        raise Exception("cancel not supported")