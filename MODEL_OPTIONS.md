# AI Model Options for Speed Optimization

## Current Configuration
- **Default Model**: `gpt-4o-mini` (changed from `claude-haiku-4-5-20251001`)
- **Expected Speed Improvement**: 2-3x faster than Claude Haiku

## Available Models (Ranked by Speed)

### 1. 🚀 GPT-4o-mini (OpenAI) - **RECOMMENDED**
- **Model Name**: `"gpt-4o-mini"`
- **Speed**: Fastest option (typically 2-3x faster than Claude Haiku)
- **Quality**: Excellent for tool use and structured tasks
- **Cost**: Very affordable (~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens)
- **API Key**: Requires `OPENAI_API_KEY` environment variable
- **Best For**: Production use when speed is critical

### 2. Claude Haiku 3.5 (Anthropic)
- **Model Name**: `"claude-3-5-haiku-20241022"`
- **Speed**: Fast (slightly faster than Haiku 4.5)
- **Quality**: Good for tool use
- **Cost**: Similar to GPT-4o-mini
- **API Key**: Requires `ANTHROPIC_API_KEY` environment variable
- **Best For**: If you prefer Anthropic's models

### 3. Claude Haiku 4.5 (Anthropic) - Previous Default
- **Model Name**: `"claude-haiku-4-5-20251001"`
- **Speed**: Moderate (current baseline)
- **Quality**: Good
- **API Key**: Requires `ANTHROPIC_API_KEY` environment variable

### 4. Gemini Flash (Google) - Optional
- **Model Name**: `"gemini-1.5-flash"`
- **Speed**: Very fast
- **Quality**: Good for simple tasks
- **API Key**: Requires `GOOGLE_API_KEY` environment variable
- **Best For**: If you have Google Cloud credits

## How to Switch Models

### Option 1: Change Default in Code
Edit `app/agents/agent.py`:
```python
def create_betting_agent(
    model_name: str = "gpt-4o-mini",  # Change this line
    ...
)
```

### Option 2: Use Environment Variable
Set `MODEL_NAME` environment variable (if supported) or pass model_name when creating agent.

### Option 3: Test Different Models
```python
# Test GPT-4o-mini (fastest)
agent = create_betting_agent(model_name="gpt-4o-mini")

# Test Claude Haiku 3.5
agent = create_betting_agent(model_name="claude-3-5-haiku-20241022")

# Test Gemini Flash
agent = create_betting_agent(model_name="gemini-1.5-flash")
```

## Expected Latency Improvements

| Model | Expected Latency | vs Current |
|-------|-----------------|------------|
| GPT-4o-mini | **3-5 seconds** | 2-3x faster |
| Claude Haiku 3.5 | 5-7 seconds | 1.5-2x faster |
| Claude Haiku 4.5 | 10-11 seconds | Baseline |
| Gemini Flash | 4-6 seconds | 2x faster |

## Setup Instructions

### For GPT-4o-mini (Recommended):
1. Get OpenAI API key from https://platform.openai.com/api-keys
2. Set environment variable:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```
3. Restart server - model will automatically use GPT-4o-mini

### For Claude Haiku:
- Already configured if `ANTHROPIC_API_KEY` is set
- Change model_name to `"claude-3-5-haiku-20241022"` for older (faster) version

### For Gemini Flash:
1. Get Google API key from https://makersuite.google.com/app/apikey
2. Set environment variable:
   ```bash
   export GOOGLE_API_KEY="..."
   ```
3. Change model_name to `"gemini-1.5-flash"`

## Notes

- **Cached queries**: Will still be instant (22ms) regardless of model
- **Fresh queries**: Model speed directly impacts latency
- **Tool execution**: Same speed regardless of model (database queries are fast)
- **Quality**: All recommended models maintain good quality for tool use

## Recommendation

**Use GPT-4o-mini** for the best speed/quality/cost balance. It's specifically optimized for fast inference and tool use, making it ideal for this use case.

