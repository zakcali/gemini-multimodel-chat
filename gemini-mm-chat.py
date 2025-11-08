import os
import gradio as gr
from google import genai
from google.genai import errors, types
from PIL import Image
from io import BytesIO
import tempfile
import atexit
import base64
from datetime import datetime

# --- Global list to track temporary files ---
temp_files_to_clean = []

def cleanup_temp_files():
    print(f"Cleaning up {len(temp_files_to_clean)} temporary files...")
    for file_path in temp_files_to_clean:
        try:
            os.remove(file_path)
            print(f"  - Removed: {file_path}")
        except FileNotFoundError:
            print(f"  - Not found (already gone): {file_path}")
        except Exception as e:
            print(f"  - Error removing {file_path}: {e}")

atexit.register(cleanup_temp_files)

def load_models(filepath="models.txt"):
    default_models = [
        "gemini-2.5-pro",
        "gemini-flash-latest",
        "gemini-2.5-flash-image-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite-preview-09-2025",
    ]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            models = [line.strip() for line in f if line.strip()]
            return models or default_models
    except FileNotFoundError:
        return default_models

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("CRITICAL: GEMINI_API_KEY environment variable not found.")

try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    client = None

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

def format_token_info(usage_metadata, history_tokens=None):
    if usage_metadata is None:
        return ""
    info_parts = []
    if history_tokens is not None:
        info_parts.append(f"📊 **History**: {history_tokens} tokens")
    if hasattr(usage_metadata, 'prompt_token_count'):
        info_parts.append(f"📝 **Prompt**: {usage_metadata.prompt_token_count} tokens")
    if hasattr(usage_metadata, 'candidates_token_count'):
        info_parts.append(f"💬 **Response**: {usage_metadata.candidates_token_count} tokens")
    if hasattr(usage_metadata, 'total_token_count'):
        info_parts.append(f"🔢 **Total**: {usage_metadata.total_token_count} tokens")
    return " | ".join(info_parts) if info_parts else ""

def export_chat_to_markdown(chat_session_state, token_info_state, model_choice, system_prompt):
    if not chat_session_state:
        return None
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_content = f"# Gemini Chat History\n\n"
        md_content += f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md_content += f"**Model:** {model_choice}\n\n"
        if system_prompt and system_prompt.strip():
            md_content += f"**System Prompt:**\n```\n{system_prompt}\n```\n\n"
        md_content += "---\n\n"
        history = chat_session_state.get_history()
        for idx, message in enumerate(history, 1):
            role = "🤖 **Assistant**" if message.role == "model" else "👤 **User**"
            md_content += f"## Message {idx} - {role}\n\n"
            for part in message.parts:
                if part.text:
                    md_content += f"{part.text}\n\n"
                elif hasattr(part, "inline_data") and part.inline_data:
                    img_data = part.inline_data.data
                    img_base64 = base64.b64encode(img_data).decode()
                    mime_type = part.inline_data.mime_type or "image/png"
                    md_content += f"![Image](data:{mime_type};base64,{img_base64})\n\n"
            md_content += "---\n\n"
        if token_info_state:
            md_content += "## 📊 Token Usage Summary\n\n"
            md_content += f"- **Total Prompt Tokens:** {token_info_state.get('total_prompt_tokens', 0)}\n"
            md_content += f"- **Total Response Tokens:** {token_info_state.get('total_response_tokens', 0)}\n"
            md_content += f"- **Total Tokens:** {token_info_state.get('total_tokens', 0)}\n\n"
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_gemini_chat_{timestamp}.md", mode="w", encoding="utf-8") as temp_file:
            output_filepath = temp_file.name
            temp_file.write(md_content)
        temp_files_to_clean.append(output_filepath)
        return output_filepath
    except Exception as e:
        print(f"Error exporting chat history: {e}")
        return None


# --- Function for download file ---
def generate_chat_history_file(chat_session, token_info, model_choice, system_prompt):
    """Generate chat history markdown file and show in gr.File component."""
    if not chat_session:
        print("No active chat session to export")
        return None
    filepath = export_chat_to_markdown(chat_session, token_info, model_choice, system_prompt)
    if filepath:
        print(f"Chat history export created: {filepath}")
        return filepath
    else:
        print("Failed to generate chat history export")
        return None

