# app.py
#
# PURPOSE:
# This single script runs the main web application AND the automated data pipeline.
# It uses a background process to watch for new chat history files and automatically
# processes them into the Qdrant vector database.
#
# HOW TO RUN:
# Run this script from your terminal after the Qdrant container is running.
# `python app.py`

# --- Core Python Libraries ---
import os
import json
import uuid
from datetime import datetime
import re
import time
import shutil
import webbrowser
from threading import Timer, Thread

# --- Qdrant Vector Database ---
from qdrant_client import QdrantClient, models

# --- Web Application Framework (Flask) ---
from flask import Flask, render_template, request, jsonify, Response

# --- LangChain & AI Libraries ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import Qdrant
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from google.api_core.exceptions import ResourceExhausted

# --- File System Watcher ---
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Utilities ---
from colorama import init, Fore, Style
init(autoreset=True)


# --- Configuration and Initialization ---
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)

# --- Global Configuration ---
CHAT_HISTORY_RAW_DIR = "chat_history"
PROCESSED_HISTORY_DIR = os.path.join(CHAT_HISTORY_RAW_DIR, "Processed")
DATA_DIR = "data"
PROCESSED_PDF_DIR = os.path.join(DATA_DIR, "Processed")
CONFIG_FILE = "./config.json"

# --- Embedding Model Configuration ---
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
VECTOR_DIMENSION = 384

KNOWLEDGE_BASE_COLLECTION_NAME = "knowledge_base"
CHAT_HISTORY_COLLECTION_NAME = "chat_history_db"

# --- Global Variables for Chatbot Components ---
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY, temperature=0.3)
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
qdrant_client = QdrantClient("http://localhost:6333")
knowledge_base_retriever = None
chat_history_retriever = None
generation_chain = None


# --- Automated Data Pipeline Logic (from create_embeddings.py) ---

def ensure_collection_exists(client: QdrantClient, collection_name: str, vector_size: int):
    """Ensures a Qdrant collection exists with the correct vector size."""
    try:
        existing_collections = [col.name for col in client.get_collections().collections]
        if collection_name in existing_collections:
            collection_info = client.get_collection(collection_name=collection_name)
            current_size = collection_info.config.params.vectors.size
            if current_size != vector_size:
                print(Fore.RED + f"CRITICAL: Collection '{collection_name}' has wrong vector size {current_size}. Expected {vector_size}. Please fix manually.")
                return False
            print(Fore.GREEN + f"Pipeline: Collection '{collection_name}' is ready.")
        else:
            print(Fore.YELLOW + f"Pipeline: Collection '{collection_name}' not found. Creating...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
            )
            print(Fore.GREEN + f"Pipeline: Collection '{collection_name}' created.")
        return True
    except Exception as e:
        print(Fore.RED + f"Pipeline: CRITICAL ERROR ensuring collection '{collection_name}': {e}")
        return False

