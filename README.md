# **Pixel: Your Personal AI Assistant with a Dynamic Memory**

**Pixel** is a sophisticated, locally-run chatbot powered by a **Retrieval-Augmented Generation (RAG)** architecture. It leverages the powerful generative capabilities of Google's Gemini models while maintaining a private, dynamic, and searchable knowledge base on your own machine.

This project is designed to be a powerful personal assistant that can learn from your documents and remember your conversations, with a fully automated data pipeline that makes managing its knowledge seamless.

## **► Core Concepts Explained**

This project combines several cutting-edge technologies. Here’s a simple breakdown of how they work together:

### **1\. What is RAG (Retrieval-Augmented Generation)?**

At its heart, RAG is a clever way to make Large Language Models (LLMs) smarter and more accurate. Instead of just relying on its pre-trained knowledge, the model first **retrieves** relevant information from your personal data (like PDFs and chat history) and then uses that information as context to **generate** a more informed and precise answer.

The workflow is:  
Your Question → Search Your Data → Find Relevant Info → Give Info \+ Question to LLM → Get a Smart, Contextual Answer

### **2\. The Components of Pixel**

| Component | Technology | Role |
| :---- | :---- | :---- |
| **Chat Interface** | Flask & HTML/JS | A beautiful, self-contained web UI for interacting with the bot. |
| **Text Generation** | **Google Gemini 1.5 Flash** | The powerful LLM that writes the responses. It receives context from our database to formulate its answers. |
| **Embeddings (The Bot's "Brain")** | Sentence-Transformers | A local model (all-MiniLM-L6-v2) that runs on your machine. It reads text and converts it into numerical representations (vectors). This is how the bot "understands" the meaning of the text. |
| **Vector Database (The Bot's "Memory")** | **Qdrant** | A high-performance database specifically designed to store and search through vectors. When you ask a question, Pixel searches Qdrant to find the most relevant text chunks from your documents and chat history. |
| **Automated Data Pipeline** | Watchdog | A background process that constantly monitors your data/ and chat\_history/ folders. When a new file appears, it automatically triggers the embedding process and updates the vector database. |

## **✨ Features**

* **PDF-Based Knowledge:** Drop any PDF into the data folder, and Pixel will automatically read, learn, and use it as a source for its answers.  
* **Persistent & Updatable Chat Memory:** Pixel remembers your conversations. You can close the app, come back later, load a past conversation, and continue right where you left off. The memory is automatically updated and re-indexed.  
* **Fully Automated Pipeline:** No need to run manual scripts\! The watchdog service detects new files and chat updates, processing them into the database in the background.  
* **Local First:** The most sensitive parts of the RAG process—your data, the embeddings model, and the vector database—all run locally on your machine, ensuring privacy.  
* **Customizable Persona:** Easily change the bot's personality and instructions from the settings menu.  
* **Sleek UI:** A clean, modern, and dark-mode-ready user interface.

## **📂 Project Structure**

.  
├── chat\_history/         \# Raw (unprocessed) chat logs are saved here first  
│   └── Processed/        \# Successfully processed chat logs are moved here  
├── data/                 \# Drop your PDFs here to add them to the knowledge base  
│   └── Processed/        \# Processed PDFs are moved here  
├── templates/  
│   └── index.html        \# The single-page frontend for the application  
├── .env                  \# Your secret API key for Google Gemini  
├── app.py                \# The main script: runs the Flask server AND the automated pipeline  
└── requirements.txt      \# List of all Python libraries needed for the project

## **🚀 How to Set Up and Run (from GitHub)**

Follow these steps to get Pixel running on your local machine.

### **Prerequisites**

* [Python 3.8+](https://www.python.org/downloads/)  
* [Docker](https://www.docker.com/get-started/)
* [Git](https://git-scm.com/downloads/)

### **Step 1: Clone the Repository**

Open your terminal and clone this repository to your local machine.

git clone https://github.com/wolf824/Pixel.git

cd pixel-rag-chatbot

### **Step 2: Set Up Your API Key**

You need a Google Gemini API key for the text generation part.

1. Create a file named .env in the root of the project directory.  
2. Add your API key to this file like so:  
   GEMINI\_API\_KEY="your-google-api-key-goes-here"

### **Step 3: Install Dependencies**

Install all the required Python libraries using the requirements.txt file.

pip install \-r requirements.txt

### **Step 4: Start the Vector Database**

The Qdrant database runs in a Docker container. Start it with this simple command. It will run in the background.

docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant

*(The first time you run this, it will download the Qdrant image, which may take a few minutes.)*

### **Step 5: Run the Application\!**

Now, start the main application. This single command launches the web server and the automated background pipeline.
``` bash
python app.py
```
Your terminal will show messages confirming that the chatbot components and the background watcher have started. Your default web browser should open automatically to http://127.0.0.1:5000.

## **📖 How to Use Pixel**

* **To Add Knowledge:** Simply drop any PDF files you want the bot to learn from directly into the data/ folder. The background watcher will automatically detect, process, and add them to the knowledge base. You will see "Pipeline:" messages in your terminal confirming this.  
* **To Chat:** Just start typing in the input box\!  
* **To Save a Chat:** The application automatically saves your conversation when you start a new chat, view the history, or close the browser tab.  
* **To Continue an Old Chat:** Click the "Chat History" icon, find the conversation you want to continue, and click on it. The chat will be loaded. When you add new messages, the history will be automatically updated and re-indexed the next time you navigate away.

# PDF Processing Utilities

This repository contains a collection of Python scripts designed to automate the creation and processing of PDF documents. These tools are ideal for building a local, readable library of articles and for preparing large documents for further analysis or use in RAG (Retrieval-Augmented Generation) applications.

## Table of Contents

1.  **URL to PDF Converter (`url_to_pdf.py`)**
    * What It Does
    * Features
    * How to Use
    * Files and Folders

2.  **PDF Content Cleaner (`process_pdfs.py`)**
    * What It Does
    * Features
    * How to Use
    * Files and Folders

---

## 1. URL to PDF Converter (`url_to_pdf.py`)

This script is a powerful tool for converting online articles and web pages into clean, readable, and uniformly styled PDF documents.

### What It Does

The script reads a list of URLs from a text file, fetches the main content from each page, strips away ads and navigation bars, and saves each article as a separate, neatly formatted PDF file in your `data` folder.

**Example:** You have a list of 20 news articles you want to read offline. You paste the URLs into `link.txt`, run the script, and get 20 clean PDF files, one for each article.

### Features

* **Content Extraction:** Uses the `readability` library to intelligently grab only the main article content, ignoring sidebars, ads, and other clutter.
* **Stateful Processing:** Keeps a log of successfully processed links (`processed_links.log`) so you never process the same link twice.
* **Automatic Cleanup:** After processing, it automatically removes the successful links from your `link.txt` file, leaving only the ones that may have failed and need attention.
* **Standardized Formatting:** Applies a consistent, professional style to all generated PDFs for a comfortable reading experience.
* **Safe Filenames:** Automatically generates valid filenames from article titles.

### How to Use

1.  **Install Dependencies:** Make sure you have the required Python libraries installed.
    ```bash
    pip install requests readability-lxml weasyprint
    ```

2.  **Create `link.txt`:** In the same directory as the script, create a file named `link.txt`.

3.  **Add URLs:** Open `link.txt` and paste the URLs you want to convert, with each URL on a new line.
    ```
    [https://example.com/some-interesting-article](https://example.com/some-interesting-article)
    [https://anothersite.com/another-great-read](https://anothersite.com/another-great-read)
    ```

4.  **Run the Script:** Open your terminal and run the script.
    ```bash
    python url_to_pdf.py
    ```

5.  **Find Your PDFs:** The script will process each new link and save the resulting PDF files in a `data/` folder.

### Files and Folders

* `url_to_pdf.py`: The script itself.
* `link.txt` **(You create this)**: Your input file where you list the URLs to be processed.
* `processed_links.log` (Created by the script): A log file to prevent re-processing links. You can safely ignore this file.
* `data/` (Created by the script): The output folder where your clean PDF files are saved.

---

## 2. PDF Content Cleaner (`process_pdfs.py`)

This script is designed to process a large, book-style PDF and remove unnecessary content.

### What It Does

The script intelligently cleans a PDF by removing boilerplate sections. It analyzes the PDF's bookmarks (its table of contents) and uses them to identify and extract only the core chapters. It discards sections like "Copyright," "Index," and "Table of Contents." Finally, it merges the useful chapters back together, overwriting the original file in the `data` folder with the new, clean version.

**Example:** You have a 500-page textbook PDF full of front matter and appendices. You run the script, and it automatically removes all the junk, leaving you with a clean PDF containing only the main chapters, ready for reading or analysis.

### Features

* **Interactive Level Selection:** The script analyzes the PDF's bookmarks and interactively asks you which outline level you want to use for splitting (e.g., main parts vs. individual chapters).
* **Intelligent Title Cleaning:** Automatically removes chapter numbering (like "Chapter 1." or "5.2 -") from filenames during processing.
* **Smart Exclusion:** Automatically skips boilerplate sections based on a predefined exclusion list (e.g., "Table of Contents," "Index," "About the Author").
* **Single-Page Chapter Removal:** Skips creating PDFs for chapters that are only one page long (often just a title page).
* **Automatic Overwrite:** After processing, it merges the useful chapters back into a single, clean PDF, replacing the original file.

### How to Use

1.  **Install Dependencies:** Make sure you have the `pypdf` library.
    ```bash
    pip install pypdf
    ```
2.  **Place PDFs in `data/`:** Move the large PDF files you want to process into the `data/` directory.

3.  **Run the Script:** Open your terminal and run the script.
    ```bash
    python process_pdfs.py
    ```
4.  **Interact with the Prompt:** For each PDF, the script will show you the available bookmark levels. Enter the number corresponding to the level you want to use for processing (usually `0` for top-level parts or `1` for chapters).

5.  **Find the Result:** The original PDF file in the `data/` folder will be overwritten with the new, cleaned version containing only the essential content.

### Files and Folders

* `process_pdfs.py`: The script itself.
* `data/`: The folder where you place your input PDFs and where the final, cleaned output PDFs will be saved.

