import os
import gradio as gr
from google import genai
from google.genai import errors, types
from PIL import Image
from io import BytesIO
import tempfile
import atexit

# --- Global list to track temporary files ---
temp_files_to_clean = []

# --- Function to perform cleanup ---
def cleanup_temp_files():
    """Iterates through the global list and deletes the tracked files."""
    print(f"Cleaning up {len(temp_files_to_clean)} temporary files...")
    for file_path in temp_files_to_clean:
        try:
            os.remove(file_path)
            print(f"  - Removed: {file_path}")
        except FileNotFoundError:
            print(f"  - Not found (already gone): {file_path}")
        except Exception as e:
            print(f"  - Error removing {file_path}: {e}")

# --- Register the cleanup function to run on script exit ---
atexit.register(cleanup_temp_files)

# --- Function to read the model list from a file ---
def load_models(filepath="models.txt"):
    """Loads the list of models from a text file, with a fallback default list."""
    default_models = [
        "gemini-2.5-pro",
        "gemini-pro-vision",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
    ]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            models = [line.strip() for line in f if line.strip()]
            if not models:
                print(f"Warning: '{filepath}' was empty. Using default model list.")
                return default_models
            return models
    except FileNotFoundError:
        print(f"Warning: '{filepath}' not found. Using default model list.")
        return default_models

# --- Configuration ---
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("CRITICAL: GEMINI_API_KEY environment variable not found.")

# --- Initialize the Gemini Client ONCE ---
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    client = None

# --- Mappings for Safety Settings ---
BLOCK_THRESHOLD_MAP = {
    "BLOCK_NONE": types.HarmBlockThreshold.BLOCK_NONE,
    "BLOCK_ONLY_HIGH": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    "BLOCK_MEDIUM_AND_ABOVE": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    "BLOCK_LOW_AND_ABOVE": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
}
HARM_CATEGORY_MAP = {
    "Hate Speech": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    "Harassment": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    "Sexually Explicit": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    "Dangerous Content": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
}

# --- Core Logic using Gemini Chat API ---
def chat_with_gemini(
    prompt, source_image, chat_session_state, model_choice, system_prompt,
    temperature, max_tokens, thinking_budget, top_p,
    hate_speech, harassment, sexually_explicit, dangerous_content
):
    """
    Handles multi-turn conversation using Gemini's Chat API.
    """
    if not client:
        return [], "", "❌ Error: Gemini Client failed to initialize. Check API key and logs.", gr.update(visible=False), None, chat_session_state
    
    if not prompt or not prompt.strip():
        return [], "", "⚠️ Please enter a prompt.", gr.update(visible=False), None, chat_session_state

    # Create a new chat session if one doesn't exist
    if chat_session_state is None:
        if not model_choice:
             error_message = "❌ Error: No model selected from the dropdown."
             return [{"role": "assistant", "content": error_message}], "", error_message, gr.update(visible=False), None, chat_session_state
        
        try:
            print(f"Starting new chat session with model: {model_choice}, Temp: {temperature}, Top P: {top_p}, Max Tokens: {max_tokens}, Thinking Budget: {thinking_budget}")
            
            # Construct safety settings from UI
            safety_settings = [
                types.SafetySetting(category=HARM_CATEGORY_MAP["Hate Speech"], threshold=BLOCK_THRESHOLD_MAP[hate_speech]),
                types.SafetySetting(category=HARM_CATEGORY_MAP["Harassment"], threshold=BLOCK_THRESHOLD_MAP[harassment]),
                types.SafetySetting(category=HARM_CATEGORY_MAP["Sexually Explicit"], threshold=BLOCK_THRESHOLD_MAP[sexually_explicit]),
                types.SafetySetting(category=HARM_CATEGORY_MAP["Dangerous Content"], threshold=BLOCK_THRESHOLD_MAP[dangerous_content]),
            ]

            # Build config with generation settings
            config = types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=int(max_tokens),
                thinking_config=types.ThinkingConfig(thinking_budget=int(thinking_budget)),
                safety_settings=safety_settings
            )
            
            # Add system instruction if provided
            if system_prompt and system_prompt.strip():
                config.system_instruction = system_prompt

            # Create the chat session with config
            chat_session_state = client.chats.create(
                model=model_choice,
                config=config
            )
            
        except Exception as e:
            error_message = f"❌ Error creating chat session: {e}"
            return ([{"role": "assistant", "content": error_message}], "", error_message, gr.update(visible=False), None, chat_session_state)

    try:
        message_parts = [prompt]
        if source_image:
            message_parts.append(source_image)
        
        response = chat_session_state.send_message(message_parts)
        
        generated_image_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data is not None:
                generated_image_data = part.inline_data.data
                break
        
        history = chat_session_state.get_history()
        
        chatbot_history = []
        for message in history:
            role = "assistant" if message.role == "model" else message.role
            content_text = ""
            for part in message.parts:
                if part.text:
                    content_text += part.text
                elif role == 'user' and hasattr(part, 'inline_data') and part.inline_data:
                    content_text += "\n🖼️ [Image uploaded]"
            
            if content_text.strip():
                chatbot_history.append({"role": role, "content": content_text})
        
        if generated_image_data is not None:
            result_image = Image.open(BytesIO(generated_image_data))
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                output_filepath = temp_file.name
                result_image.save(output_filepath)
            
            temp_files_to_clean.append(output_filepath)
            print(f"Created and tracking temp file: {output_filepath}")
            
            if chatbot_history and chatbot_history[-1]['role'] == 'assistant':
                 chatbot_history[-1]['content'] += "\n\n🖼️ [Image generated - see below]"
            
            return (
                chatbot_history, "", "✅ Image generated successfully!",
                gr.update(visible=True, value=output_filepath), output_filepath, chat_session_state
            )
        else:
            return (
                chatbot_history, "", "✅ Response received.",
                gr.update(visible=False), None, chat_session_state
            )
    
    except errors.APIError as e:
        error_message = f"❌ API Error ({e.code}): {e.message}"
        current_history = [{"role": "assistant", "content": error_message}]
        return current_history, "", error_message, gr.update(visible=False), None, chat_session_state
    
    except Exception as e:
        error_message = f"❌ Unexpected error: {e}"
        current_history = [{"role": "assistant", "content": error_message}]
        return current_history, "", error_message, gr.update(visible=False), None, chat_session_state