def process_file_for_qdrant(file_path: str):
    """Processes a single file (PDF or JSON) and uploads its chunks to Qdrant."""
    filename = os.path.basename(file_path)
    source_dir = os.path.dirname(file_path)
    
    is_pdf = filename.lower().endswith('.pdf')
    collection_name = KNOWLEDGE_BASE_COLLECTION_NAME if is_pdf else CHAT_HISTORY_COLLECTION_NAME
    processed_dir = PROCESSED_PDF_DIR if is_pdf else PROCESSED_HISTORY_DIR
    
    print(Fore.CYAN + f"Pipeline: Processing '{filename}' for collection '{collection_name}'...")

    try:
        if is_pdf:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = text_splitter.split_documents(documents)
        else: # It's a JSON chat history
            with open(file_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            transcript = f"Chat Summary: {chat_data.get('summary', 'Untitled')}\n\n" + "\n".join(
                [f"{item['role']}: {item['content']}" for item in chat_data.get('history', [])]
            )
            if not chat_data.get('history'):
                print(Fore.YELLOW + "Pipeline: Skipping empty chat file.")
                shutil.move(file_path, os.path.join(processed_dir, filename))
                return
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = text_splitter.create_documents([transcript])

        if not chunks:
            print(Fore.YELLOW + f"Pipeline: No text chunks created for '{filename}', skipping.")
            shutil.move(file_path, os.path.join(processed_dir, filename))
            return
            
        for chunk in chunks:
            chunk.metadata = {"source_file": filename}

        Qdrant.from_documents(
            documents=chunks,
            embedding=embeddings,
            url="http://localhost:6333",
            collection_name=collection_name
        )
        print(Fore.GREEN + f"Pipeline: Successfully uploaded '{filename}' to Qdrant.")
        shutil.move(file_path, os.path.join(processed_dir, filename))
        print(Fore.GREEN + f"Pipeline: Moved '{filename}' to processed directory.")

    except Exception as e:
        print(Fore.RED + f"Pipeline ERROR processing '{filename}': {e}")

class NewFileHandler(FileSystemEventHandler):
    """Event handler that triggers when a new file is created."""
    def on_created(self, event):
        if not event.is_directory and (event.src_path.endswith('.json') or event.src_path.endswith('.pdf')):
            print(Fore.YELLOW + f"Watcher: Detected new file: {event.src_path}")
            # Give the file a moment to finish writing before processing
            time.sleep(1) 
            process_file_for_qdrant(event.src_path)

def start_pipeline_watcher():
    """Initializes and starts the file system watcher in a background thread."""
    # Ensure all needed directories exist before starting
    os.makedirs(CHAT_HISTORY_RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_HISTORY_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PROCESSED_PDF_DIR, exist_ok=True)

    # Ensure Qdrant collections are ready
    if not ensure_collection_exists(qdrant_client, KNOWLEDGE_BASE_COLLECTION_NAME, VECTOR_DIMENSION): return
    if not ensure_collection_exists(qdrant_client, CHAT_HISTORY_COLLECTION_NAME, VECTOR_DIMENSION): return

    print(Style.BRIGHT + Fore.MAGENTA + "--- Starting Automated Data Pipeline Watcher ---")
    event_handler = NewFileHandler()
    observer = Observer()
    # Watch both the raw chat history and the main data directory
    observer.schedule(event_handler, CHAT_HISTORY_RAW_DIR, recursive=False)
    observer.schedule(event_handler, DATA_DIR, recursive=False)
    observer.daemon = True
    observer.start()
    print(Style.BRIGHT + Fore.GREEN + "--- Watcher is now running in the background. ---")


# --- Flask Web App Logic ---

# (Helper functions like load_config, save_config, etc., are unchanged)
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return {"user_name": None, "persona_instructions": "You are Pixel, a friendly AI assistant."}
def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)
def get_all_chat_summaries_and_filenames():
    chat_summaries = []
    processed_dir = PROCESSED_HISTORY_DIR
    os.makedirs(processed_dir, exist_ok=True) 
    if os.path.exists(processed_dir):
        for filename in os.listdir(processed_dir):
            if filename.lower().endswith(".json"):
                try:
                    with open(os.path.join(processed_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        chat_summaries.append({"filename": filename, "summary": data.get("summary", "Untitled Chat"), "timestamp": data.get("timestamp", "1970-01-01T00:00:00")})
                except json.JSONDecodeError: continue
    chat_summaries.sort(key=lambda x: x['timestamp'], reverse=True)
    return chat_summaries
def load_chat_history_from_file(filename):
    history_file_path = os.path.join(PROCESSED_HISTORY_DIR, filename)
    if os.path.exists(history_file_path):
        try:
            with open(history_file_path, 'r', encoding='utf-8') as f:
                raw_history_data = json.load(f)
                return raw_history_data.get("history", [])
        except json.JSONDecodeError: return []
    return []
def save_new_chat_for_processing(history_messages, summary="Untitled Chat"):
    os.makedirs(CHAT_HISTORY_RAW_DIR, exist_ok=True)
    filename = f"{summary.replace(' ', '_')}_{datetime.now().strftime('%y%m%d%H%M%S')}.json"
    history_file_path = os.path.join(CHAT_HISTORY_RAW_DIR, filename)
    chat_data_to_save = {"summary": summary, "history": history_messages, "timestamp": datetime.now().isoformat()}
    with open(history_file_path, 'w', encoding='utf-8') as f:
        json.dump(chat_data_to_save, f, indent=4)
    # The watcher will now automatically pick this file up!
    return history_file_path

@app.before_request
def initialize_chatbot_components():
    global knowledge_base_retriever, chat_history_retriever, generation_chain
    if generation_chain is not None: return
    try:
        print(Fore.YELLOW + "Initializing chatbot components...")
        knowledge_base_store = Qdrant(client=qdrant_client, collection_name=KNOWLEDGE_BASE_COLLECTION_NAME, embeddings=embeddings)
        knowledge_base_retriever = knowledge_base_store.as_retriever(search_kwargs={"k": 5})
        chat_history_store = Qdrant(client=qdrant_client, collection_name=CHAT_HISTORY_COLLECTION_NAME, embeddings=embeddings)
        chat_history_retriever = chat_history_store.as_retriever(search_kwargs={"k": 5})
        doc_chain_prompt = ChatPromptTemplate.from_messages([
            ("system", "{persona_instructions}\n\nYou are a helpful AI assistant. Answer based ONLY on the context provided below.\n\nContext:\n{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ])
        generation_chain = create_stuff_documents_chain(llm, doc_chain_prompt)
        print(Fore.GREEN + "Chatbot components initialized.")
    except Exception as e:
        print(Fore.RED + f"CRITICAL ERROR during initialization: {e}")

@app.route('/')
def index():
    return render_template('index.html')

# (All other API routes: /api/chat, /api/history/list, etc. are unchanged)
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    frontend_history = data.get('history', [])
    if not user_message: return jsonify({"response": "No message."}), 400
    if not generation_chain: return jsonify({"response": "Chatbot not ready."}), 503
    config = load_config()
    persona_instructions = config.get("persona_instructions", "You are a helpful AI assistant.")
    lc_chat_history = [HumanMessage(content=msg['content']) if msg['role'] == 'user' else AIMessage(content=msg['content']) for msg in frontend_history]

    def generate_response():
        try:
            knowledge_docs = knowledge_base_retriever.invoke(user_message)
            history_docs = chat_history_retriever.invoke(user_message)
            stream = generation_chain.stream({"input": user_message, "chat_history": lc_chat_history, "context": knowledge_docs + history_docs, "persona_instructions": persona_instructions})
            for chunk in stream:
                if isinstance(chunk, str) and chunk: yield f"event: message\ndata: {json.dumps({'content': chunk})}\n\n"
        except ResourceExhausted as e:
            yield f"event: message\ndata: {json.dumps({'content': 'API rate limit exceeded. Please try again later.', 'error': True})}\n\n"
        except Exception as e:
            yield f"event: message\ndata: {json.dumps({'content': 'An error occurred.', 'error': True})}\n\n"
        finally:
            yield "event: end\ndata: {}\n\n"
    return Response(generate_response(), mimetype='text/event-stream')
@app.route('/api/history/list', methods=['GET'])
def api_history_list():
    return jsonify({"status": "success", "files": get_all_chat_summaries_and_filenames()})
@app.route('/api/history/save', methods=['POST'])
def api_history_save():
    data = request.json
    history_to_save = data.get('history', [])
    if not history_to_save: return jsonify({"status": "ignored"}), 200
    first_user_message = next((msg['content'].strip()[:30] for msg in history_to_save if msg.get('role') == 'user' and msg.get('content','').strip()), "Untitled Chat")
    summary_for_display = first_user_message.replace("_", " ").title()
    save_new_chat_for_processing(history_to_save, summary=summary_for_display)
    return jsonify({"status": "success"})
@app.route('/api/history/update', methods=['POST'])
def api_history_update():
    data = request.json
    history_to_save = data.get('history', [])
    original_filename = data.get('filename')
    if not history_to_save or not original_filename:
        return jsonify({"status": "error", "message": "Missing history or original filename."}), 400
    print(Fore.YELLOW + f"Web: Updating chat history for '{original_filename}'...")
    try:
        print(Fore.CYAN + f"  -> Deleting old vectors from Qdrant where source is '{original_filename}'...")
        qdrant_client.delete(
            collection_name=CHAT_HISTORY_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="payload.source_file", match=models.MatchValue(value=original_filename))]
                )
            ),
            wait=True,
        )
        old_file_path = os.path.join(PROCESSED_HISTORY_DIR, original_filename)
        if os.path.exists(old_file_path):
            print(Fore.CYAN + f"  -> Deleting old file: '{old_file_path}'")
            os.remove(old_file_path)
        first_user_message = next((msg['content'].strip()[:30] for msg in history_to_save if msg.get('role') == 'user' and msg.get('content','').strip()), "Untitled Chat")
        summary_for_display = first_user_message.replace("_", " ").title()
        save_new_chat_for_processing(history_to_save, summary=summary_for_display)
        print(Fore.GREEN + f"Web: Successfully staged updated history for re-processing.")
        return jsonify({"status": "success"})
    except Exception as e:
        print(Fore.RED + f"Web: An error occurred during history update: {e}")
        return jsonify({"status": "error", "message": "An internal error occurred."}), 500
@app.route('/api/history/load', methods=['POST'])
def api_history_load():
    data = request.json
    filename = data.get('filename')
    if not filename: return jsonify({"status": "error"}), 400
    history = load_chat_history_from_file(filename)
    return jsonify({"status": "success", "history": history, "filename": filename}) if history else jsonify({"status": "error"}), 404
@app.route('/api/history/delete_all', methods=['POST'])
def api_history_delete_all():
    try:
        qdrant_client.recreate_collection(collection_name=CHAT_HISTORY_COLLECTION_NAME, vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE))
        qdrant_client.recreate_collection(collection_name=KNOWLEDGE_BASE_COLLECTION_NAME, vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE))
        if os.path.exists(CHAT_HISTORY_RAW_DIR): shutil.rmtree(CHAT_HISTORY_RAW_DIR)
        os.makedirs(PROCESSED_HISTORY_DIR, exist_ok=True)
        os.makedirs(CHAT_HISTORY_RAW_DIR, exist_ok=True)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error"}), 500
@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    config = load_config()
    if request.method == 'POST':
        data = request.json
        config['user_name'] = data.get('userName', config.get('user_name'))
        config['persona_instructions'] = data.get('persona', config.get('persona_instructions'))
        save_config(config)
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "success", "userName": config.get('user_name', ''), "persona": config.get('persona_instructions', '')})

def open_browser():
    webbrowser.open_new_tab('http://127.0.0.1:5000/')

if __name__ == '__main__':
    # Start the background pipeline watcher only when running the main Flask process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        pipeline_thread = Thread(target=start_pipeline_watcher)
        pipeline_thread.daemon = True
        pipeline_thread.start()
        Timer(1, open_browser).start()
        
    app.run(host='0.0.0.0', port=5000, debug=True)
