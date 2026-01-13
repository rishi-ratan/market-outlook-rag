# Vision Analysis Setup Guide

This guide explains how to enable GPT-4 Vision for chart and graph analysis in the RAG system.

## Overview

The visual extraction system can analyze charts and graphs from PDFs using GPT-4 Vision models. This provides deeper insights into visual data that text extraction alone cannot capture.

## Quick Setup

### 1. Enable Vision Analysis

Add to your `.env` file:

```env
ENABLE_VISION_ANALYSIS=true
OPENAI_VISION_MODEL=gpt-4o-mini
```

### 2. Choose Your Vision Model

**Recommended Models (in order of cost-effectiveness):**

1. **`gpt-4o-mini`** (Recommended for most use cases)
   - Cost: ~$0.15 per 1M input tokens
   - Quality: Good for most chart analysis tasks
   - Speed: Fast
   - **Best balance of cost and quality**

2. **`gpt-4o`** (Best quality)
   - Cost: ~$2.50 per 1M input tokens
   - Quality: Excellent, best for complex charts
   - Speed: Fast
   - **Use when you need the highest accuracy**

3. **`gpt-4-turbo`** (Alternative)
   - Cost: ~$1.00 per 1M input tokens
   - Quality: Very good
   - Speed: Moderate
   - **Good middle ground**

### 3. Example `.env` Configuration

```env
# Required
OPENAI_API_KEY=sk-your-key-here
TOGETHER_API_KEY=your-together-key-here

# Vision Analysis (Optional)
ENABLE_VISION_ANALYSIS=true
OPENAI_VISION_MODEL=gpt-4o-mini

# Other settings
TOGETHER_MODEL=Qwen/Qwen2.5-72B-Instruct
OPENAI_MODEL=gpt-4o-mini
```

## How It Works

1. **During Document Processing:**
   - When `ENABLE_VISION_ANALYSIS=true`, each PDF page is converted to an image
   - The image is sent to GPT-4 Vision for analysis
   - Chart insights are extracted and stored alongside text chunks

2. **In Responses:**
   - Visual data (tables and chart analyses) are automatically included in answers
   - Tables are displayed in the UI
   - Chart analyses show insights, data points, and trends

## Cost Considerations

**Vision analysis adds cost because:**
- Each page image needs to be processed by GPT-4 Vision
- Images are base64-encoded and sent as part of the API request
- Processing time increases (though still reasonable)

**Cost Estimation (per document):**
- 50-page document with `gpt-4o-mini`: ~$0.10-0.30
- 50-page document with `gpt-4o`: ~$1.50-4.00
- Most documents: 20-100 pages

**Recommendation:** Start with `gpt-4o-mini` - it provides excellent results at a fraction of the cost.

## Qwen Model on TogetherAI

**Important:** Qwen models on TogetherAI do **NOT** support vision/image analysis. They are text-only models.

- ✅ **Qwen is great for:** Text generation, Q&A, reasoning
- ❌ **Qwen cannot:** Analyze images, charts, or graphs

**For vision analysis, you must use OpenAI models:**
- `gpt-4o-mini` (recommended)
- `gpt-4o` (best quality)
- `gpt-4-turbo` (alternative)

## Usage

### Enable for New Documents

1. Set `ENABLE_VISION_ANALYSIS=true` in `.env`
2. Upload a new document through the UI
3. The document will be processed with vision analysis

### Enable for Existing Documents

1. Set `ENABLE_VISION_ANALYSIS=true` in `.env`
2. Delete the document from the UI
3. Re-upload the document
4. It will be reprocessed with vision analysis

### Disable Vision Analysis

Set `ENABLE_VISION_ANALYSIS=false` or remove the variable from `.env`

## What Gets Extracted

When vision analysis is enabled, the system extracts:

1. **Tables:** Already extracted via `pdfplumber` (no vision needed)
2. **Chart Analysis:**
   - Chart type (bar, line, pie, etc.)
   - Title and axis labels
   - Key data points and values
   - Trends and insights
   - Structured numerical data

## Troubleshooting

### Vision Analysis Not Working

1. **Check API Key:**
   ```bash
   # Verify your OpenAI API key has access to vision models
   # Check at: https://platform.openai.com/api-keys
   ```

2. **Check Model Availability:**
   - Ensure your OpenAI account has access to the selected model
   - Some models may require API access approval

3. **Check Logs:**
   - Look for errors in the backend console
   - Check if vision analysis is being called

### High Costs

- Switch to `gpt-4o-mini` (much cheaper)
- Disable vision for documents without many charts
- Process only specific pages if needed

## Best Practices

1. **Start with `gpt-4o-mini`** - It's 16x cheaper than `gpt-4o` and works great
2. **Enable selectively** - Only enable for documents with important charts/graphs
3. **Monitor costs** - Check your OpenAI usage dashboard regularly
4. **Test first** - Process a small document first to estimate costs

## Example Output

When vision analysis is enabled, you'll see in responses:

```
Chart Analysis:
Page 15
Title: Private Market Performance Trends
Type: Line Chart
Insights: Shows steady growth in private equity returns over 5 years...
Key Data Points:
- 2020: 12.5%
- 2021: 15.2%
- 2022: 18.7%
```

This provides much richer context than text extraction alone!
