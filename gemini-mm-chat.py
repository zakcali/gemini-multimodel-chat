import os
import gradio as gr
from google import genai
from google.genai import errors, types
from PIL import Image
from io import BytesIO
import tempfile
import atexit
import base64
import time
from datetime import datetime
import unicodedata
import shutil
import mimetypes


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

# Supported document types for File Search
SUPPORTED_DOC_TYPES = ['.pdf', '.docx', '.txt', '.json', '.csv', '.md', '.html', '.xml']

def _make_ascii_safe_filename(filename):
    """
    Convert filename to a Windows-safe ASCII version by removing or simplifying
    any non-ASCII characters (accents, symbols, ideographs, etc.).
    """
    name, ext = os.path.splitext(filename)
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in ascii_name)
    return ascii_name + ext


def list_file_search_stores():
    """
    Lists all File Search stores with their metadata.
    Returns formatted markdown string for display.
    """
    if not client:
        return "❌ Gemini client not initialized"
    
    try:
        stores_list = []
        store_count = 0
        
        for store in client.file_search_stores.list():
            store_count += 1
            store_info = {
                'name': store.name if hasattr(store, 'name') else 'Unknown',
                'display_name': store.display_name if hasattr(store, 'display_name') else 'N/A',
                'create_time': store.create_time if hasattr(store, 'create_time') else 'N/A',
            }
            stores_list.append(store_info)
        
        if store_count == 0:
            return "📭 **No File Search stores found.**\n\nStores will be created automatically when you upload documents."
        
        # Format output
        output = f"## 📚 File Search Stores ({store_count})\n\n"
        output += "*Stores persist indefinitely until deleted. Files expire after 48 hours.*\n\n---\n\n"
        
        for idx, store in enumerate(stores_list, 1):
            output += f"### {idx}. Store\n\n"
            output += f"- **Name:** `{store['name']}`\n"
            if store['display_name'] != 'N/A':
                output += f"- **Display Name:** {store['display_name']}\n"
            output += f"- **Created:** {store['create_time']}\n"
            output += "\n---\n\n"
        
        return output
        
    except Exception as e:
        error_msg = f"❌ **Error listing stores:** {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg


def delete_all_file_search_stores():
    """
    Deletes all File Search stores with force=True.
    Returns status message with count of deleted stores.
    """
    if not client:
        return "❌ Gemini client not initialized", None
    
    try:
        stores_to_delete = []
        
        # Collect all store names first
        for store in client.file_search_stores.list():
            if hasattr(store, 'name'):
                stores_to_delete.append(store.name)
        
        if not stores_to_delete:
            return "📭 No stores to delete.", None
        
        # Delete each store
        deleted_count = 0
        failed_deletes = []
        
        for store_name in stores_to_delete:
            try:
                client.file_search_stores.delete(
                    name=store_name,
                    config={'force': True}
                )
                deleted_count += 1
                print(f"✅ Deleted store: {store_name}")
            except Exception as e:
                failed_deletes.append(f"{store_name}: {str(e)}")
                print(f"❌ Failed to delete {store_name}: {e}")
        
        # Build status message
        status = f"### 🗑️ Deletion Complete\n\n"
        status += f"✅ **Successfully deleted:** {deleted_count} store(s)\n\n"
        
        if failed_deletes:
            status += f"❌ **Failed deletions:** {len(failed_deletes)}\n\n"
            for failure in failed_deletes:
                status += f"- {failure}\n"
        
        status += "\n---\n\n*All File Search data has been permanently removed.*"
        
        # Clear the current session's store state
        return status, None
        
    except Exception as e:
        error_msg = f"❌ **Error during deletion:** {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg, None


