# app.py
#
# PURPOSE:
# This script runs the main web application. It now uses Google's Gemini models for both
# text generation and for creating the embeddings used in the RAG search.
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
from threading import Timer
from dotenv import load_dotenv

# --- Qdrant Vector Database ---
from qdrant_client import QdrantClient, models

# --- Web Application Framework (Flask) ---
from flask import Flask, render_template, request, jsonify, Response

# --- LangChain & Google AI Libraries ---
# --- NEW: We use Google's models for both generation and embeddings ---
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_qdrant import Qdrant
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from google.api_core.exceptions import ResourceExhausted

# --- Utilities ---
from colorama import init, Fore, Style
init(autoreset=True)


# --- Configuration and Initialization ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)

# --- Global Configuration ---
CHAT_HISTORY_RAW_DIR = "chat_history"
PROCESSED_HISTORY_DIR = os.path.join(CHAT_HISTORY_RAW_DIR, "Processed")
CONFIG_FILE = "./config.json"

# --- NEW: Use Google's embedding model ---
EMBEDDING_MODEL_NAME = "models/embedding-001"
# --- NEW: The vector dimension must match the model (768) ---
VECTOR_DIMENSION = 768

KNOWLEDGE_BASE_COLLECTION_NAME = "knowledge_base"
CHAT_HISTORY_COLLECTION_NAME = "chat_history_db"

# --- Global Variables for Chatbot Components ---
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GEMINI_API_KEY, temperature=0.3)
# --- NEW: Instantiate Google's embedding model ---
embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME, google_api_key=GEMINI_API_KEY)
knowledge_base_retriever = None
chat_history_retriever = None
generation_chain = None


# --- Helper Functions (omitted for brevity, they are unchanged) ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return {"user_name": None, "persona_instructions": "You are Pixel, a friendly AI assistant."}
def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)
def save_chat_history_to_file(filename, history_messages, summary="Untitled Chat"):
    os.makedirs(CHAT_HISTORY_RAW_DIR, exist_ok=True)
    history_file_path = os.path.join(CHAT_HISTORY_RAW_DIR, filename)
    chat_data_to_save = {"summary": summary, "history": history_messages, "timestamp": datetime.now().isoformat()}
    with open(history_file_path, 'w', encoding='utf-8') as f: json.dump(chat_data_to_save, f, indent=4)
    return history_file_path
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
def embed_and_store_chat_history(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        transcript = f"Chat Summary: {chat_data.get('summary', 'Untitled')}\n\n" + "\n".join(
            [f"{item['role']}: {item['content']}" for item in chat_data.get('history', [])]
        )
        if not chat_data.get('history'): return
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.create_documents([transcript])
        Qdrant.from_documents(documents=chunks, embedding=embeddings, url="http://localhost:6333", collection_name=CHAT_HISTORY_COLLECTION_NAME)
        os.makedirs(PROCESSED_HISTORY_DIR, exist_ok=True)
        shutil.move(file_path, os.path.join(PROCESSED_HISTORY_DIR, os.path.basename(file_path)))
    except Exception as e:
        print(Fore.RED + f"ERROR embedding chat history: {e}")


# --- Core Application Logic ---
@app.before_request
def initialize_chatbot_components():
    """Initializes chatbot components before the first request."""
    global knowledge_base_retriever, chat_history_retriever, generation_chain
    if generation_chain is not None: return
    try:
        print(Fore.YELLOW + "Initializing chatbot components with Gemini Embeddings...")
        qdrant_client = QdrantClient("http://localhost:6333")
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


# --- API Routes for Chat History and Settings ---
@app.route('/api/history/list', methods=['GET'])
def api_history_list():
    return jsonify({"status": "success", "files": get_all_chat_summaries_and_filenames()})
@app.route('/api/history/save', methods=['POST'])
def api_history_save():
    data = request.json
    history_to_save = data.get('history', [])
    if not history_to_save: return jsonify({"status": "ignored"}), 200
    first_user_message = next((msg['content'].strip()[:30].replace(" ", "_") for msg in history_to_save if msg.get('role') == 'user' and msg.get('content','').strip()), "Untitled_Chat")
    filename = f"{first_user_message}_{datetime.now().strftime('%y%m%d%H%M%S')}.json"
    summary_for_display = first_user_message.replace("_", " ").title()
    file_path = save_chat_history_to_file(filename, history_to_save, summary=summary_for_display)
    embed_and_store_chat_history(file_path)
    return jsonify({"status": "success"})
@app.route('/api/history/load', methods=['POST'])
def api_history_load():
    data = request.json
    filename = data.get('filename')
    if not filename: return jsonify({"status": "error"}), 400
    history = load_chat_history_from_file(filename)
    return jsonify({"status": "success", "history": history}) if history else jsonify({"status": "error"}), 404
@app.route('/api/history/delete_all', methods=['POST'])
def api_history_delete_all():
    try:
        client = QdrantClient("http://localhost:6333")
        client.delete_collection(collection_name=CHAT_HISTORY_COLLECTION_NAME)
        # --- NEW: Use the correct vector dimension (768) when recreating ---
        client.recreate_collection(collection_name=CHAT_HISTORY_COLLECTION_NAME, vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance="Cosine"))
        if os.path.exists(CHAT_HISTORY_RAW_DIR): shutil.rmtree(CHAT_HISTORY_RAW_DIR)
        os.makedirs(PROCESSED_HISTORY_DIR, exist_ok=True)
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

# --- Main Execution Block ---
def open_browser():
    webbrowser.open_new_tab('http://127.0.0.1:5000/')

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        Timer(1, open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
