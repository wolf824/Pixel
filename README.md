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
├── docker-compose.yml    \# Configuration to easily run the Qdrant database  
└── requirements.txt      \# List of all Python libraries needed for the project

## **🚀 How to Set Up and Run (from GitHub)**

Follow these steps to get Pixel running on your local machine.

### **Prerequisites**

* [Python 3.8+](https://www.python.org/downloads/)  
* [Docker](https://www.docker.com/get-started/) and Docker Compose  
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

python app.py

Your terminal will show messages confirming that the chatbot components and the background watcher have started. Your default web browser should open automatically to http://127.0.0.1:5000.

## **📖 How to Use Pixel**

* **To Add Knowledge:** Simply drop any PDF files you want the bot to learn from directly into the data/ folder. The background watcher will automatically detect, process, and add them to the knowledge base. You will see "Pipeline:" messages in your terminal confirming this.  
* **To Chat:** Just start typing in the input box\!  
* **To Save a Chat:** The application automatically saves your conversation when you start a new chat, view the history, or close the browser tab.  
* **To Continue an Old Chat:** Click the "Chat History" icon, find the conversation you want to continue, and click on it. The chat will be loaded. When you add new messages, the history will be automatically updated and re-indexed the next time you navigate away.
