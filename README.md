# GenAI-extract-data-from-images-to-create-chatbot-knowledge
This project involves extracting data from images using a large language model (LLM) with vision capabilities to create knowledge for chatbots.

## Overview

The solution has been tested with Python 10 and utilizes image data of glasses.

## Requirements

- **LLM Model with Vision**: Azure OpenAI GPT-4o
- **Embedding Model**: Azure OpenAI GPT-4o
- **Vector Database**: Azure Search AI

## Flow Diagram

![Flow Diagram](images/flow.png)

## Installation and Setup

1. **Install Dependencies**

   First, install the required packages by running:

   ```bash
   pip install -r requirements.txt
Tested with python 10. Dan menggunakan data gambar kacamata.

Requirment:
LLM model with vision --> (Azure OpenAI gpt-4o)
Embedding model --> (Azure OpenAI gpt-4o)
Vector Database --> (Azure Search AI)

Gambar flow [images/flow.png]

Pertama, install requierment.txt
pip install requirments.txt

Kedua, sesuaikan env file sesuai resource yang anda punya.

Kedua, jalankan script notebook.ipynb menggunakan sample data pada folder data untuk menjalankan flow secara end-to-end dari extract data sampai simulasi chatbot. Anda bisa mencoba data usecase lain sesuai kebutuhan.

Ketiga, jalankan simulasi menggunakan frontend streamlit. Ada 2 fitur:
1. Extract Data, untuk simulasi dari gambar menjadi informasi berbentuk json
gambar [images/Extract Data.png]
2. Chatbot, tanya jawab berdasarkan knowledge yang sudah dibuat pada script notebook.ipynb
gambar [images/chatbot.png]
