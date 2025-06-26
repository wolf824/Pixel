# create_embeddings.py
#
# PURPOSE:
# This script is the data pipeline for our RAG application. Its sole job is to find new documents (PDFs)
# and chat histories, process them into searchable chunks, convert those chunks into numerical vectors
# using Google's Gemini embedding model, and upload them to our Qdrant vector database.
#
# HOW TO RUN:
# Run this script from your terminal whenever you add new files to the `data/` directory.
# `python create_embeddings.py`

# --- Core Python Libraries ---
import os
import shutil
import time
import json
from dotenv import load_dotenv

# --- Qdrant Vector Database ---
from qdrant_client import QdrantClient, models

# --- LangChain & Google AI Libraries ---
# --- NEW: Import Google's own embedding model ---
from langchain_google_genai import GoogleGenerativeAIEmbeddings
# A LangChain tool for loading and parsing text from PDF files.
from langchain_community.document_loaders import PyPDFLoader
# A smart text splitter that tries to keep related text together.
from langchain.text_splitter import RecursiveCharacterTextSplitter
# The LangChain integration that makes uploading data to Qdrant easy.
from langchain_qdrant import Qdrant

# --- Utilities ---
from colorama import init, Fore, Style

# Initialize colorama to automatically reset colors after each print statement.
init(autoreset=True)

# --- Main Configuration ---
load_dotenv()
# The Google API Key is now needed here for creating embeddings.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file.")

# --- Directory and File Paths ---
DATA_DIR = "data"
PROCESSED_PDF_DIR = os.path.join(DATA_DIR, "Processed")
CHAT_HISTORY_RAW_DIR = "chat_history"
PROCESSED_HISTORY_DIR = os.path.join(CHAT_HISTORY_RAW_DIR, "Processed")

# --- Qdrant & Embedding Model Configuration ---
KNOWLEDGE_BASE_COLLECTION_NAME = "knowledge_base"
CHAT_HISTORY_COLLECTION_NAME = "chat_history_db"

# --- NEW: Use a Google embedding model ---
EMBEDDING_MODEL_NAME = "models/embedding-001"
# --- NEW: Gemini embeddings have a different dimension ---
VECTOR_DIMENSION = 768