# --- Core Logic using Gemini Chat API ---
def chat_with_gemini(
    prompt,
    source_image,
    chat_session_state,
    model_choice,
    system_prompt,
    temperature,
    max_tokens,
    thinking_budget,
    top_p,
    hate_speech,
    harassment,
    sexually_explicit,
    dangerous_content,
    token_info_state,
):
    """
    Handles multi-turn conversation using Gemini's Chat API with token counting.
    """
    if not client:
        return (
            [],
            "",
            "❌ Error: Gemini Client failed to initialize. Check API key and logs.",
            gr.update(visible=False),
            None,
            chat_session_state,
            "",
            token_info_state,
            gr.update(visible=False),
        )

    if not prompt or not prompt.strip():
        current_download = gr.update(visible=False)
        if chat_session_state:
            # If chat exists, prepare download
            filepath = export_chat_to_markdown(chat_session_state, token_info_state, model_choice, system_prompt)
            if filepath:
                current_download = gr.update(visible=True, value=filepath)
        
        return (
            [],
            "",
            "⚠️ Please enter a prompt.",
            gr.update(visible=False),
            None,
            chat_session_state,
            token_info_state.get("display", "") if token_info_state else "",
            token_info_state,
            current_download,
        )

    # Initialize token info state if needed
    if token_info_state is None:
        token_info_state = {
            "total_prompt_tokens": 0,
            "total_response_tokens": 0,
            "total_tokens": 0,
            "display": ""
        }

    # Create a new chat session if one doesn't exist
    if chat_session_state is None:
        if not model_choice:
            error_message = "❌ Error: No model selected from the dropdown."
            return (
                [{"role": "assistant", "content": error_message}],
                "",
                error_message,
                gr.update(visible=False),
                None,
                chat_session_state,
                "",
                token_info_state,
                gr.update(visible=False),
            )

        try:
            print(
                f"Starting new chat session with model: {model_choice}, Temp: {temperature}, Top P: {top_p}, Max Tokens: {max_tokens}, Thinking Budget: {thinking_budget}"
            )

            # Construct safety settings from UI
            safety_settings = [
                types.SafetySetting(
                    category=HARM_CATEGORY_MAP["Hate Speech"],
                    threshold=BLOCK_THRESHOLD_MAP[hate_speech],
                ),
                types.SafetySetting(
                    category=HARM_CATEGORY_MAP["Harassment"],
                    threshold=BLOCK_THRESHOLD_MAP[harassment],
                ),
                types.SafetySetting(
                    category=HARM_CATEGORY_MAP["Sexually Explicit"],
                    threshold=BLOCK_THRESHOLD_MAP[sexually_explicit],
                ),
                types.SafetySetting(
                    category=HARM_CATEGORY_MAP["Dangerous Content"],
                    threshold=BLOCK_THRESHOLD_MAP[dangerous_content],
                ),
            ]

            # Build config with generation settings
            config = types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=int(max_tokens),
                thinking_config=types.ThinkingConfig(
                    thinking_budget=int(thinking_budget)
                ),
                safety_settings=safety_settings,
            )

            # Add system instruction if provided
            if system_prompt and system_prompt.strip():
                config.system_instruction = system_prompt

            # Create the chat session with config
            chat_session_state = client.chats.create(model=model_choice, config=config)

        except Exception as e:
            error_message = f"❌ Error creating chat session: {e}"
            return (
                [{"role": "assistant", "content": error_message}],
                "",
                error_message,
                gr.update(visible=False),
                None,
                chat_session_state,
                "",
                token_info_state,
                gr.update(visible=False),
            )

    try:
        # Count tokens BEFORE sending the message
        history_before = chat_session_state.get_history()
        message_parts = [prompt]
        if source_image:
            message_parts.append(source_image)
        
        # Count tokens for history before message
        try:
            if history_before:
                history_token_count = client.models.count_tokens(
                    model=model_choice, 
                    contents=history_before
                )
                history_tokens = history_token_count.total_tokens
            else:
                history_tokens = 0
        except Exception as e:
            print(f"Error counting history tokens: {e}")
            history_tokens = 0

        # Send the message
        response = chat_session_state.send_message(message_parts)

        # Extract usage metadata from response
        usage_metadata = response.usage_metadata if hasattr(response, 'usage_metadata') else None
        
        # Update cumulative token counts
        if usage_metadata:
            if hasattr(usage_metadata, 'prompt_token_count'):
                token_info_state["total_prompt_tokens"] += usage_metadata.prompt_token_count
            if hasattr(usage_metadata, 'candidates_token_count'):
                token_info_state["total_response_tokens"] += usage_metadata.candidates_token_count
            if hasattr(usage_metadata, 'total_token_count'):
                token_info_state["total_tokens"] += usage_metadata.total_token_count
        
        # Format token display for this turn
        current_turn_info = format_token_info(usage_metadata, history_tokens)
        
        # Format cumulative token display
        cumulative_info = (
            f"\n\n**📈 Session Total**: "
            f"{token_info_state['total_prompt_tokens']} prompt + "
            f"{token_info_state['total_response_tokens']} response = "
            f"{token_info_state['total_tokens']} total tokens"
        )
        
        token_display = f"**This Turn**: {current_turn_info}{cumulative_info}"
        token_info_state["display"] = token_display

        # Check for generated images
        generated_image_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data is not None:
                generated_image_data = part.inline_data.data
                break

        # Build chat history
        history = chat_session_state.get_history()
        chatbot_history = []
        for message in history:
            role = "assistant" if message.role == "model" else message.role
            content_text = ""
            for part in message.parts:
                if part.text:
                    content_text += part.text
                elif (
                    role == "user" and hasattr(part, "inline_data") and part.inline_data
                ):
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

            if chatbot_history and chatbot_history[-1]["role"] == "assistant":
                chatbot_history[-1]["content"] += "\n\n🖼️ [Image generated - see below]"

            download_update = gr.update(visible=True) if chat_session_state else gr.update(visible=False)
            return (
                chatbot_history,
                "",
                "✅ Image generated successfully!",
                gr.update(visible=True, value=output_filepath),
                output_filepath,
                chat_session_state,
                token_display,
                token_info_state,
                download_update,
            )
        else:
            download_update = gr.update(visible=True) if chat_session_state else gr.update(visible=False)   
            return (
                chatbot_history,
                "",
                "✅ Response received.",
                gr.update(visible=False),
                None,
                chat_session_state,
                token_display,
                token_info_state,
                download_update,
            )

    except errors.APIError as e:
        error_message = f"❌ API Error ({e.code}): {e.message}"
        current_history = [{"role": "assistant", "content": error_message}]
        
        # Still try to export what we have
    
        download_update = gr.update(visible=True) if chat_session_state else gr.update(visible=False)
        
        return (
            current_history,
            "",
            error_message,
            gr.update(visible=False),
            None,
            chat_session_state,
            token_info_state.get("display", "") if token_info_state else "",
            token_info_state,
            download_update,
        )

    except Exception as e:
        error_message = f"❌ Unexpected error: {e}"
        current_history = [{"role": "assistant", "content": error_message}]
        
        # Still try to export what we have
        download_update = gr.update(visible=False)
        if chat_session_state:
            chat_export_path = export_chat_to_markdown(chat_session_state, token_info_state, model_choice, system_prompt)
            if chat_export_path:
                download_update = gr.update(visible=True, value=chat_export_path)
        
        return (
            current_history,
            "",
            error_message,
            gr.update(visible=False),
            None,
            chat_session_state,
            token_info_state.get("display", "") if token_info_state else "",
            token_info_state,
            download_update,
        )


