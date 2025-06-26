# **RAG Chatbot with Gemini & Qdrant**

This document provides a detailed explanation of the Retrieval-Augmented Generation (RAG) chatbot application. We'll cover its architecture, the core concepts that make it work, the methods it employs, and a step-by-step guide to set it up and run it on any machine.

## **1\. Project Overview**

This application is a sophisticated conversational AI that can answer questions based on a custom set of documents you provide. Instead of relying only on its pre-trained knowledge, it first searches for relevant information in your private knowledge base (like PDFs) and then uses that information to formulate a precise, contextually-aware answer.

This technique is called **Retrieval-Augmented Generation (RAG)**, and it makes the chatbot incredibly powerful for specific knowledge domains, turning it into a personalized expert.

**Key Features:**

* **Unified AI Stack:** Uses Google's Gemini models for both generating answers and creating the embeddings for search, simplifying the architecture and ensuring high compatibility.  
* **Scalable:** Can handle millions of documents efficiently thanks to the self-hosted Qdrant vector database, which separates the memory-intensive work from the main application.  
* **Knowledgeable:** Answers questions based on a custom knowledge base you provide (PDFs).  
* **Long-Term Memory:** Remembers past conversations by saving and embedding chat histories, allowing it to reference previous interactions.  
* **Efficient:** The architecture is designed to run smoothly even on low-spec hardware (e.g., an i3 processor with 8GB of RAM) by offloading heavy computation.

## **2\. Core Concepts Explained**

To understand how the chatbot works, let's break down the foundational concepts.

### **a) Retrieval-Augmented Generation (RAG)**

Imagine you have to answer a difficult question for an open-book exam. Instead of just trying to remember the answer, you first look through your textbook for the relevant page and *then* write your answer based on what you found.

That's exactly what RAG does\!

1. **Retrieve (The Search):** When you ask the chatbot a question, it doesn't immediately try to answer. First, it **retrieves** (searches for) the most relevant snippets of text from your knowledge base.  
2. **Augment (The Enhancement):** It then takes your original question and **augments** it by adding the relevant text snippets it found. This gives the AI crucial context.  
3. **Generate (The Answer):** Finally, it sends this combined information (your question \+ the relevant text) to the powerful Gemini language model, which **generates** a comprehensive answer based on the provided facts.

### **b) Gemini Embeddings: The Language of Meaning**

Computers don't understand words; they understand numbers. To make our search work, we need to convert our text into a numerical format that captures its *meaning*. This numerical representation is called an **embedding** or a **vector**.

* **Example:** The sentence "The cat sat on the mat" is converted into a list of 768 numbers like \[0.12, \-0.45, 0.67, ...\].  
* Crucially, sentences with similar meanings will have similar lists of numbers. "The feline was on the rug" will have a vector very close to the first one.

This application uses Google's embedding-001 model, which is highly compatible with the Gemini model used for generating answers, ensuring a cohesive understanding of the text.

### **c) Vector Database (Qdrant): The Super-Fast Library**

Now that all our text chunks are converted into vectors, we need a place to store them and search through them incredibly quickly. A traditional database is slow at comparing vectors.

A **vector database** like **Qdrant** is a specialized tool built for this task. It's like a giant, highly organized library for these vectors. When you give it a new vector (from your question), it can find the "closest" or most similar vectors from your documents in milliseconds, even if there are millions of them. This is the engine behind the "Retrieve" step.

## **3\. Methods: The Application's Workflow**

Here's a detailed look at the methods and the journey of your question from start to finish.

1. **User Asks a Question:** You type a message in the web browser (e.g., "What are the symptoms of anxiety?").  
2. **API Request:** The frontend sends the question to the **Flask App (app.py)**.  
3. **Embedding** the **Query:** The app uses the **Gemini embedding model** to convert your question into a 768-dimension vector.  
4. **Parallel Retrieval:** The app sends this vector to the **Qdrant database** to search in two collections simultaneously:  
   * knowledge\_base: To find relevant chunks from your PDFs.  
   * chat\_history\_db: To find relevant chunks from past conversations, providing memory.  
