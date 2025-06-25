# Ad Script Generator Agent for AdScribe.AI

This directory contains the Ad Script Generator Agent implementation that replaces the n8n workflow for intelligent ad script generation and general query processing using modular nodes and dynamic classification.

## Overview

The Ad Script Generator Agent provides:

1. **Dynamic Text Classification**: Automatically classifies user queries using configurable classification classes
2. **Ad Script Generation**: Uses best-performing ad analysis data to generate new ad scripts in Roman Urdu
3. **General Query Processing**: Handles general questions and conversations using OpenAI GPT models
4. **Modular Node Architecture**: Separate node files for better maintainability and extensibility

## Architecture

### Agent State
The agent maintains state through the `AgentState` TypedDict which includes:
- `user_message`: The current user query
- `previous_messages`: Chat history for context
- `ad_analyses`: Best performing ad analysis data
- `classification`: Query classification result
- `final_response`: Generated response
- `error`: Any error information

### Workflow Nodes

The agent uses separate node classes for better modularity:

1. **TextClassifierNode** (`text_classifier_node.py`): Dynamically classifies user queries based on configurable class definitions
2. **AdScriptGeneratorNode** (`ad_script_generator_node.py`): Generates ad scripts using the Urdu prompt template and best ad data
3. **GeneralResponseNode** (`general_response_node.py`): Handles general queries with OpenAI

### Default Classification Classes

- **ad_script**: "If user wants to write new ad speech or video script or text but not code."
- **default**: "it is default category all remaining query should lie under this category"

### Routing Logic

The agent uses conditional routing based on:
- Query classification result
- Availability of ad analysis data

For ad script generation, both the correct classification AND ad analysis data must be available.

## Usage

### Basic Usage

```python
from app.core.AI_Agent.Agent.Ad_Script_Generator_Agent import ad_script_generator_agent

# Process a request with default classification
response = await ad_script_generator_agent.process_request(
    user_message="Generate a new ad script for perfume",
    previous_messages=[],
    ad_analyses=ad_data
)

# Create agent with custom classification classes
from app.core.AI_Agent.Agent.Ad_Script_Generator_Agent import AdScriptGeneratorAgent

custom_classes = {
    "ad_script": "If user wants to write new ad speech or video script or text but not code.",
    "analytics": "If user asks about metrics or performance data",
    "default": "it is default category all remaining query should lie under this category"
}

custom_agent = AdScriptGeneratorAgent(custom_classes)
response = await custom_agent.process_request(user_message="Show me ROAS data")

# Update classification classes dynamically
custom_agent.update_classification_classes(new_classes)
```

### Integration with Webhook

The agent is integrated into the webhook endpoint at `Backend/app/api/v1/endpoints/webhook.py` and replaces the previous n8n webhook calls.

## Ad Script Generation

When generating ad scripts, the agent uses the following structure (in Roman Urdu):

1. **Hook (5 seconds)**: Attention-grabbing opening with power words
2. **Interest & Desire**: Product benefits and packaging highlights
3. **Risk Reversal**: Money-back guarantee
4. **Call to Action**: Clear purchase instruction

### Required Data

For ad script generation, the following data from the best performing ad is used:
- AD TITLE
- ROAS (Return on Ad Spend)
- CTR (Click Through Rate)
- Conversion Volume
- Revenue
- Audio Description
- Video Description

## Configuration

### Environment Variables

Ensure the following environment variable is set:
- `OPENAI_API_KEY`: Your OpenAI API key

### Dependencies

The agent requires:
- `langgraph==0.4.7`
- `openai==1.82.0`

## Testing

Run the test script to validate functionality:

```bash
cd Backend/app/core/AI_Agent/Agent
python test_ad_script_generator_agent.py
```

## Error Handling

The agent includes comprehensive error handling:
- Classification errors default to "general" processing
- Ad script generation errors return helpful error messages
- General response errors are logged and return fallback messages

## Logging

The agent uses Python's logging module with the logger name `__name__` for debugging and monitoring.

## Migration from n8n

This agent completely replaces the previous n8n workflow with the following benefits:
- No external dependency on n8n
- Better error handling and logging
- More maintainable code
- Faster response times
- Better integration with the existing codebase

## Future Enhancements

Potential improvements:
- Add more sophisticated classification with multiple categories
- Implement conversation memory for better context
- Add support for multiple languages
- Include A/B testing for different prompt templates 