def new_conversation():
    """Resets the chat session and clears all UI elements."""
    return [], "", "🔄 New conversation started.", gr.update(visible=False), None, None

# --- Load external configuration before building UI ---
model_list = load_models()
default_model = model_list[0] if model_list else None
safety_threshold_choices = list(BLOCK_THRESHOLD_MAP.keys())

# --- Gradio User Interface ---
with gr.Blocks(theme=gr.themes.Soft(), title="💬 Gemini Multi-turn Chat") as demo:
    gr.Markdown("# 💬 Gemini Multi-turn Chat with Image Generation")
    gr.Markdown("Chat with Gemini using the official Chat API! Configure model settings, generate images, analyze them, or have conversations with full context retention.")
    
    chat_session = gr.State(None)
    
    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="Conversation", height=600, show_copy_button=True,
                type="messages",
                avatar_images=(None, "https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690345.svg")
            )
            output_image = gr.Image(label="Latest Generated Image", height=400, show_download_button=False, visible=True)
            download_btn = gr.DownloadButton(label="💾 Download Image", visible=False)
        
        with gr.Column(scale=1):
            model_choice = gr.Dropdown(
               label="Choose a Model", choices=model_list, value=default_model
            )
            input_image = gr.Image(type="pil", label="Upload Image (Optional)", height=200)
            prompt_box = gr.Textbox(
                label="Your Message",
                placeholder="Ask questions, request images, or analyze uploaded images...",
                lines=8
            )
            
            with gr.Accordion("Advanced Settings", open=False):
                system_prompt_box = gr.Textbox(
                    label="System Prompt",
                    placeholder="e.g., You are a helpful and witty assistant.",
                    lines=3
                )
                temperature_slider = gr.Slider(
                    minimum=0.0, maximum=2.0, value=1.0, step=0.1,
                    label="Temperature (Creativity)"
                )
                top_p_slider = gr.Slider(
                    minimum=0.0, maximum=1.0, value=0.95, step=0.05,
                    label="Top P"
                )
                max_tokens_slider = gr.Slider(
                    minimum=1024, maximum=1000000, value=128000, step=1024,
                    label="Max Output Tokens"
                )
                thinking_budget_slider = gr.Slider(
                    minimum=0, maximum=16384, value=8192, step=256,
                    label="Thinking Budget (Tokens)"
                )
                gr.Markdown("#### Safety Settings")
                hate_speech_dd = gr.Dropdown(label="Hate Speech", choices=safety_threshold_choices, value="BLOCK_NONE")
                harassment_dd = gr.Dropdown(label="Harassment", choices=safety_threshold_choices, value="BLOCK_NONE")
                sexually_explicit_dd = gr.Dropdown(label="Sexually Explicit", choices=safety_threshold_choices, value="BLOCK_NONE")
                dangerous_content_dd = gr.Dropdown(label="Dangerous Content", choices=safety_threshold_choices, value="BLOCK_NONE")


            with gr.Row():
                send_btn = gr.Button("📤 Send", variant="primary", scale=2)
                clear_input_btn = gr.Button("🗑️ Clear Input", scale=1)
            
            status_box = gr.Markdown("")
            gr.Markdown("---")
            new_chat_btn = gr.Button("🔄 New Conversation", variant="stop")
            gr.Markdown("""
            ### Tips:
            - A new conversation uses the currently selected model and advanced settings.
            - To change settings mid-chat, start a new conversation.
            """)
    
    def send_message(
        prompt, image, session, model, system_prompt, temp, top_p, tokens, thinking_budget,
        hate, harass, sexual, dangerous
    ):
        result = chat_with_gemini(
            prompt, image, session, model, system_prompt, temp, tokens, thinking_budget, top_p,
            hate, harass, sexual, dangerous
        )
        return result
    
    inputs_list = [
        prompt_box, input_image, chat_session, model_choice, system_prompt_box, 
        temperature_slider, top_p_slider, max_tokens_slider, thinking_budget_slider,
        hate_speech_dd, harassment_dd, sexually_explicit_dd, dangerous_content_dd
    ]
    outputs_list = [chatbot, prompt_box, status_box, download_btn, output_image, chat_session]

    send_btn.click(
        fn=send_message,
        inputs=inputs_list,
        outputs=outputs_list
    ).then(fn=lambda: None, outputs=[input_image])
    
    prompt_box.submit(
        fn=send_message,
        inputs=inputs_list,
        outputs=outputs_list
    ).then(fn=lambda: None, outputs=[input_image])
    
    clear_input_btn.click(
        fn=lambda: ("", None, "✏️ Input cleared."),
        outputs=[prompt_box, input_image, status_box],
        queue=False
    )
    
    new_chat_btn.click(
        fn=new_conversation,
        outputs=[chatbot, prompt_box, status_box, download_btn, output_image, chat_session]
    )

if __name__ == "__main__":
    print("Launching Gradio interface with Gemini Chat API... Press Ctrl+C to exit.")
    print("To customize the model list, create a file named 'models.txt' with one model name per line.")
    print("Temporary files for this session will be cleaned up automatically on exit.")
    demo.launch()