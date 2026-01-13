# Visual Extraction Dependencies Installation

## ✅ Python Packages (Already Installed)

The following Python packages have been installed:
- ✅ `pdfplumber==0.11.4` - For table extraction
- ✅ `Pillow==11.0.0` - For image processing
- ✅ `pdf2image==1.17.0` - For PDF to image conversion
- ✅ `pytesseract==0.3.13` - For OCR (optional)

## ⚠️ Windows-Specific: Poppler Installation

**If you want to use GPT-4 Vision analysis** (chart/graph analysis), you need to install Poppler for Windows.

### Option 1: Install Poppler (Recommended for Vision Analysis)

1. **Download Poppler for Windows:**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases/
   - Download the latest release (e.g., `Release-23.11.0-0.zip`)
   - Extract the zip file to a location like `C:\poppler`

2. **Add to PATH:**
   - Open System Properties → Environment Variables
   - Add `C:\poppler\Library\bin` to your PATH
   - Or set it in your `.env` file:
     ```env
     POPPLER_PATH=C:\poppler\Library\bin
     ```

3. **Restart your backend** after adding to PATH

### Option 2: Skip Poppler (Tables Only)

If you **only need table extraction** (which doesn't require Poppler), you can skip this step. The system will:
- ✅ Extract tables from PDFs
- ✅ Include tables in RAG responses
- ❌ Skip chart/graph analysis with GPT-4 Vision

## Testing the Installation

After installing, try uploading a PDF again. The error should be resolved!

## Troubleshooting

### Still Getting "No module named 'pdfplumber'"

1. **Check your Python environment:**
   ```bash
   python -c "import pdfplumber; print('pdfplumber installed')"
   ```

2. **Make sure you're using the same Python environment as your backend:**
   - Check which Python your backend is using
   - Install packages in that environment

3. **Restart your backend server** after installing packages

### pdf2image Errors (if using Vision Analysis)

If you see errors about `pdf2image` not finding Poppler:
- Make sure Poppler is installed and in your PATH
- Or set `POPPLER_PATH` environment variable
- Restart your backend

### uvloop Error (Windows)

The `uvloop` error is **normal on Windows** - it's a Linux-only package. It won't affect functionality.

## What Works Without Poppler

Even without Poppler, you still get:
- ✅ **Table extraction** from PDFs
- ✅ **Text extraction** from PDFs
- ✅ **RAG with table data** included in responses
- ✅ **All core functionality**

You only need Poppler if you want:
- 🔍 **GPT-4 Vision chart analysis** (requires `ENABLE_VISION_ANALYSIS=true`)

## Next Steps

1. **Try uploading your PDF again** - it should work now!
2. **If you want vision analysis**, install Poppler (see above)
3. **Set `ENABLE_VISION_ANALYSIS=true`** in `.env` if you want chart analysis