def initialize_directories():
    """Ensures that all necessary data directories exist before starting."""
    print(Fore.YELLOW + "Initializing data directory structure...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PROCESSED_PDF_DIR, exist_ok=True)
    os.makedirs(CHAT_HISTORY_RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_HISTORY_DIR, exist_ok=True)
    print(Fore.GREEN + "Data directories initialized successfully.")


def get_new_files(source_dir, processed_dir, file_extension):
    """
    Compares the source and processed directories to find new, unprocessed files.
    """
    print(Fore.YELLOW + f"Scanning '{source_dir}' for new '{file_extension}' files...")
    all_files = {f for f in os.listdir(source_dir) if f.lower().endswith(file_extension)}
    processed_files = {f for f in os.listdir(processed_dir) if f.lower().endswith(file_extension)}
    new_files = list(all_files - processed_files)

    if not new_files:
        print(Fore.GREEN + f"No new '{file_extension}' files found to process.")
    else:
        print(Fore.CYAN + f"Found {len(new_files)} new '{file_extension}' file(s): {', '.join(new_files)}")
    return new_files


def process_and_upload_to_qdrant(filename, source_dir, processed_dir, collection_name, embeddings_model, is_pdf=True):
    """
    The core function that takes a single file, processes it, and uploads it to Qdrant.
    """
    file_path = os.path.join(source_dir, filename)
    print(f"  -> Processing '{filename}' for Qdrant collection '{collection_name}'...")

    try:
        chunks = []
        if is_pdf:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = text_splitter.split_documents(documents)
            print(Fore.CYAN + f"     - Loaded PDF '{filename}' and created {len(chunks)} chunks.")
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
            transcript = f"Chat Summary: {chat_data.get('summary', 'Untitled')}\n\n" + "\n".join(
                [f"{item['role']}: {item['content']}" for item in chat_data.get('history', [])]
            )
            if not chat_data.get('history'):
                print(Fore.YELLOW + "     - File has no messages, skipping.")
                shutil.move(file_path, os.path.join(processed_dir, filename))
                return
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            chunks = text_splitter.create_documents([transcript])
            print(Fore.CYAN + f"     - Loaded chat history '{filename}' and created {len(chunks)} chunks.")

        if not chunks:
            print(Fore.YELLOW + f"     - No text chunks were created for '{filename}', skipping.")
            shutil.move(file_path, os.path.join(processed_dir, filename))
            return

        print(Fore.YELLOW + f"     - Uploading {len(chunks)} chunks to Qdrant...")
        Qdrant.from_documents(
            documents=chunks,
            embedding=embeddings_model,
            url="http://localhost:6333",
            collection_name=collection_name,
            force_recreate=False
        )
        print(Fore.GREEN + "     - Successfully uploaded chunks to Qdrant.")

        shutil.move(file_path, os.path.join(processed_dir, filename))
        print(Fore.GREEN + f"     - Moved processed file '{filename}' to '{processed_dir}'.")

    except Exception as e:
        print(Fore.RED + f"     [ERROR] An unexpected error occurred with '{filename}': {e}")
        import traceback
        traceback.print_exc()


def main():
    """
    The main execution function that orchestrates the entire process.
    """
    print(Style.BRIGHT + Fore.MAGENTA + "--- Starting Knowledge Base Update for Qdrant ---")
    start_time = time.time()
    initialize_directories()

    try:
        # --- NEW: Initialize Google's embedding model ---
        embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME, google_api_key=GEMINI_API_KEY)
        print(Fore.GREEN + f"Google Embeddings model '{EMBEDDING_MODEL_NAME}' loaded successfully.")

        qdrant_client = QdrantClient("http://localhost:6333")
        print(Fore.GREEN + "Qdrant client initialized successfully.")

        # --- NEW: Ensure collections exist with the correct 768 dimension ---
        qdrant_client.recreate_collection(
            collection_name=KNOWLEDGE_BASE_COLLECTION_NAME,
            vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE)
        )
        print(f" - Collection '{KNOWLEDGE_BASE_COLLECTION_NAME}' is ready.")

        qdrant_client.recreate_collection(
            collection_name=CHAT_HISTORY_COLLECTION_NAME,
            vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE)
        )
        print(f" - Collection '{CHAT_HISTORY_COLLECTION_NAME}' is ready.")

        # --- Process and Upload New Files ---
        print(Style.BRIGHT + Fore.CYAN + "\n--- Processing PDF Knowledge Base ---")
        new_pdfs = get_new_files(DATA_DIR, PROCESSED_PDF_DIR, '.pdf')
        for pdf_file in new_pdfs:
            process_and_upload_to_qdrant(pdf_file, DATA_DIR, PROCESSED_PDF_DIR, KNOWLEDGE_BASE_COLLECTION_NAME, embeddings)

        print(Style.BRIGHT + Fore.CYAN + "\n--- Processing Chat History Memory Database ---")
        new_history_files = get_new_files(CHAT_HISTORY_RAW_DIR, PROCESSED_HISTORY_DIR, '.json')
        for history_file in new_history_files:
            process_and_upload_to_qdrant(history_file, CHAT_HISTORY_RAW_DIR, PROCESSED_HISTORY_DIR, CHAT_HISTORY_COLLECTION_NAME, embeddings, is_pdf=False)

    except Exception as e:
        print(Fore.RED + f"A critical error occurred during the process: {e}")
        print(Fore.YELLOW + "Please ensure the Qdrant Docker container is running.")

    end_time = time.time()
    print(Style.BRIGHT + Fore.MAGENTA + f"\n--- Full Knowledge Base Update Finished in {end_time - start_time:.2f} seconds ---")


# This ensures the `main()` function is called only when the script is executed directly.
if __name__ == "__main__":
    main()