5. **Context Assembly:** Qdrant returns the most relevant chunks (e.g., the top 5 from each collection). The app.py script assembles these into a single block of context.  
6. **Prompt Engineering:** The app creates a detailed prompt for the Gemini LLM, which includes:  
   * Your custom persona instructions (from the settings).  
   * The assembled context from the retrieval step.  
   * The recent chat history.  
   * Your original question.  
7. **Answer Generation:** This complete prompt is sent to the **Gemini LLM**. It generates a final answer based *only* on the information provided.  
8. **Streaming Response:** The app streams the answer back to your web browser token-by-token, so the response appears dynamically as it's being generated.

## **4\. Application Architecture**

The application is designed to be modular and scalable, consisting of three main, independent processes.

* **1\. Qdrant Vector Database:** A standalone service running in a Docker container. It is the long-term memory of the application, responsible for storing and searching through all the document vectors.  
* **2\. Data Processing Script (create\_embeddings.py):** A command-line script you run to process your documents. It finds new PDFs, splits them into chunks, creates Gemini embeddings, and uploads them to the Qdrant database.  
* **3\. Chat Application (app.py):** The main Flask web application. It serves the user interface, handles API requests, orchestrates the RAG workflow, and communicates with both the Qdrant database and the Gemini API.

### **Directory Structure**

A well-organized project is easy to understand. Here is the file structure:

/pixel\_chatbot/  
├── data/  
│   └── Processed/  
│   └── your\_document.pdf  
├── chat\_history/  
│   └── Processed/  
│   └── chat\_summary\_timestamp.json  
├── templates/  
│   └── index.html  
├── qdrant\_storage/         \<-- Automatically created by Docker  
├── app.py                  \<-- The main web application  
├── create\_embeddings.py    \<-- The data processing script  
├── requirements.txt        \<-- List of Python packages needed  
└── .env                    \<-- Your secret API keys

## **5\. How to Set Up and Run This Application (For Other Users)**

This guide will walk anyone through setting up the project from a source like GitHub.

### **Step 1: Prerequisites**

Make sure you have the following software installed on your computer:

* **Python** (version 3.9 or higher)  
* **Docker Desktop** (for running the Qdrant database)  
* **Git** (for cloning the project repository)

### **Step 2: Get the Code**

Open your terminal, navigate to where you want to store the project, and clone the repository.

\# Replace the URL with your actual GitHub repository URL  
git clone https://github.com/wolf824/Pixel.git 
cd pixel-chatbot

### **Step 3: Install Python Packages**

This step installs all the necessary Python packages for the application from the requirements.txt file.

pip install \-r requirements.txt

### **Step 4: Create the .env File for API Keys**

Create a new file named .env in the main project directory. This file will hold your secret API key for the Google Gemini model.

**.env file contents:**

GEMINI\_API\_KEY="YOUR\_GOOGLE\_AI\_STUDIO\_API\_KEY"

You can get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey). You may also need to set up a billing account in Google Cloud for higher usage limits.

### **Step 5: Start the Qdrant Vector Database**

Make sure Docker Desktop is running. Then, in your terminal, run the following command to start the Qdrant service:

docker run \-p 6333:6333 \-p 6334:6334 \\  
    \-v $(pwd)/qdrant\_storage:/qdrant/storage:z \\  
    qdrant/qdrant

Leave this terminal window open. It is now running your database.
You can use Qdrant web dashboard at http://localhost:6333/dashboard.

### **Step 6: Add Your Documents**

Place any PDF files you want the chatbot to learn from inside the data/ directory.

### **Step 7: Process Your Documents**

This step reads your PDFs, creates Gemini embeddings, and uploads them to Qdrant. Open a **new, second terminal** (keep the Docker one running) and run:

python create\_embeddings.py

### **Step 8: Run the Chat Application**

Finally, it's time to start the chatbot\! In a **third terminal** (or you can reuse the second one after the embedding script finishes), run the main app:

python app.py

A web browser tab should automatically open to http://127.0.0.1:5000/. You can now start chatting with your AI assistant\!


