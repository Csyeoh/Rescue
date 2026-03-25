from crewai.events import (
    BaseEventListener,
    AgentReasoningCompletedEvent,
    MCPToolExecutionCompletedEvent
)
import websocket_manager

class ReasoningLogger(BaseEventListener):
    """
    A simple event listener class for logging CrewAI agent reasoning and execution events.
    """
    def __init__(self):
        super().__init__()
        
    def setup_listeners(self, crewai_event_bus):

        @crewai_event_bus.on(AgentReasoningCompletedEvent)
        def on_reasoning_completed(source, event: AgentReasoningCompletedEvent):
            print(f"Plan: {str(event)}")
            websocket_manager.send_to_ui("agent_reasoning_completed", {
                "agent_role": event.agent_role,
                "task_id": event.task_id,
                "plan": event.plan,
                "ready": event.ready
            })
            
        @crewai_event_bus.on(MCPToolExecutionCompletedEvent)
        def on_mcp_tool_completed(source, event: MCPToolExecutionCompletedEvent):
            print(f"tool call: {str(event)}")
            websocket_manager.send_to_ui("mcp_tool_execution_completed", {
                "tool_name": event.tool_name,
                "tool_args": event.tool_args,
                "result": event.result,
                "execution_duration_ms": event.execution_duration_ms
            })