# 💬 Gemini Multi-turn Chat with Image Generation

A powerful Gradio-based chat interface for Google's Gemini API featuring multi-turn conversations, image generation, image analysis, and extensive customization options.

## ✨ Features

- **Multi-turn Conversations**: Full context retention across multiple exchanges
- **Image Generation**: Generate images directly from text prompts
- **Image Analysis**: Upload and analyze images with Gemini's vision capabilities
- **Model Selection**: Choose from multiple Gemini models (2.5 Pro, Flash, etc.)
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

### Image Generation
Simply ask Gemini to generate an image:
```
Generate an image of a sunset over mountains
```

### Image Analysis
1. Click "Upload Image" and select an image
2. Ask questions about the image:
```
What's in this image? Describe it in detail.
```

### Advanced Settings

Access the "Advanced Settings" accordion to customize:

- **System Prompt**: Set the assistant's behavior and personality
- **Temperature** (0.0-2.0): Control creativity (higher = more creative)
- **Top P** (0.0-1.0): Control randomness in token selection
- **Max Output Tokens**: Set maximum response length (1,024-1,000,000)
- **Thinking Budget**: Allocate tokens for internal reasoning (0-16,384)
- **Safety Settings**: Configure content filtering for:
  - Hate Speech
  - Harassment
  - Sexually Explicit content
  - Dangerous Content

### Model Configuration

You can customize available models by creating a `models.txt` file:

```txt
gemini-2.5-pro
gemini-flash-latest
gemini-2.5-flash-image-preview
gemini-2.5-flash
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

### Import Errors
If you encounter import errors:
```bash
pip install --upgrade google-genai gradio Pillow
```

## 🔗 Resources

- [Google AI Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [Gemini API Quickstart](https://ai.google.dev/gemini-api/docs/quickstart)
- [Get API Key](https://aistudio.google.com/app/apikey)
- [Gradio Documentation](https://www.gradio.app/docs)

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

## ⚠️ Important Notes

- Temporary image files are automatically cleaned up when the application exits
- Starting a new conversation resets the context and applies current settings
- Settings cannot be changed mid-conversation; start a new chat to apply changes
- Downloaded images are saved to temporary files that will be cleaned up on exit

## 💡 Tips

- Use descriptive prompts for better image generation results
- Experiment with temperature settings for different use cases
- Higher thinking budgets can improve reasoning for complex queries
- Use system prompts to maintain consistent assistant behavior throughout conversations
