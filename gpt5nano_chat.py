#!/home/gslee/llm-api-vault/venv/bin/python3
"""Interactive chat with GPT-5 Nano (OpenAI) - maintains conversation history."""

import json
import os
import sys

from openai import OpenAI
from web_search import search, fetch_page, format_results
from cron_manager import cron_list, cron_create, cron_delete

API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY_HERE")

client = OpenAI(api_key=API_KEY)

# ── Settings ────────────────────────────────────────────────────────
MODEL = "gpt-5-nano"            # Model ID
STREAM = True                   # True for streaming, False for batch
TEMPERATURE = None              # 0.0–2.0 (None = default)
# ────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Use when the user asks about recent events, real-time data, or anything you're unsure about.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Fetch and read the full text content of a webpage. Use after web_search to read detailed content from a specific search result URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to read"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cron_list",
            "description": "List all current cron jobs for this user.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cron_create",
            "description": "Create a new scheduled cron job. The user will be asked to confirm before it is added.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedule": {"type": "string", "description": "Cron schedule expression, e.g. '0 9 * * *' for daily at 9am, '*/5 * * * *' for every 5 minutes"},
                    "command": {"type": "string", "description": "Shell command to run"},
                },
                "required": ["schedule", "command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cron_delete",
            "description": "Delete a cron job by its index number (from cron_list). The user will be asked to confirm before deletion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "Index of the cron job to delete"},
                },
                "required": ["index"],
            },
        },
    },
]


def build_params(messages):
    """Build API call parameters."""
    params = {"model": MODEL, "messages": messages, "stream": STREAM, "tools": TOOLS}
    if TEMPERATURE is not None:
        params["temperature"] = TEMPERATURE
    return params


def handle_tool_calls(response_message, messages):
    """Process tool calls from the model, execute tools, and get follow-up response."""
    messages.append(response_message)

    for tool_call in response_message.tool_calls:
        args = json.loads(tool_call.function.arguments)
        if tool_call.function.name == "web_search":
            query = args.get("query", "")
            print(f"[Searching: {query}...]")
            try:
                results = search(query)
                result_text = format_results(results)
            except Exception as e:
                result_text = f"Search error: {e}"
            print(result_text)
        elif tool_call.function.name == "read_webpage":
            url = args.get("url", "")
            print(f"[Reading: {url}...]")
            try:
                text = fetch_page(url)
                if len(text) > 15000:
                    text = text[:15000] + "\n\n[... content truncated ...]"
                result_text = text
            except Exception as e:
                result_text = f"Fetch error: {e}"
        elif tool_call.function.name == "cron_list":
            result_text = cron_list()
            print(result_text)
        elif tool_call.function.name == "cron_create":
            schedule = args.get("schedule", "")
            command = args.get("command", "")
            result_text = cron_create(schedule, command)
            print(result_text)
        elif tool_call.function.name == "cron_delete":
            index = args.get("index", 0)
            result_text = cron_delete(index)
            print(result_text)
        else:
            result_text = f"Unknown tool: {tool_call.function.name}"
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result_text,
        })

    follow_up = client.chat.completions.create(**build_params(messages))
    return follow_up


def handle_stream(response):
    """Handle streaming response, printing tokens as they arrive."""
    answer_chunks = []
    tool_calls_data = {}

    for chunk in response:
        delta = chunk.choices[0].delta

        # Accumulate tool call chunks
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_data:
                    tool_calls_data[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                if tc.id:
                    tool_calls_data[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tool_calls_data[idx]["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments
            continue

        if delta.content:
            if not answer_chunks:
                print("\nAssistant: ", end="")
            print(delta.content, end="", flush=True)
            answer_chunks.append(delta.content)

    if tool_calls_data:
        return None, tool_calls_data

    print("\n")
    return "".join(answer_chunks), None


def handle_batch(response):
    """Handle non-streaming response."""
    message = response.choices[0].message
    if message.tool_calls:
        return None, message
    answer = message.content or ""
    print(f"\nAssistant: {answer}\n")
    return answer, None


def main():
    messages = []
    print(f"GPT-5 Nano Chat (model: {MODEL}, stream: {STREAM}, temp: {TEMPERATURE or 'default'})")
    print("Type 'quit' or 'exit' to end. Type 'clear' to reset conversation.")
    print("Type '/search <query>' to search the web manually.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Bye!")
            break
        if user_input.lower() == "clear":
            messages.clear()
            print("[Conversation cleared]\n")
            continue
        if user_input.lower().startswith("/search "):
            query = user_input[8:].strip()
            if not query:
                continue
            user_input = f"Research the following by searching the web, reading the most relevant pages in detail, and providing a comprehensive answer:\n\n{query}"

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(**build_params(messages))
            answer = None

            for _ in range(10):  # max 10 rounds of tool calls
                if STREAM:
                    answer, tool_data = handle_stream(response)
                    if tool_data:
                        from openai.types.chat import ChatCompletionMessage
                        from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function
                        tc_list = []
                        for idx in sorted(tool_data.keys()):
                            tc = tool_data[idx]
                            tc_list.append(ChatCompletionMessageToolCall(
                                id=tc["id"],
                                type="function",
                                function=Function(name=tc["function"]["name"], arguments=tc["function"]["arguments"]),
                            ))
                        msg = ChatCompletionMessage(role="assistant", content=None, tool_calls=tc_list)
                        response = handle_tool_calls(msg, messages)
                        continue
                else:
                    answer, tool_msg = handle_batch(response)
                    if tool_msg:
                        response = handle_tool_calls(tool_msg, messages)
                        continue
                break  # got a text answer, stop looping

            # If loop exhausted without a text answer, force one without tools
            if not answer:
                no_tool_params = {"model": MODEL, "messages": messages, "stream": STREAM}
                if TEMPERATURE is not None:
                    no_tool_params["temperature"] = TEMPERATURE
                response = client.chat.completions.create(**no_tool_params)
                if STREAM:
                    answer, _ = handle_stream(response)
                else:
                    answer, _ = handle_batch(response)

            if answer:
                messages.append({"role": "assistant", "content": answer})

        except Exception as e:
            print(f"\nError: {e}\n")
            messages.pop()


if __name__ == "__main__":
    main()
