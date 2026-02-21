"""Support agent pool: general support, FAQ, help. Uses tools + RAG + conversation history."""
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from ..config import config
from ..shared_services.rag import RAGService, StubRAGService
from ..shared_services.guardrails import GuardrailService, StubGuardrailService, SimpleGuardrailService
from ..shared_services.history_rag import ConversationHistoryRAG
from ..tools.support_tools import get_support_tools
from ..tools.mcp_client import get_tools_with_mcp


def create_support_agent(
    rag: RAGService | None = None,
    model: str = "gpt-4o-mini",
    history_rag: ConversationHistoryRAG | None = None,
    guardrail: GuardrailService | None = None,
) -> "SupportAgent":
    """Create Support agent with RAG, conversation history, tools, and guardrails. MCP is required (MCP_SERVER_URL must be set)."""
    gr = guardrail or (SimpleGuardrailService() if config.guardrails_enabled else StubGuardrailService())
    return SupportAgent(rag=rag or StubRAGService(), model=model, history_rag=history_rag or ConversationHistoryRAG(), guardrail=gr)


class SupportAgent:
    """Support agent: RAG + conversation history + LLM + tools + MCP tools."""

    def __init__(
        self,
        rag: RAGService,
        model: str = "gpt-4o-mini",
        history_rag: ConversationHistoryRAG | None = None,
        guardrail: GuardrailService | None = None,
    ) -> None:
        self.rag = rag
        self.history_rag = history_rag or ConversationHistoryRAG()
        self.guardrail = guardrail or StubGuardrailService()
        built_in = get_support_tools()
        self.tools = get_tools_with_mcp(built_in)
        # top_p: nucleus sampling to constrain token selection, reduce hallucinations
        self.llm = ChatOpenAI(model=model, temperature=0, top_p=config.top_p).bind_tools(self.tools)

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Process state: guardrails → RAG context + tool-calling loop → guard_output."""
        messages = list(state.get("messages", []))
        last_msg = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        if not last_msg or not getattr(last_msg, "content", None):
            return {
                "messages": [AIMessage(content="I didn't receive a message. How can I help?")],
                "resolved": False,
                "needs_escalation": False,
                "last_rag_context": "",
            }

        query = str(last_msg.content)
        # Input guardrail: block off-topic or policy-violating user input
        input_result = self.guardrail.guard_input(query)
        if not input_result.passed:
            return {
                "messages": [AIMessage(content="I can only help with support questions. Please ask about our products, FAQ, or how to get assistance.")],
                "resolved": False,
                "needs_escalation": False,
                "last_rag_context": "",
            }
        chunks = self.rag.retrieve(query, top_k=3)
        doc_context = "\n".join(c.content for c in chunks)
        history_context = self.history_rag.format_for_context(messages, max_turns=10)

        system = (
            "You are a helpful support agent. Answer based on the context when possible. "
            "Use the conversation history to understand the ongoing issue and avoid repeating yourself. "
            "Use search_knowledge_base for FAQs and how-to questions. Use create_support_ticket when the user needs human follow-up. "
            "If unsure, say so and suggest escalating to a human. Keep replies concise."
        )
        prompt_msgs = [
            SystemMessage(content=system),
            HumanMessage(
                content=f"Conversation history (for issue handling):\n{history_context}\n\n"
                f"Document context:\n{doc_context}\n\n"
                f"Current user message: {query}"
            ),
        ]
        # Tool-calling loop
        response = self._invoke_with_tools(prompt_msgs)
        content = response.content if isinstance(response.content, str) else str(response.content or "")
        # Output guardrail: filter policy-violating content
        content = self.guardrail.guard_output(content).filtered_text

        return {
            "messages": [AIMessage(content=content)],
            "resolved": "unsure" not in content.lower() and "escalat" not in content.lower(),
            "needs_escalation": "escalat" in content.lower() or "ticket" in content.lower(),
            "last_rag_context": doc_context,
        }

    def _invoke_with_tools(self, messages: list) -> AIMessage:
        """Invoke LLM with tools; loop until no more tool calls."""
        response = self.llm.invoke(messages)
        if not getattr(response, "tool_calls", None):
            return response

        tool_map = {t.name: t for t in self.tools}
        msgs = list(messages) + [response]

        for tc in response.tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            tool_call_id = tc.get("id", "")
            tool = tool_map.get(name)
            if tool:
                result = tool.invoke(args)
            else:
                result = f"Unknown tool: {name}"
            msgs.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))

        return self._invoke_with_tools(msgs)