def upload_document_to_file_search(file_path, store_state):
    """
    Uploads a document to a File Search store.
    Handles non-ASCII filenames safely on Windows.
    """
    if not client:
        return None, "❌ Gemini client not initialized", store_state
    
    if not file_path:
        return None, "", store_state
    
    try:
        temp_files_to_clean.append(file_path)
        print(f"Tracking document for cleanup: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in SUPPORTED_DOC_TYPES:
            return None, f"⚠️ Unsupported file type: {file_ext}. Supported: {', '.join(SUPPORTED_DOC_TYPES)}", store_state
        
        # Create or reuse store
        if store_state is None:
            print("Creating new File Search store...")
            store = client.file_search_stores.create()
            store_state = {
                'store_name': store.name,
                'uploaded_files': []
            }
        
        # Handle Windows unsafe filenames
        dir_path = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        safe_name = _make_ascii_safe_filename(base_name)
        safe_path = os.path.join(dir_path, safe_name)

        if base_name != safe_name:
            print(f"Renaming for upload (safe ASCII): '{base_name}' → '{safe_name}'")
            shutil.copy2(file_path, safe_path)
            upload_target = safe_path
        else:
            upload_target = file_path

        # Add support for various MIME types
        mimetypes.add_type("text/markdown", ".md")
        mimetypes.add_type("text/csv", ".csv")
        mimetypes.add_type("application/json", ".json")
        mimetypes.add_type("application/xml", ".xml")

        mime_type, _ = mimetypes.guess_type(upload_target)
        
        print(f"Uploading document ({mime_type or 'unknown'}): {upload_target}")
        upload_op = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_state['store_name'],
            file=upload_target
        )
        
        # Wait for upload to complete
        max_wait = 300
        wait_time = 0
        while wait_time < max_wait:
            if hasattr(upload_op, 'done') and upload_op.done:
                break
            time.sleep(5)
            try:
                upload_op = client.operations.get(
                    name=upload_op.name if hasattr(upload_op, 'name') else upload_op
                )
            except:
                if wait_time >= 10:
                    break
            wait_time += 2
        
        store_state['uploaded_files'].append(os.path.basename(file_path))
        
        status_msg = f"✅ Document uploaded: {os.path.basename(file_path)}\n📚 Total documents in store: {len(store_state['uploaded_files'])}"
        return store_state['store_name'], status_msg, store_state
        
    except Exception as e:
        error_msg = f"❌ Error uploading document: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return None, error_msg, store_state


