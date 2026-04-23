# Orchids Agent Architecture Analysis

## Overview

The **Orchids** agent is a sophisticated AI agent powered by **Claude Sonnet 4-6** (via Amazon Bedrock) that uses a **Server-Sent Events (SSE)** streaming protocol to communicate with clients. It follows a **ReAct-style** (Reasoning + Acting) architecture where the LLM thinks through a problem, uses tools to gather information, and then synthesizes a final answer.

---

## 1. Communication Protocol: Server-Sent Events (SSE)

The agent communicates via an SSE stream with the following format:

```
data: {"type":"orchids.started","data":{"ptySessionId":"...","sandboxId":"..."}}

data: {"type":"orchids.s2-stream","data":{"uri":"s2://orchids-runs/..."}}

data: {"type":"orchids.route_decision","data":{"runtime":"claude","model":"auto"}}

data: {"type":"orchids.event","data":"{...escaped JSON...}"}

event: ping
data: {}
```

### Event Types

| Event Type | Purpose |
|-----------|---------|
| `orchids.started` | Session initialization with IDs |
| `orchids.s2-stream` | References the stream storage location |
| `orchids.route_decision` | Model routing decision (which LLM to use) |
| `orchids.event` | Main event wrapper containing all LLM/tool interactions |
| `ping` | Keep-alive heartbeat |

### Inside `orchids.event`

The main events have an inner `type` field:

| Inner Type | Purpose |
|-----------|---------|
| `system` / `init` | Initial system configuration, available tools, MCP servers |
| `stream_event` | Raw LLM streaming deltas (thinking, content, tool_use) |
| `assistant` | Complete assistant message (after streaming finishes) |
| `user` | Tool results fed back to the LLM |

---

## 2. Agent Architecture: ReAct Loop

The agent follows a classic **ReAct (Reasoning + Acting)** loop:

```
User Request
    ↓
LLM Thinks (thinking_delta events)
    ↓
LLM Decides to Use Tools (tool_use events)
    ↓
Tools Execute (Web_Search, WebFetch, etc.)
    ↓
Tool Results Fed Back as "user" messages
    ↓
LLM Thinks Again
    ↓
... (repeat until satisfied)
    ↓
Final Answer
```

### Example Flow from the Log

1. **User asks**: "Best gaming PC under ₹80,000"
2. **LLM thinks**: "The user wants to find the best deals... Let me search for current deals" (`thinking_delta`)
3. **LLM calls tool**: `mcp__orchids__Web_Search` with query "best gaming PC build under 80000 rupees..."
4. **Search results** returned as `user` message with `tool_result`
5. **LLM calls more tools**: `WebFetch` on specific URLs to get detailed prices
6. **LLM encounters errors**: Some pages return 403 or have no pricing info
7. **LLM adapts**: Tries different search queries and different retailers
8. **LLM compiles**: After gathering enough data, it synthesizes a PC build list

---

## 3. Tools & Capabilities

From the `init` event, the agent has access to:

### Native Tools
- `Task` - Delegate subtasks to other agents
- `TaskOutput` - Output from delegated tasks
- `Bash` - Execute shell commands
- `Glob` - File pattern matching
- `Grep` - Content search
- `Read` / `Edit` / `Write` - File operations
- `WebFetch` - Fetch and analyze a specific URL
- `TodoWrite` - Task list management
- `AskUserQuestion` - Interactive user prompts

### MCP Servers
- `orchids` - The main MCP server providing:
  - `mcp__orchids__Web_Search` - Web search with Google-like results
  - `mcp__orchids__ReportFinalDeliverables` - Final report generation
  - `mcp__orchids__GenerateOrEditMedia` - Media creation
  - `mcp__orchids__Web_Search` - Additional search capabilities

### Agent Types
- `general-purpose` - Default agent
- `statusline-setup` - Setup helper
- `Explore` - Codebase explorer
- `Plan` - Planning agent

---

## 4. Key Technical Features

### A. Streaming Token Deltas

The LLM streams every token separately:

```json
{"type":"stream_event","event":{"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"The user wants"}}}
{"type":"stream_event","event":{"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":" to find the best deals for"}}}
```

This allows the UI to show the agent "thinking" in real-time.

### B. Tool Use with Incremental JSON

When the LLM decides to use a tool, it streams the JSON parameters incrementally:

```json
{"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\"query\": \"best gaming PC build"}}
{"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":" under 80000 rup"}}
```

### C. Prompt Caching

The agent uses Claude's prompt caching extensively:

