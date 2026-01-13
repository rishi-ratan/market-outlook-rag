"""
Visual Data Extraction Module
Extracts tables, charts, and images from PDFs for enhanced RAG.
"""
import base64
import io
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
import pdfplumber
from pypdf import PdfReader
from PIL import Image
import pdf2image
from openai import OpenAI
import os

def extract_tables_from_pdf(pdf_path: str, page_num: int) -> List[Dict[str, Any]]:
    """
    Extract tables from a specific page of a PDF.
    Returns list of tables with their data and metadata.
    """
    tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num <= len(pdf.pages):
                page = pdf.pages[page_num - 1]  # pdfplumber uses 0-indexed
                page_tables = page.extract_tables()
                
                for idx, table in enumerate(page_tables):
                    if table and len(table) > 0:
                        # Convert table to structured format
                        table_data = {
                            "table_id": f"p{page_num}_t{idx}",
                            "page": page_num,
                            "rows": table,
                            "row_count": len(table),
                            "col_count": len(table[0]) if table else 0,
                            "type": "table"
                        }
                        tables.append(table_data)
    except Exception as e:
        print(f"Error extracting tables from page {page_num}: {e}")
    
    return tables

def extract_images_from_pdf(pdf_path: str, page_num: int) -> List[Dict[str, Any]]:
    """
    Extract images from a specific page of a PDF.
    Returns list of images with base64-encoded data.
    """
    images = []
    try:
        reader = PdfReader(pdf_path)
        if page_num <= len(reader.pages):
            page = reader.pages[page_num - 1]
            
            if '/XObject' in page.get('/Resources', {}):
                xObject = page['/Resources']['/XObject'].get_object()
                
                for idx, obj in xObject.items():
                    if xObject[obj]['/Subtype'] == '/Image':
                        try:
                            size = (xObject[obj]['/Width'], xObject[obj]['/Height'])
                            data = xObject[obj].get_data()
                            
                            # Try to decode image
                            img = Image.open(io.BytesIO(data))
                            buffered = io.BytesIO()
                            img.save(buffered, format="PNG")
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            
                            image_data = {
                                "image_id": f"p{page_num}_i{idx}",
                                "page": page_num,
                                "width": size[0],
                                "height": size[1],
                                "format": img.format or "PNG",
                                "base64": img_base64,
                                "type": "image"
                            }
                            images.append(image_data)
                        except Exception as e:
                            print(f"Error processing image {idx} on page {page_num}: {e}")
    except Exception as e:
        print(f"Error extracting images from page {page_num}: {e}")
    
    return images

def extract_page_as_image(pdf_path: str, page_num: int, dpi: int = 200) -> Optional[str]:
    """
    Convert a PDF page to an image and return as base64.
    Useful for chart/graph analysis with vision models.
    """
    try:
        images = pdf2image.convert_from_path(pdf_path, dpi=dpi, first_page=page_num, last_page=page_num)
        if images:
            img = images[0]
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            return img_base64
    except Exception as e:
        print(f"Error converting page {page_num} to image: {e}")
    
    return None

def analyze_chart_with_vision(image_base64: str, api_key: str, page_num: int) -> Optional[Dict[str, Any]]:
    """
    Use GPT-4 Vision to analyze a chart/graph and extract structured data.
    """
    try:
        client = OpenAI(api_key=api_key)
        
        # Use environment variable to select vision model, default to gpt-4o-mini for cost savings
        vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
        # Available models: "gpt-4o", "gpt-4o-mini", "gpt-4-turbo"
        # gpt-4o-mini: Cheapest, good quality (~$0.15 per 1M input tokens)
        # gpt-4o: Best quality, more expensive (~$2.50 per 1M input tokens)
        # gpt-4-turbo: Good balance, moderate cost
        
        response = client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this chart/graph and extract:
1. Chart type (bar, line, pie, etc.)
2. Title and axis labels
3. Key data points (values, categories, trends)
4. Summary of insights
5. Any numerical data in a structured format (JSON if possible)

Return your analysis in JSON format with keys: chart_type, title, axes, data_points, insights, structured_data."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        analysis_text = response.choices[0].message.content
        
        # Try to parse JSON from response
        try:
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in analysis_text:
                json_start = analysis_text.find("```json") + 7
                json_end = analysis_text.find("```", json_start)
                analysis_text = analysis_text[json_start:json_end].strip()
            elif "```" in analysis_text:
                json_start = analysis_text.find("```") + 3
                json_end = analysis_text.find("```", json_start)
                analysis_text = analysis_text[json_start:json_end].strip()
            
            analysis_data = json.loads(analysis_text)
        except:
            # If JSON parsing fails, return as text
            analysis_data = {
                "raw_analysis": analysis_text,
                "chart_type": "unknown",
                "title": "",
                "axes": {},
                "data_points": [],
                "insights": analysis_text,
                "structured_data": {}
            }
        
        return {
            "page": page_num,
            "type": "chart_analysis",
            "analysis": analysis_data,
            "model": "gpt-4o"
        }
    except Exception as e:
        print(f"Error analyzing chart with vision API: {e}")
        return None

def extract_visual_data_from_pdf(pdf_path: str, page_num: int, use_vision: bool = False, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract all visual data from a specific page: tables, images, and optionally chart analysis.
    """
    visual_data = {
        "page": page_num,
        "tables": [],
        "images": [],
        "chart_analyses": []
    }
    
    # Extract tables
    tables = extract_tables_from_pdf(pdf_path, page_num)
    visual_data["tables"] = tables
    
    # Extract images
    images = extract_images_from_pdf(pdf_path, page_num)
    visual_data["images"] = images
    
    # If vision analysis is enabled and API key provided, analyze charts
    if use_vision and api_key:
        page_image = extract_page_as_image(pdf_path, page_num)
        if page_image:
            chart_analysis = analyze_chart_with_vision(page_image, api_key, page_num)
            if chart_analysis:
                visual_data["chart_analyses"].append(chart_analysis)
    
    return visual_data

def format_table_as_text(table_data: Dict[str, Any]) -> str:
    """
    Convert a table to a readable text format for inclusion in chunks.
    """
    if not table_data.get("rows"):
        return ""
    
    rows = table_data["rows"]
    text_lines = [f"Table on page {table_data['page']}:"]
    
    for row in rows:
        if row:
            # Filter out None values and convert to strings
            row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
            text_lines.append(row_text)
    
    return "\n".join(text_lines)

def format_chart_analysis_as_text(analysis: Dict[str, Any]) -> str:
    """
    Convert chart analysis to text format for inclusion in chunks.
    """
    if not analysis or not analysis.get("analysis"):
        return ""
    
    analysis_data = analysis["analysis"]
    text_lines = [f"Chart analysis on page {analysis['page']}:"]
    
    if isinstance(analysis_data, dict):
        if analysis_data.get("title"):
            text_lines.append(f"Title: {analysis_data['title']}")
        if analysis_data.get("chart_type"):
            text_lines.append(f"Chart Type: {analysis_data['chart_type']}")
        if analysis_data.get("insights"):
            text_lines.append(f"Insights: {analysis_data['insights']}")
        if analysis_data.get("data_points"):
            text_lines.append(f"Key Data Points: {json.dumps(analysis_data['data_points'], indent=2)}")
    else:
        text_lines.append(str(analysis_data))
    
    return "\n".join(text_lines)