def format_grounding_sources(grounding_metadata):
    """Formats grounding metadata into user-friendly display."""
    if not grounding_metadata:
        return ""
    
    output = "\n\n---\n\n### 📚 Grounding Sources\n\n"
    
    # Search entry point
    if hasattr(grounding_metadata, 'search_entry_point') and grounding_metadata.search_entry_point:
        entry_point = grounding_metadata.search_entry_point
        if hasattr(entry_point, 'rendered_content') and entry_point.rendered_content:
            output += f"🔗 **[View All Sources Together]({entry_point.rendered_content})**\n\n---\n\n"
    
    # Grounding attributions
    if hasattr(grounding_metadata, 'grounding_attributions') and grounding_metadata.grounding_attributions:
        output += "#### 🎯 Source Relevance Scores\n\n"
        
        for idx, attribution in enumerate(grounding_metadata.grounding_attributions, 1):
            if hasattr(attribution, 'source_id'):
                source_id = attribution.source_id
                source_name = "Unknown Source"
                
                if hasattr(source_id, 'grounding_passage') and source_id.grounding_passage:
                    passage = source_id.grounding_passage
                    if hasattr(passage, 'passage_id'):
                        source_name = passage.passage_id
                elif hasattr(source_id, 'semantic_retriever_chunk') and source_id.semantic_retriever_chunk:
                    chunk = source_id.semantic_retriever_chunk
                    if hasattr(chunk, 'source'):
                        source_name = chunk.source
                
                output += f"{idx}. **{source_name}**"
                
                if hasattr(attribution, 'confidence_score') and attribution.confidence_score:
                    score_pct = attribution.confidence_score * 100
                    output += f" - 🎯 {score_pct:.1f}% confidence"
                
                output += "\n"
        
        output += "\n---\n\n"
    
    # Grounding chunks
    if not hasattr(grounding_metadata, 'grounding_chunks') or not grounding_metadata.grounding_chunks:
        return output + "*No grounding chunks found*\n"
    
    sources_dict = {}
    chunk_counter = 0
    
    for chunk in grounding_metadata.grounding_chunks:
        if hasattr(chunk, 'retrieved_context') and chunk.retrieved_context:
            context = chunk.retrieved_context
            title = context.title if hasattr(context, 'title') else "Unknown Source"
            
            if title not in sources_dict:
                sources_dict[title] = {
                    'title': title,
                    'uri': context.uri if hasattr(context, 'uri') else None,
                    'chunks': []
                }
            
            chunk_info = {}
            if hasattr(context, 'text') and context.text:
                chunk_info['text'] = context.text
                chunk_info['preview'] = context.text[:500] + "..." if len(context.text) > 500 else context.text
            
            if hasattr(context, 'uri') and context.uri:
                chunk_info['location'] = context.uri
            
            if hasattr(chunk, 'chunk_relevance_score'):
                chunk_info['relevance'] = chunk.chunk_relevance_score
            
            if chunk_info:
                sources_dict[title]['chunks'].append(chunk_info)
                chunk_counter += 1
        
        elif hasattr(chunk, 'web'):
            web_chunk = chunk.web
            title = "🌐 Web Search Results"
            
            if title not in sources_dict:
                sources_dict[title] = {
                    'title': title,
                    'uri': None,
                    'chunks': [],
                    'is_web': True
                }
            
            chunk_info = {}
            if hasattr(web_chunk, 'uri'):
                chunk_info['location'] = web_chunk.uri
            if hasattr(web_chunk, 'title'):
                chunk_info['web_title'] = web_chunk.title
            
            sources_dict[title]['chunks'].append(chunk_info)
            chunk_counter += 1
    
    if not sources_dict:
        return output + "*No sources found*\n"
    
    output += f"#### 📖 Retrieved Content\n\n"
    output += f"*📊 Total: **{chunk_counter} chunks** from **{len(sources_dict)} documents***\n\n"
    
    for idx, (title, info) in enumerate(sources_dict.items(), 1):
        is_web = info.get('is_web', False)
        icon = "🌐" if is_web else "📄"
        output += f"**{idx}. {icon} {title}**\n\n"
        
        if info['uri'] and not is_web:
            output += f"📍 *Location:* `{info['uri']}`\n\n"
        
        if info['chunks']:
            output += f"📦 *Chunks Retrieved:* {len(info['chunks'])}\n\n"
            
            for chunk_idx, chunk_info in enumerate(info['chunks'], 1):
                if is_web and 'web_title' in chunk_info:
                    output += f"  - [{chunk_info['web_title']}]({chunk_info.get('location', '#')})\n"
                elif 'preview' in chunk_info:
                    output += f"\n<details>\n\n<summary>🔍 Chunk {chunk_idx}"
                    
                    if 'relevance' in chunk_info:
                        output += f" (Relevance: {chunk_info['relevance']:.1%})"
                    
                    output += f"</summary>\n\n```\n{chunk_info['preview']}\n```\n\n</details>\n"
        
        output += "\n---\n\n"
    
    if hasattr(grounding_metadata, 'grounding_support') and grounding_metadata.grounding_support:
        support = grounding_metadata.grounding_support
        
        output += "#### 📊 Grounding Quality\n\n"
        
        if hasattr(support, 'grounding_chunk_indices') and support.grounding_chunk_indices:
            output += f"- **Active Chunks:** {len(support.grounding_chunk_indices)}\n"
        
        if hasattr(support, 'support_score'):
            output += f"- **Support Score:** {support.support_score:.2%}\n"
        
        if hasattr(support, 'confidence_score'):
            output += f"- **Confidence:** {support.confidence_score:.2%}\n"
        
        output += "\n"
    
    output += "\n*💡 Click any chunk to see the exact text used to ground this response*\n"
    
    return output


def load_models(filepath="models.txt"):
    default_models = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash-image-preview",
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