```json
"usage":{
  "input_tokens":10,
  "cache_creation_input_tokens":424,
  "cache_read_input_tokens":18793,
  "cache_creation":{"ephemeral_5m_input_tokens":424,"ephemeral_1h_input_tokens":0}
}
```

This makes multi-turn conversations fast and cost-effective by caching the system prompt and conversation history.

### D. Session & Message Tracking

Every event has:
- `session_id` - The conversation session
- `uuid` - Unique event ID
- `parent_tool_use_id` - Links tool results to their requests
- `tool_use_id` - Unique ID for each tool invocation

### E. Error Resilience

The agent gracefully handles failures:

```json
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"Request failed with status code 403","is_error":true}]}}
```

When a `WebFetch` fails with 403 or a page has no useful data, the LLM adapts its strategy rather than crashing.

---

## 5. How to Build a Similar Agent

### Option A: Full-Stack Implementation (Recommended)

#### Architecture

```
┌─────────────┐      SSE/WS      ┌─────────────────────┐      HTTPS       ┌─────────────┐
│   Client    │ ◄──────────────► │   Agent Server      │ ◄──────────────► │  LLM API    │
│  (React/    │                  │  (Node.js/Python)   │                  │  (Bedrock/  │
│   CLI)      │                  │                     │                  │   OpenAI)   │
└─────────────┘                  └─────────────────────┘                  └─────────────┘
                                          │
                                          ▼
                                ┌─────────────────────┐
                                │   MCP Server        │
                                │  (Tool Registry)    │
                                └─────────────────────┘
```

#### Step-by-Step Implementation

**1. Set Up the SSE Stream Server**

```javascript
// server.js - Express with SSE
const express = require('express');
const app = express();

app.get('/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const sessionId = generateUUID();

  // Send initialization events
  res.write(`data: ${JSON.stringify({type: 'agent.started', data: {sessionId}})}\n\n`);

  // Handle client messages
  // ...
});
```

**2. Create the ReAct Loop**

```python
# agent.py
class ReActAgent:
    def __init__(self, llm_client, tools):
        self.llm = llm_client
        self.tools = tools
        self.messages = []

    async def run(self, user_input, stream_callback):
        self.messages.append({"role": "user", "content": user_input})

        while True:
            # Stream the LLM response
            response = await self.llm.stream_messages(
                messages=self.messages,
                tools=self.tools,
                callback=stream_callback
            )

            # Check if the LLM wants to use tools
            if response.stop_reason == "tool_use":
                for tool_use in response.tool_uses:
                    # Execute the tool
                    result = await self.execute_tool(tool_use)

                    # Stream the tool result
                    stream_callback({
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [{"type": "tool_result", **result}]
                        }
                    })

                    # Add to conversation history
                    self.messages.append({
                        "role": "user",
                        "content": [{"tool_use_id": tool_use.id, "type": "tool_result", **result}]
                    })
            else:
                # Final answer - break the loop
                break

    async def execute_tool(self, tool_use):
        tool = self.tools[tool_use.name]
        try:
            result = await tool(**tool_use.input)
            return {"content": result, "is_error": False}
        except Exception as e:
            return {"content": str(e), "is_error": True}
```

**3. Implement Tools (MCP Pattern)**

```python
# tools.py
class WebSearchTool:
    name = "web_search"
    description = "Search the web for information"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        }
    }

    async def run(self, query: str):
        # Use Google Custom Search, Serper, or similar API
        results = await search_api.search(query)
        return [{"title": r.title, "url": r.url} for r in results]

class WebFetchTool:
    name = "web_fetch"
    description = "Fetch and extract content from a URL"
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "prompt": {"type": "string", "description": "What to extract"}
        }
    }

    async def run(self, url: str, prompt: str = None):
        content = await fetch_url(url)
        if prompt:
            # Use a smaller LLM call to extract specific info
            extracted = await extract_with_llm(content, prompt)
            return extracted
        return content
```

**4. Stream Events to Client**

```python
async def stream_to_client(agent_response, client_connection):
    for event in agent_response.events:
        if event.type == "thinking_delta":
            client_connection.send({
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "thinking_delta", "thinking": event.text}
                }
            })
        elif event.type == "tool_use":
            client_connection.send({
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "content_block": {"type": "tool_use", "name": event.tool_name, "input": {}}
                }
            })
            # Stream JSON incrementally
            for chunk in json_chunks(event.input):
                client_connection.send({
                    "type": "stream_event",
                    "event": {
                        "type": "content_block_delta",
                        "delta": {"type": "input_json_delta", "partial_json": chunk}
                    }
                })
```

