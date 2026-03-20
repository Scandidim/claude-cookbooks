# Multi-Agent Orchestration

Building accessible AI systems through intelligent agent coordination.

## Overview

This guide demonstrates a multi-agent orchestration pattern for building more accessible and intelligent AI systems. Instead of a single monolithic agent, the system consists of:

1. **Orchestrator Agent** - Strategic coordinator that routes requests to specialists
2. **Summarization Agent** - Breaks down complex documents into digestible insights
3. **Settings Agent** - Manages user preferences and accessibility configurations
4. **Context Agent** - Maintains and recalls conversation history

## Key Concepts

### The Orchestration Pattern

The orchestrator analyzes user requests and intelligently routes them to one or more specialist agents. This approach offers:

- **Specialization**: Each agent develops expertise in one domain
- **Better Accessibility**: Specialists can focus on accessibility-specific needs
- **Context Preservation**: Shared state across all agents ensures consistency
- **Scalability**: New agents can be added without modifying core logic
- **Improved UX**: Users interact naturally without technical complexity

### Real-World Applications

This pattern has been successfully used for:

- **StreetReaderAI**: A virtual guide system for navigating physical spaces with visual and interactive agents
- **Multimodal Video Player**: Transforms passive video watching into interactive experiences with description and Q&A agents
- **Educational Platforms**: Multiple agents handling content explanation, progress tracking, and assessment
- **Document Processing**: Specialized agents for OCR, analysis, and formatting

## Running the Notebook

### Prerequisites

```bash
pip install anthropic
```

### Setup

1. Create a `.env` file with your API key:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

2. Open and run `guide.ipynb` in Jupyter or your preferred notebook environment

### What You'll Learn

- How to architect a multi-agent system
- How to implement an intelligent orchestrator
- How to create specialist agents with different expertise levels
- How to maintain shared context across agents
- How to route requests intelligently
- Real examples of accessibility-focused agent interactions

## Architecture Diagram

```
User Input
    ↓
[Orchestrator Agent]
    ├─→ Route to Summarization Agent → Complex document analysis
    ├─→ Route to Settings Agent → User preferences
    └─→ Route to Context Agent → Shared state management
    ↓
Unified Response
```

## Key Features

### 1. Intelligent Routing

The orchestrator analyzes requests and determines which specialist(s) should handle them:

```python
routing_decision = orchestrator.analyze_request(
    "Please summarize this accessibility document",
    context
)
# Returns: primary_agent, supporting_agents, reasoning, instructions
```

### 2. Shared Context Management

All agents operate within a shared context that persists across interactions:

```python
context = UserContext(
    user_id="user_001",
    document_content="...",
    accessibility_settings={...},
    conversation_history=[...],
    agent_outputs={...}
)
```

### 3. Specialist Agents

Each agent focuses on one area of expertise:

- **SummarizationAgent**: Analyzes documents and creates accessible summaries
- **SettingsAgent**: Manages accessibility configurations (text scale, contrast, language simplification)
- **ContextAgent**: Maintains conversation history and previous agent outputs

### 4. Synthesis

The orchestrator synthesizes responses from multiple agents into a unified, coherent response:

```python
response = orchestrator.orchestrate(user_request, context)
# Uses multiple agents if needed, then synthesizes final answer
```

## Models Used

- **Orchestrator**: `claude-opus-4-6` (most capable for complex routing)
- **Summarization Agent**: `claude-sonnet-4-6` (balanced performance)
- **Settings & Context Agents**: `claude-haiku-4-5` (fast for specific tasks)

> Note: Never use dated model IDs. Always use the non-dated aliases for best compatibility.

## Accessibility Focus

This system demonstrates how multi-agent architecture can improve accessibility:

1. **Adaptive Responses**: Each agent considers user accessibility settings
2. **Multiple Formats**: Different agents can provide information in different formats
3. **Simplified Language**: Settings agent can trigger language simplification
4. **Audio Support**: Architecture supports audio descriptions and text-to-speech
5. **User Preferences**: All agents respect and adapt to user settings

## Extending the System

### Adding a New Specialist

```python
class NewSpecialistAgent:
    def __init__(self, client: Anthropic):
        self.client = client
        self.model = "claude-sonnet-4-6"

    def process(self, request: str, context: UserContext, instructions: str = "") -> str:
        # Implement your agent logic
        prompt = f"Your specialized prompt: {request}"
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

# Register the new agent
new_agent = NewSpecialistAgent(client)
orchestrator.register_specialist("new_agent", new_agent)
```

### Modifying the Orchestrator

The `analyze_request` method determines routing. You can:

1. Add new specialist agents to the list
2. Modify routing logic based on request patterns
3. Add confidence scoring to routing decisions
4. Implement caching for common patterns

## Performance Considerations

### Token Efficiency

- Routing analysis: ~200-400 tokens per request
- Specialist responses: ~500-1000 tokens each
- Synthesis: ~300-500 tokens
- **Total**: Typically 1000-2500 tokens per multi-agent interaction

### Optimization Tips

1. Cache routing decisions for similar requests
2. Use `claude-haiku-4-5` for simple routing tasks
3. Batch related requests to reduce redundant analysis
4. Monitor agent response times and optimize specialist selection

## Limitations and Future Work

### Current Limitations

- Context window size limits multi-turn conversations
- No persistent storage across sessions
- Routing decisions could be more sophisticated
- No feedback loop to improve routing over time

### Future Enhancements

1. **Persistent Context Storage**: Use vector databases for long-term memory
2. **Feedback Learning**: Learn routing patterns from user interactions
3. **Performance Optimization**: Predict which agents will be needed before routing
4. **Custom Agents**: Framework for user-defined specialist agents
5. **Tool Integration**: Allow agents to call external APIs and tools

## References

### Research & Inspiration

- Google Research AI accessibility work
- WCAG 2.1 accessibility guidelines
- Research on multimodal AI for accessibility
- Agent-based system design patterns

### Resources

- [Claude API Documentation](https://docs.anthropic.com/en/api/messages)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Accessibility Best Practices](https://www.anthropic.com/news/accessibility)

## License

This notebook is provided as part of the Claude Cookbooks repository.