def chat_with_gemini(
    prompt,
    source_image,
    source_document,
    chat_session_state,
    file_search_store_state,
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
    use_file_search,
):
    """
    Handles multi-turn conversation using Gemini's Chat API with token counting and File Search.
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
            "",
            file_search_store_state,
            None,
            "",
        )

    # Handle document upload if provided
    document_status = ""
    if source_document:
        store_name, doc_status, file_search_store_state = upload_document_to_file_search(
            source_document, file_search_store_state
        )
        document_status = doc_status
        if "Error" in doc_status or "Unsupported" in doc_status:
            return (
                [],
                "",
                doc_status,
                gr.update(visible=False),
                None,
                chat_session_state,
                token_info_state.get("display", "") if token_info_state else "",
                token_info_state,
                gr.update(visible=False),
                document_status,
                file_search_store_state,
                None,
                "",
            )

    if not prompt or not prompt.strip():
        current_download = gr.update(visible=False)
        if chat_session_state:
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
            document_status,
            file_search_store_state,
            None,
            "",
        )

    if token_info_state is None:
        token_info_state = {
            "total_prompt_tokens": 0,
            "total_response_tokens": 0,
            "total_tokens": 0,
            "display": ""
        }

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
                document_status,
                file_search_store_state,
                None,
                "",
            )

        try:
            print(
                f"Starting new chat session with model: {model_choice}, Temp: {temperature}, Top P: {top_p}, Max Tokens: {max_tokens}, Thinking Budget: {thinking_budget}"
            )

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

            config = types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=int(max_tokens),
                thinking_config=types.ThinkingConfig(
                    thinking_budget=int(thinking_budget)
                ),
                safety_settings=safety_settings,
            )

            if use_file_search and file_search_store_state and file_search_store_state.get('store_name'):
                config.tools = [
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[file_search_store_state['store_name']]
                        )
                    )
                ]
                print(f"File Search enabled with store: {file_search_store_state['store_name']}")

            if system_prompt and system_prompt.strip():
                config.system_instruction = system_prompt

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
                document_status,
                file_search_store_state,
                None,
                "",
            )

    try:
        history_before = chat_session_state.get_history()
        message_parts = [prompt]
        if source_image:
            message_parts.append(source_image)
        
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

        response = chat_session_state.send_message(message_parts)

        usage_metadata = response.usage_metadata if hasattr(response, 'usage_metadata') else None
        
        if usage_metadata:
            if hasattr(usage_metadata, 'prompt_token_count'):
                token_info_state["total_prompt_tokens"] += usage_metadata.prompt_token_count
            if hasattr(usage_metadata, 'candidates_token_count'):
                token_info_state["total_response_tokens"] += usage_metadata.candidates_token_count
            if hasattr(usage_metadata, 'total_token_count'):
                token_info_state["total_tokens"] += usage_metadata.total_token_count
        
        current_turn_info = format_token_info(usage_metadata, history_tokens)
        
        cumulative_info = (
            f"\n\n**📈 Session Total**: "
            f"{token_info_state['total_prompt_tokens']} prompt + "
            f"{token_info_state['total_response_tokens']} response = "
            f"{token_info_state['total_tokens']} total tokens"
        )
        
        token_display = f"**This Turn**: {current_turn_info}{cumulative_info}"
        token_info_state["display"] = token_display

        grounding_sources_display = ""
        if hasattr(response, 'candidates') and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                grounding_sources_display = format_grounding_sources(candidate.grounding_metadata)
                print(f"Grounding sources found: {grounding_sources_display[:100]}...")

        generated_image_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data is not None:
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

            status_msg = "✅ Image generated successfully!"
            if grounding_sources_display:
                status_msg += " (with grounded sources)"

            download_update = gr.update(visible=True) if chat_session_state else gr.update(visible=False)
            return (
                chatbot_history,
                "",
                status_msg,
                gr.update(visible=True, value=output_filepath),
                output_filepath,
                chat_session_state,
                token_display,
                token_info_state,
                download_update,
                document_status,
                file_search_store_state,
                None,
                grounding_sources_display,
            )
        else:
            status_msg = "✅ Response received."
            if grounding_sources_display:
                status_msg += " (grounded in uploaded documents)"

            download_update = gr.update(visible=True) if chat_session_state else gr.update(visible=False)   
            return (
                chatbot_history,
                "",
                status_msg,
                gr.update(visible=False),
                None,
                chat_session_state,
                token_display,
                token_info_state,
                download_update,
                document_status,
                file_search_store_state,
                None,
                grounding_sources_display,
            )

    except errors.APIError as e:
        error_message = f"❌ API Error ({e.code}): {e.message}"
        current_history = [{"role": "assistant", "content": error_message}]
        
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
            document_status,
            file_search_store_state,
            None,
            "",
        )

    except Exception as e:
        error_message = f"❌ Unexpected error: {e}"
        current_history = [{"role": "assistant", "content": error_message}]
        
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
            document_status,
            file_search_store_state,
            None,
            "",
        )


def new_conversation():
    """Resets the chat session and clears all UI elements."""
    new_token_state = {
        "total_prompt_tokens": 0,
        "total_response_tokens": 0,
        "total_tokens": 0,
        "display": ""
    }
    return [], "", "🔄 New conversation started.", gr.update(visible=False), None, None, "", new_token_state, gr.update(visible=False), "", None, None, ""


# --- Load configuration and build UI ---
model_list = load_models()
default_model = model_list[0] if model_list else None
safety_threshold_choices = list(BLOCK_THRESHOLD_MAP.keys())

with gr.Blocks(title="💬 Gemini Multi-turn Chat") as demo:
    gr.Markdown("# 💬 Gemini Multi-turn Chat with Image Generation, Document Analysis & Token Counting")
    gr.Markdown("📄 **New**: Upload documents (PDF, DOCX, TXT, JSON, etc.) for RAG-powered analysis using File Search!")

    chat_session = gr.State(None)
    token_info = gr.State(None)
    file_search_store = gr.State(None)

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="Conversation", height=600, buttons=["copy"])
            token_usage_box = gr.Markdown(label="Token Usage", value="")
            grounding_sources_box = gr.Markdown(label="Grounding Sources", value="")
            status_box = gr.Markdown("")
            document_status_box = gr.Markdown("")
            gr.Markdown("---")
            output_image = gr.Image(label="Latest Generated Image", height=400, visible=True, buttons=[])

        with gr.Column(scale=1):
            model_choice = gr.Dropdown(label="Choose a Model", choices=model_list, value=default_model)
            
            # File upload section with tabs
            with gr.Tabs() as upload_tabs:
                with gr.Tab("🖼️ Image"):
                    input_image = gr.Image(type="pil", label="Upload Image", height=200)
                with gr.Tab("📄 Document"):
                    input_document = gr.File(
                        label="Upload Document (PDF, DOCX, TXT, JSON, CSV, MD, HTML, XML)",
                        file_types=SUPPORTED_DOC_TYPES
                    )
            
            prompt_box = gr.Textbox(label="Your Message", placeholder="Ask questions, request images, or analyze uploaded documents...", lines=8)

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
                generate_chat_btn = gr.Button("📥 Generate Chat History File", scale=2)
            chat_file_output = gr.File(label="📄 Chat History File", visible=False)

            # NEW: File Search Store Management Section
            with gr.Accordion("🗄️ File Search Store Management", open=False):
                gr.Markdown("⚠️ **Important**: File Search stores persist indefinitely until deleted. Files expire after 48 hours, but the indexed data remains.")
                
                with gr.Row():
                    list_stores_btn = gr.Button("📋 List All Stores", scale=1)
                    delete_all_stores_btn = gr.Button("🗑️ Delete All Stores", variant="stop", scale=1)
                
                stores_display = gr.Markdown(label="Stores Information", value="")

    # --- Send button and input bindings ---
    def send_message(
        prompt, image, document, session, file_store, model, system_prompt, temp, top_p, tokens,
        thinking_budget, hate, harass, sexual, dangerous, token_state
    ):
        use_file_search = True if document and not image else False
        
        return chat_with_gemini(
            prompt, image, document, session, file_store, model, system_prompt, temp,
            tokens, thinking_budget, top_p, hate, harass, sexual, dangerous, token_state, use_file_search
        )

    inputs_list = [
        prompt_box,
        input_image,
        input_document,
        chat_session,
        file_search_store,
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
        chat_file_output,
        document_status_box,
        file_search_store,
        input_document,
        grounding_sources_box,
    ]

    send_btn.click(fn=send_message, inputs=inputs_list, outputs=outputs_list).then(
        fn=lambda: None, outputs=[input_image]
    )

    prompt_box.submit(fn=send_message, inputs=inputs_list, outputs=outputs_list).then(
        fn=lambda: None, outputs=[input_image]
    )

    clear_input_btn.click(
        fn=lambda: ("", None, None, "✏️ Input cleared."),
        outputs=[prompt_box, input_image, input_document, status_box],
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
            chat_file_output,
            document_status_box,
            file_search_store,
            input_document,
            grounding_sources_box,
        ],
    )

    generate_chat_btn.click(
        fn=generate_chat_history_file,
        inputs=[chat_session, token_info, model_choice, system_prompt_box],
        outputs=[chat_file_output],
    )

    # NEW: File Search Store Management Button Handlers
    list_stores_btn.click(
        fn=list_file_search_stores,
        outputs=[stores_display],
    )

    delete_all_stores_btn.click(
        fn=delete_all_file_search_stores,
        outputs=[stores_display, file_search_store],
    )

if __name__ == "__main__":
    print("Launching Gradio interface with Gemini Chat API... Press Ctrl+C to exit.")
    print("📄 Document upload enabled: PDF, DOCX, TXT, JSON, CSV, MD, HTML, XML")
    print("🔍 Enhanced grounding sources display - see which documents power each response!")
    print("🗄️ File Search Store Management - list and delete stores to manage storage")
    print("To customize the model list, create a file named 'models.txt' with one model name per line.")
    print("Temporary files for this session will be cleaned up automatically on exit.")
    demo.launch(theme=gr.themes.Default())