**5. Client-Side Rendering**

```typescript
// client.ts
class AgentClient {
  private eventSource: EventSource;

  connect() {
    this.eventSource = new EventSource('/stream');

    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleEvent(data);
    };
  }

  handleEvent(event: AgentEvent) {
    switch (event.type) {
      case 'stream_event':
        if (event.event.type === 'content_block_delta') {
          if (event.event.delta.type === 'thinking_delta') {
            this.ui.showThinking(event.event.delta.thinking);
          } else if (event.event.delta.type === 'input_json_delta') {
            this.ui.updateToolInput(event.event.delta.partial_json);
          }
        }
        break;
      case 'assistant':
        this.ui.showMessage(event.message);
        break;
      case 'user':
        // Tool results - usually internal
        break;
    }
  }
}
```

---

### Option B: Using Existing Frameworks

#### 1. **Vercel AI SDK** (Easiest)

```bash
npm install ai @anthropic-ai/sdk
```

```typescript
// app/api/chat/route.ts
import { streamText } from 'ai';
import { anthropic } from '@ai-sdk/anthropic';
import { webSearchTool, webFetchTool } from './tools';

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    model: anthropic('claude-sonnet-4-20250514'),
    messages,
    tools: { webSearch: webSearchTool, webFetch: webFetchTool },
    maxSteps: 10, // Multi-step tool use
  });

  return result.toDataStreamResponse();
}
```

```typescript
// app/page.tsx
'use client';
import { useChat } from 'ai/react';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();

  return (
    <div>
      {messages.map(m => (
        <div key={m.id}>
          {m.role === 'user' ? 'User: ' : 'AI: '}
          {m.parts?.map((part, i) => {
            if (part.type === 'text') return <span key={i}>{part.text}</span>;
            if (part.type === 'tool-invocation') {
              return <ToolCall key={i} tool={part.toolInvocation} />;
            }
          })}
        </div>
      ))}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
      </form>
    </div>
  );
}
```

#### 2. **LangChain / LangGraph**

```python
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain.tools import tool

@tool
def web_search(query: str) -> str:
    """Search the web."""
    return search_api.search(query)

@tool
def web_fetch(url: str, prompt: str = None) -> str:
    """Fetch a URL."""
    return fetch_and_extract(url, prompt)

model = ChatAnthropic(model="claude-sonnet-4-6")
agent = create_react_agent(model, [web_search, web_fetch])

# Stream events
async for event in agent.astream({"messages": [("user", "Best gaming PC under 80000")]}):
    print(event)
```

#### 3. **MCP (Model Context Protocol) - Official**

The Orchids agent uses MCP. You can build similar:

```typescript
// server.ts - MCP Server
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

const server = new Server({
  name: 'my-agent-tools',
  version: '1.0.0',
}, {
  capabilities: {
    tools: {
      web_search: {
        description: 'Search the web',
        inputSchema: { type: 'object', properties: { query: { type: 'string' } } }
      },
      web_fetch: {
        description: 'Fetch a URL',
        inputSchema: { type: 'object', properties: { url: { type: 'string' } } }
      }
    }
  }
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'web_search') {
    const results = await search(args.query);
    return { content: [{ type: 'text', text: JSON.stringify(results) }] };
  }

  if (name === 'web_fetch') {
    const content = await fetch(args.url);
    return { content: [{ type: 'text', text: content }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

---

## 6. Infrastructure & Deployment

### Required Components

| Component | Purpose | Options |
|-----------|---------|---------|
| **LLM Provider** | Core reasoning | Anthropic (Claude), OpenAI (GPT-4), AWS Bedrock |
| **Search API** | Web search | Serper.dev, Google CSE, Bing API, Tavily |
| **Fetch Service** | URL fetching | Puppeteer, Playwright, Jina AI Reader, Firecrawl |
| **Stream Server** | SSE/WebSocket | Node.js/Express, Python/FastAPI, Cloudflare Workers |
| **Database** | Session storage | Redis, PostgreSQL, Upstash |
| **Frontend** | UI | React/Vue + EventSource |

### AWS Bedrock Setup (as used by Orchids)

```python
import boto3

bedrock = boto3.client('bedrock-runtime')

response = bedrock.invoke_model_with_response_stream(
    modelId='anthropic.claude-sonnet-4-20250514-v1:0',
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
        "tools": tools,
        "max_tokens": 4096,
        "system": system_prompt
    })
)

for event in response['body']:
    chunk = json.loads(event['chunk']['bytes'])
    # Stream to client