def new_conversation():
    """Resets the chat session and clears all UI elements."""
    new_token_state = {
        "total_prompt_tokens": 0,
        "total_response_tokens": 0,
        "total_tokens": 0,
        "display": ""
    }
    return [], "", "🔄 New conversation started.", gr.update(visible=False), None, None, "", new_token_state, gr.update(visible=False)



# --- Load configuration and build UI ---
model_list = load_models()
default_model = model_list[0] if model_list else None
safety_threshold_choices = list(BLOCK_THRESHOLD_MAP.keys())

with gr.Blocks(theme=gr.themes.Default(), title="💬 Gemini Multi-turn Chat") as demo:
    gr.Markdown("# 💬 Gemini Multi-turn Chat with Image Generation & Token Counting")

    chat_session = gr.State(None)
    token_info = gr.State(None)

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="Conversation", height=600, show_copy_button=True, type="messages")
            token_usage_box = gr.Markdown(label="Token Usage", value="")
            status_box = gr.Markdown("")
            gr.Markdown("---")
            output_image = gr.Image(label="Latest Generated Image", height=400, show_download_button=False, visible=True)

        with gr.Column(scale=1):
            model_choice = gr.Dropdown(label="Choose a Model", choices=model_list, value=default_model)
            input_image = gr.Image(type="pil", label="Upload Image (Optional)", height=200)
            prompt_box = gr.Textbox(label="Your Message", placeholder="Ask questions, request images, or analyze uploaded images...", lines=8)

            with gr.Accordion("Advanced Settings", open=False):
                system_prompt_box = gr.Textbox(label="System Prompt", placeholder="e.g., You are a helpful assistant.", lines=3)
                temperature_slider = gr.Slider(minimum=0.0, maximum=2.0, value=1.0, step=0.1, label="Temperature (Creativity)")
                top_p_slider = gr.Slider(minimum=0.0, maximum=1.0, value=0.95, step=0.05, label="Top P")
                max_tokens_slider = gr.Slider(minimum=1024, maximum=65536, value=65536, step=1024, label="Max Output Tokens")
                thinking_budget_input = gr.Number(label="Thinking Budget (Tokens)", value=-1, info="Set to 0 to disable, or -1 for dynamic thinking. Other options, 1000, 2000, 8192, etc.",)
                gr.Markdown("#### Safety Settings")
                hate_speech_dd = gr.Dropdown(label="Hate Speech", choices=safety_threshold_choices, value="BLOCK_NONE")
                harassment_dd = gr.Dropdown(label="Harassment", choices=safety_threshold_choices, value="BLOCK_NONE")
                sexually_explicit_dd = gr.Dropdown(label="Sexually Explicit", choices=safety_threshold_choices, value="BLOCK_NONE")
                dangerous_content_dd = gr.Dropdown(label="Dangerous Content", choices=safety_threshold_choices, value="BLOCK_NONE")

            with gr.Row():
                send_btn = gr.Button("📤 Send", variant="primary", scale=2)
                clear_input_btn = gr.Button("🗑️ Clear Input", scale=1)

            new_chat_btn = gr.Button("🔄 New Conversation", variant="stop")

            with gr.Row():
                download_image_btn = gr.DownloadButton(label="💾 Download Image", visible=False, scale=1)
                # New chat history export controls
                generate_chat_btn = gr.Button("📥 Generate Chat History File", scale=2)
            chat_file_output = gr.File(label="📄 Chat History File", visible=False)        

    # --- Send button and input bindings ---
    def send_message(
        prompt, image, session, model, system_prompt, temp, top_p, tokens,
        thinking_budget, hate, harass, sexual, dangerous, token_state
    ):
        return chat_with_gemini(
            prompt, image, session, model, system_prompt, temp,
            tokens, thinking_budget, top_p, hate, harass, sexual, dangerous, token_state
        )

    inputs_list = [
        prompt_box,
        input_image,
        chat_session,
        model_choice,
        system_prompt_box,
        temperature_slider,
        top_p_slider,
        max_tokens_slider,
        thinking_budget_input,
        hate_speech_dd,
        harassment_dd,
        sexually_explicit_dd,
        dangerous_content_dd,
        token_info,
    ]

    outputs_list = [
        chatbot,
        prompt_box,
        status_box,
        download_image_btn,
        output_image,
        chat_session,
        token_usage_box,
        token_info,
        chat_file_output,  # replaced download_chat_btn
    ]

    send_btn.click(fn=send_message, inputs=inputs_list, outputs=outputs_list).then(
        fn=lambda: None, outputs=[input_image]
    )

    prompt_box.submit(fn=send_message, inputs=inputs_list, outputs=outputs_list).then(
        fn=lambda: None, outputs=[input_image]
    )

    clear_input_btn.click(
        fn=lambda: ("", None, "✏️ Input cleared."),
        outputs=[prompt_box, input_image, status_box],
        queue=False,
    )

    new_chat_btn.click(
        fn=new_conversation,
        outputs=[
            chatbot,
            prompt_box,
            status_box,
            download_image_btn,
            output_image,
            chat_session,
            token_usage_box,
            token_info,
            chat_file_output,  # replaced download_chat_btn
        ],
    )

    # 🆕 Binding for chat export
    generate_chat_btn.click(
        fn=generate_chat_history_file,
        inputs=[chat_session, token_info, model_choice, system_prompt_box],
        outputs=[chat_file_output],
    )

if __name__ == "__main__":
    print("Launching Gradio interface with Gemini Chat API... Press Ctrl+C to exit.")
    print(
        "To customize the model list, create a file named 'models.txt' with one model name per line."
    )
    print("Temporary files for this session will be cleaned up automatically on exit.")
    demo.launch()
