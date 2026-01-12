# Qwen Model Comparison Setup

This guide explains how to use the Qwen model (via Together AI) for comparison with OpenAI.

## Setup

1. **Add Together AI API Key to `.env`**

   Create or update `.env` in the `market-outlook-rag` folder:

   ```env
   OPENAI_API_KEY=sk-your-openai-key-here
   TOGETHER_API_KEY=your-together-api-key-here
   TOGETHER_MODEL=Qwen/Qwen2.5-72B-Instruct
   ```

   The `TOGETHER_MODEL` is optional - it defaults to `Qwen/Qwen2.5-72B-Instruct` if not specified.

2. **Get Together AI API Key**

   - Sign up at https://together.ai
   - Get your API key from the dashboard
   - Add it to your `.env` file

## Usage

### Single Provider Mode

1. **Select Provider**: Use the dropdown to choose between:
   - **OpenAI (GPT-4o-mini)**: Default OpenAI model
   - **Together AI (Qwen2.5-72B)**: Qwen model via Together AI

2. **Ask Question**: Type your question and click "Ask"

### Comparison Mode

1. **Enable Comparison**: Check the "Compare providers" checkbox
2. **Ask Question**: Type your question and click "Compare"
3. **View Results**: See side-by-side comparison of:
   - OpenAI (GPT-4o-mini) response
   - Together AI (Qwen2.5-72B) response

Both responses will show:
- Answer
- Key points
- Citations with sources

## API Endpoints

### Single Provider
```
POST /ask
{
  "question": "Your question here",
  "top_k": 8,
  "provider": "openai" | "together"
}
```

### Comparison
```
POST /ask/compare
{
  "question": "Your question here",
  "top_k": 8
}
```

Returns responses from both providers in parallel.

## Notes

- Both providers use the same RAG retrieval system
- Citations are validated and enforced for both providers
- Comparison mode runs both providers in parallel for faster results
- The Together AI API is OpenAI-compatible, so it uses the same `openai` Python package