```

---

## 7. Key Design Decisions

### Why SSE over WebSockets?
- **SSE**: Simpler, auto-reconnects, works over HTTP/2, good for server-to-client streaming
- **WebSockets**: Better for bidirectional real-time, but more complex
- Orchids uses SSE because the client primarily *receives* data; sends happen via separate POST requests

### Why Show Thinking?
- Builds user trust
- Allows users to cancel if the agent is going down the wrong path
- Makes debugging easier

### Why Prompt Caching?
- Multi-turn tool-use conversations can get very long (30k+ tokens)
- Caching reduces latency and cost significantly
- Orchids shows `cache_read_input_tokens: 40034` - that's 40K tokens being reused!

### Why MCP?
- Standardizes tool definitions across different LLM providers
- Allows tools to be shared between different agents
- Type-safe tool schemas

---

## 8. Simplified Starter Code

Here's a minimal working example you can run:

```python
# minimal_agent.py
import asyncio
import json
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key="your-key")

async def search_web(query: str) -> str:
    # Replace with real search API
    return json.dumps([{"title": f"Result for {query}", "url": "https://example.com"}])

async def fetch_url(url: str) -> str:
    # Replace with real fetch
    return f"Content from {url}"

TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "web_fetch",
        "description": "Fetch a URL",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    }
]

async def run_agent(user_input: str):
    messages = [{"role": "user", "content": user_input}]

    while True:
        print(f"\n--- LLM Call ({len(messages)} messages) ---")

        stream = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=messages,
            tools=TOOLS,
            stream=True
        )

        current_tool_use = None
        current_tool_input = ""
        assistant_content = []

        async for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "thinking":
                    print("🧠 Thinking...")
                elif event.content_block.type == "tool_use":
                    current_tool_use = {
                        "id": event.content_block.id,
                        "name": event.content_block.name
                    }
                    print(f"🔧 Tool: {event.content_block.name}")

            elif event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    print(event.delta.thinking, end="", flush=True)
                elif event.delta.type == "text_delta":
                    print(event.delta.text, end="", flush=True)
                elif event.delta.type == "input_json_delta":
                    current_tool_input += event.delta.partial_json
                    print(".", end="", flush=True)

            elif event.type == "message_stop":
                print(f"\n✅ Stop reason: {event.message.stop_reason}")

                if event.message.stop_reason == "tool_use":
                    # Execute tools
                    for block in event.message.content:
                        if block.type == "tool_use":
                            tool_input = json.loads(block.input)
                            print(f"\n📡 Executing {block.name}({tool_input})")

                            if block.name == "web_search":
                                result = await search_web(tool_input["query"])
                            elif block.name == "web_fetch":
                                result = await fetch_url(tool_input["url"])
                            else:
                                result = "Unknown tool"

                            messages.append({
                                "role": "assistant",
                                "content": event.message.content
                            })
                            messages.append({
                                "role": "user",
                                "content": [{"type": "tool_result", "tool_use_id": block.id, "content": result}]
                            })
                else:
                    # Final answer
                    return

# Run
asyncio.run(run_agent("Find the best gaming PC under $1000"))
```

---

## 9. Comparison: Build vs Buy

| Approach | Time | Cost | Flexibility | Best For |
|----------|------|------|-------------|----------|
| **Vercel AI SDK** | 1-2 days | Low | Medium | Prototypes, simple agents |
| **LangChain/LangGraph** | 3-5 days | Low | High | Complex workflows, research |
| **Custom (like Orchids)** | 2-4 weeks | Medium | Maximum | Production, scale, specific UX |
| **OpenCode / Claude Code** | Minutes | Free (local) | Limited | Personal use, file-based tasks |

---

## 10. Summary

The Orchids agent is a **production-grade ReAct agent** that:

1. Uses **SSE streaming** for real-time client communication
2. Leverages **Claude's tool-use capabilities** for multi-step reasoning
3. Implements **prompt caching** for efficiency at scale
4. Wraps tools in an **MCP server** for standardization
5. Handles errors gracefully and adapts its strategy
6. Shows its thinking process to build user trust

To build something similar, start with the **Vercel AI SDK** for a quick prototype, then graduate to a **custom implementation** with MCP when you need full control over the streaming protocol, caching, and tool ecosystem.

The key insight from Orchids is that **the agent is not just an LLM - it's a loop**. The LLM thinks, acts (via tools), observes results, and thinks again. This loop continues until the task is complete or the LLM decides it has enough information to provide a final answer.