# Setting Environment Variables in LangSmith

To add environment variables to your LangSmith deployment without pushing them to GitHub:

## Method 1: LangSmith UI (Recommended)

1. **Go to your LangSmith project/deployment settings:**
   - Navigate to your LangGraph deployment in LangSmith
   - Look for "Environment Variables" or "Secrets" section
   - This is usually in the deployment configuration or project settings

2. **Add your environment variables:**
   - Click "Add Environment Variable" or "Add Secret"
   - Add each variable one by one:

   **Required Variables:**
   ```
   OPTICODDS_API_KEY=f8a621e8-2583-4e97-a769-e70c99acdb85
   ANTHROPIC_API_KEY=your-anthropic-api-key-here
   TAVILY_API_KEY=your-tavily-api-key-here (optional)
   ```

3. **Save and redeploy:**
   - Save the environment variables
   - Trigger a new deployment

## Method 2: LangGraph CLI (if available)

If you're using LangGraph CLI, you can set environment variables:

```bash
langgraph deploy --env-file .env
```

Or set them individually:
```bash
langgraph deploy \
  --env OPTICODDS_API_KEY=f8a621e8-2583-4e97-a769-e70c99acdb85 \
  --env ANTHROPIC_API_KEY=your-key \
  --env TAVILY_API_KEY=your-key
```

## Method 3: langgraph.json Configuration

You can also reference environment variables in your `langgraph.json`:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./app/agents/agent.py:agent"
  },
  "env": ".env"
}
```

But make sure `.env` is in `.gitignore` and the variables are set in LangSmith's UI.

## Current Required Variables

Based on your codebase, these are the environment variables needed:

1. **OPTICODDS_API_KEY** (Required)
   - Default is set in config, but can be overridden
   - Current default: `f8a621e8-2583-4e97-a769-e70c99acdb85`

2. **ANTHROPIC_API_KEY** (Required)
   - Needed for Claude model access
   - Get from: https://console.anthropic.com/

3. **TAVILY_API_KEY** (Optional)
   - Only needed if you want web search functionality
   - Get from: https://tavily.com/
   - The agent will work without it, but web search won't be available

## Important Notes

- **Never commit `.env` files to GitHub**
- Always add `.env` to `.gitignore`
- Use LangSmith's environment variable UI for production deployments
- Environment variables set in LangSmith take precedence over defaults in code

