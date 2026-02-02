# 💬 Gemini Multi-turn Chat with RAG & Image Generation

A powerful Gradio-based chat interface for Google's Gemini API featuring multi-turn conversations, RAG-powered document analysis, image generation, and comprehensive token tracking.

## ✨ Features

### Core Capabilities
- **Multi-turn Conversations**: Full context retention across multiple exchanges with complete chat history export
- **RAG Document Analysis**: Upload and analyze documents (PDF, DOCX, TXT, JSON, CSV, MD, HTML, XML) with File Search
- **Grounding Sources**: See exactly which document chunks were used to generate responses with confidence scores
- **Image Generation**: Generate images directly from text prompts
- **Image Analysis**: Upload and analyze images with Gemini's vision capabilities
- **Token Tracking**: Real-time token counting for prompts, responses, and conversation history

### Advanced Features
- **Model Selection**: Choose from multiple Gemini models (2.5 Pro, Flash, etc.)
- **File Search Store Management**: List and delete persistent document stores to manage storage
- **Detailed Grounding Metadata**: View source relevance scores, chunk details, and grounding quality metrics
- **Chat History Export**: Export full conversations to Markdown with embedded images and token statistics
- **Advanced Configuration**: Control temperature, top-p, max tokens, and thinking budget
- **Safety Settings**: Customize content filtering for different harm categories
- **System Prompts**: Set custom system instructions for tailored responses
- **Auto-cleanup**: Temporary files are automatically cleaned up on exit

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- A Google AI API key ([Get one here](https://aistudio.google.com/app/apikey))

### Installation

1. Clone this repository:
```bash
git clone https://github.com/zakcali/gemini-multimodel-chat
cd gemini-multimodel-chat
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Set your API key as an environment variable:

**Linux/Mac:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set GEMINI_API_KEY=your-api-key-here
```

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

### Running the Application

```bash
python gemini-mm-chat.py
```

The Gradio interface will launch in your default browser, typically at `http://localhost:7860`.

## 📋 Requirements

Create a `requirements.txt` file with:

```
gradio
google-genai
Pillow
```

Install with:
```bash
pip install -r requirements.txt
```

## 🎮 Usage

### Basic Chat
1. Select a model from the dropdown menu
2. Type your message in the prompt box
3. Click "📤 Send" or press Enter

### Document Analysis (RAG)
1. Click the "📄 Document" tab
2. Upload a document (PDF, DOCX, TXT, JSON, CSV, MD, HTML, XML)
3. Ask questions about the document:
```
Summarize the main points of this document
```
4. View grounding sources to see which document chunks informed the response

### File Search Store Management

**Important**: File Search stores persist indefinitely until deleted. While uploaded files expire after 48 hours, the indexed data remains in the store.

#### List All Stores
1. Open "🗄️ File Search Store Management" accordion
2. Click "📋 List All Stores" to view:
   - Store names and display names
   - Creation timestamps
   - Total store count

#### Delete All Stores
1. Open "🗄️ File Search Store Management" accordion
2. Click "🗑️ Delete All Stores" to permanently remove:
   - All File Search stores
   - All indexed document data
   - Current session's store state

**Note**: This operation cannot be undone. Use it to clean up storage after completed projects.

### Image Generation
Simply ask Gemini to generate an image:
```
Generate an image of a sunset over mountains
```

### Image Analysis
1. Click the "🖼️ Image" tab and upload an image
2. Ask questions about the image:
```
What's in this image? Describe it in detail.
```

### Token Tracking
- **This Turn**: See tokens used in the current exchange (history + prompt + response)
- **Session Total**: Track cumulative token usage across the entire conversation
- Helps monitor API usage and optimize prompts

### Chat History Export
1. Click "📥 Generate Chat History File" at any time
2. Download a complete Markdown file with:
   - Full conversation history
   - Embedded images (as base64)
   - Token usage statistics
   - Model and system prompt configuration

### Advanced Settings

Access the "Advanced Settings" accordion to customize:

- **System Prompt**: Set the assistant's behavior and personality
- **Temperature** (0.0-2.0): Control creativity (higher = more creative)
- **Top P** (0.0-1.0): Control randomness in token selection
- **Max Output Tokens**: Set maximum response length (1,024-65,536)
- **Thinking Budget**: Allocate tokens for internal reasoning (-1 for dynamic, 0 to disable, or specific values like 1000, 2000, 8192)
- **Safety Settings**: Configure content filtering for:
  - Hate Speech
  - Harassment
  - Sexually Explicit content
  - Dangerous Content

### Model Configuration

You can customize available models by creating a `models.txt` file:

```txt
gemini-2.5-pro
gemini-2.5-flash
gemini-flash-latest
gemini-2.5-flash-image-preview
gemini-2.5-flash-lite-preview-09-2025
```

Place one model name per line. If the file is missing, default models will be used.

## 🔧 Configuration Options

### Safety Thresholds

- **BLOCK_NONE**: No blocking
- **BLOCK_ONLY_HIGH**: Block only high-probability harmful content
- **BLOCK_MEDIUM_AND_ABOVE**: Block medium and high-probability content
- **BLOCK_LOW_AND_ABOVE**: Block low, medium, and high-probability content

### Generation Parameters

- **Temperature**: Higher values (1.5-2.0) produce more creative outputs; lower values (0.3-0.7) are more focused
- **Top P**: Nucleus sampling parameter; 0.95 is a good default
- **Max Tokens**: Maximum length of response; adjust based on needs
- **Thinking Budget**: Tokens allocated for Gemini's internal reasoning process

### File Search & RAG

- Documents are uploaded to a persistent File Search store
- Stores persist indefinitely until explicitly deleted
- **Uploaded files expire after 48 hours**, but indexed data remains
- Use File Search Store Management to clean up unused stores
- Grounding sources show:
  - Search entry points with links to view all sources
  - Source relevance scores with confidence percentages
  - All retrieved chunks with expandable previews
  - Grounding quality metrics (support score, confidence)

## 📊 Grounding Sources Display

When using document analysis, the interface shows detailed grounding information:

1. **Search Entry Point**: Link to view all sources together
2. **Source Relevance Scores**: Confidence percentages for each source
3. **Retrieved Content**: All chunks used, with expandable previews
4. **Grounding Quality**: Support scores and active chunk counts

Example grounding display:
```
📚 Grounding Sources

🔗 [View All Sources Together](link)

🎯 Source Relevance Scores
1. document.pdf - 🎯 87.5% confidence

📖 Retrieved Content
📊 Total: 3 chunks from 1 documents

1. 📄 document.pdf
📍 Location: /path/to/file
📦 Chunks Retrieved: 3
  🔍 Chunk 1 (Relevance: 92%)
  [Click to expand]
```

## 🗄️ File Search Store Lifecycle

Understanding File Search storage behavior:

### Store Creation
- Stores are created automatically when you upload your first document
- One store per chat session (reused for multiple documents in same session)
- Stores persist indefinitely until deleted

### File Expiration
- Uploaded `File` objects expire after **48 hours**
- Indexed data in the store remains permanently
- You can continue querying indexed data after file expiration

### Store Management
**Best Practices:**
- Use "List All Stores" to audit existing stores
- Delete unused stores with "Delete All Stores" to free up storage
- Clean up stores after completing projects
- Starting a new conversation creates a fresh store if documents are uploaded

**Storage Cleanup Workflow:**
```
1. Export chat history (if needed for records)
2. Open File Search Store Management
3. Click "List All Stores" to review
4. Click "Delete All Stores" to clean up
5. Confirm deletion in the status message
```

## 📁 Project Structure

```
.
├── gemini-mm-chat.py    # Main application file
├── models.txt           # Model configuration (optional)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🐛 Troubleshooting

### API Key Issues
If you see "GEMINI_API_KEY environment variable not found":
- Ensure you've set the environment variable correctly
- Restart your terminal after setting the variable
- Check that the API key is valid

### Model Not Available
If a model isn't working:
- Verify the model name is correct
- Check that your API key has access to that model
- Try using a different model from the dropdown

### Document Upload Issues
- Ensure file format is supported (PDF, DOCX, TXT, JSON, CSV, MD, HTML, XML)
- Files with non-ASCII characters in names are automatically renamed for compatibility
- Check file size limits based on your API tier

### File Search Store Issues
- If stores accumulate, use "Delete All Stores" to clean up
- Stores from old sessions persist - clean them periodically
- Check store list before deleting to understand what will be removed

### Import Errors
If you encounter import errors:
```bash
pip install --upgrade google-genai gradio Pillow
```

## 🔗 Resources

- [Google AI Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [Gemini File Search Documentation](https://ai.google.dev/gemini-api/docs/file-search)
- [Gemini API Quickstart](https://ai.google.dev/gemini-api/docs/quickstart)
- [Get API Key](https://aistudio.google.com/app/apikey)
- [Gradio Documentation](https://www.gradio.app/docs)

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

## ⚠️ Important Notes

- Temporary files (images, documents, exports) are automatically cleaned up when the application exits
- File Search stores persist indefinitely and must be manually deleted
- Uploaded files expire after 48 hours, but indexed data remains in stores
- Starting a new conversation creates a new File Search store if documents are uploaded
- Settings cannot be changed mid-conversation; start a new chat to apply changes
- Token counting includes history tokens, prompt tokens, and response tokens separately
- Grounding sources are only displayed when File Search is active and documents are used

## 💡 Tips

### For Better Results
- Upload relevant documents before asking questions for RAG-powered responses
- Use descriptive prompts for better image generation results
- Experiment with temperature settings for different use cases
- Higher thinking budgets can improve reasoning for complex queries
- Use system prompts to maintain consistent assistant behavior throughout conversations

### For Document Analysis
- Upload multiple related documents to the same session for cross-document queries
- Check grounding sources to verify which parts of documents were used
- Use specific questions to target particular document sections
- Review confidence scores to assess response reliability

### For Token Management
- Monitor token usage to optimize API costs
- Export chat history before starting new conversations to preserve context
- Use thinking budget strategically for complex reasoning tasks
- Consider token counts when uploading large documents

### For Store Management
- Periodically list and delete unused File Search stores
- Clean up stores after completing projects to free storage
- Remember: stores persist indefinitely until you delete them
- Use "Delete All Stores" at the end of work sessions

## 🆕 Recent Updates

- ✅ **NEW**: Added File Search Store Management (list and delete stores)
- ✅ Added RAG document upload with File Search integration
- ✅ Enhanced grounding sources display with all chunks visible
- ✅ Added comprehensive token tracking (history + prompt + response)
- ✅ Implemented chat history export to Markdown with images
- ✅ Fixed Windows compatibility for non-ASCII filenames
- ✅ Added support for multiple document formats
- ✅ Improved grounding metadata parsing and display
- ✅ Updated code according to gradio 6.0;
1- theme is now a parameter for launch : demo.launch(theme=gr.themes.Default())

2- Those parameters are gone: show_copy_button=True, show_download_button=False, type="messages"

3- those parameter is enough for current code: chatbot = gr.Chatbot(label="Conversation", height=600, buttons=["copy"]) and
output_image = gr.Image(label="Latest Generated Image", height=400, visible=True)

## 🎯 Roadmap

- [ ] Individual store deletion (select specific stores)
- [ ] Store display names for easier identification
- [ ] File Search store usage statistics
- [ ] Automatic store cleanup after configurable time periods
- [ ] Multi-store queries for cross-project document searches
