import os
import base64
import json
import requests
import pandas as pd
from PIL import Image
from io import BytesIO
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
import streamlit as st

## Load environment variables from a .env file

load_dotenv()

# Load Azure OpenAI credentials and configuration
azure_openai_key = os.environ["AZURE_OPENAI_KEY"]
azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_api_version = os.environ["AZURE_OPENAI_API_VERSION"]
azure_openai_embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
azure_openai_embedding_dimensions = int(os.environ["AZURE_OPENAI_EMBEDDING_DIMENSIONS"])
azure_openai_chat_endpoint = os.environ["AZURE_OPENAI_CHATGPT_ENDPOINT"]

# Initialize the Azure OpenAI client for embeddings
embeddings_client = AzureOpenAI(
    api_key=azure_openai_key,
    api_version=azure_openai_api_version,
    azure_endpoint=azure_openai_endpoint
)

# Load Azure Search (Vector DB) credentials and configuration
vdb_endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
vdb_credential = AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"])
vdb_index_name = 'test-kacamata-index'  # Name of the index for vector database

# Initialize clients for index and search operations in Azure Search
index_client = SearchIndexClient(endpoint=vdb_endpoint, credential=vdb_credential)
search_client = SearchClient(endpoint=vdb_endpoint, index_name=vdb_index_name, credential=vdb_credential)
######################

## Extract Data Preparation

# Function to encode an image for processing by LLM
def encode_image(data):
    with BytesIO() as image_processing:
        data.save(image_processing, format='PNG')
        return base64.b64encode(image_processing.getvalue()).decode('ascii')

# Function to extract data from an image using gpt-4o model
def extract_image(prompt, encoded_image, key, endpoint):
    headers = {"Content-Type": "application/json", "api-key": key}

    # Payload for the request
    payload = {
        "model": "gpt-4o",
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are an AI assistant that extracts data from documents and returns them as structured JSON objects. Do not return as a code block."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]
            }
        ]
    }

    # Send request to the endpoint
    response = requests.post(endpoint, headers=headers, json=payload)
    return response.json()

# Function to ensure the result is in the desired JSON format
def parse_result(result):
    # Extract the content from the response
    answer = result['choices'][0]['message']['content']

    # Attempt to convert the string to JSON
    try:
        data_json = json.loads(answer)
        return data_json
    except json.JSONDecodeError:
        try:
            # Extract the JSON-like string from the response
            start_index = answer.find('{')
            end_index = answer.rfind('}') + 1
            answer_clean = answer[start_index:end_index]
            data_json = json.loads(answer_clean)
            return data_json
        except json.JSONDecodeError:
            print('Error parsing JSON')
            return {"metadata": "error", "bentuk": "error", "deskripsi": "error"}

# Define the prompt for extracting information
prompt = """Ekstrak informasi tentang kacamata dari data yang diberikan.

1. Bentuk: Klasifikasikan bentuk lensa menjadi oval, bulat, atau persegi.
2. Metadata: informasi tentang kacamata yang bisa disimpan.
3. Deskripsi: Berikan deskripsi terperinci tentang kacamata dari data yang diberikan, termasuk bentuk kacamata.
3. Jika ada informasi yang tidak tersedia, isi dengan "unknown".
4. Kembalikan dalam struktur JSON berikut sebagai satu-satunya respon:
{
  "metadata": {
    "merek": "",
    "jenis_gagang": "",
    "bahan": "",
    "warna_kacamata": "",
    "warna_gagang": ""
  },
  "bentuk": "",
  "deskripsi": ""
}
"""

###############################

## Chatbot Preparation

# Function to generate embeddings for a given text
def generate_embeddings(text, model=azure_openai_embedding_deployment):
    response = embeddings_client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding

# System prompt for the AI assistant
system_prompt = """Anda adalah Asisten AI yang menjawab pertanyaan tentang kacamata berdasarkan KATALOG yang ada. 
Jika pengguna meminta katalog spesifik, berikan jawaban sesuai detail yang diminta. 
Jika tidak ada informasi spesifik, tetapi ada yang mirip, Anda boleh merekomendasikan. 
Jika tidak ada KATALOG yang relevan, jawab dengan "Maaf, kami tidak punya katalog seperti yang Anda cari." 
Sertakan ID kacamata saat merekomendasikan.
Berikan respon yang terstruktur dan mudah dibaca, selalu pastikan jawaban Anda sesuai dengan pertanyaan."""

# Headers for the API request
headers = {"Content-Type": "application/json", "api-key": azure_openai_key}

# Function to perform vector search
def vector_search(query, top_k=3):
    knowledges = ''

    # Create a vectorized query using the generate_embeddings function
    vector_query = VectorizedQuery(vector=generate_embeddings(query), k_nearest_neighbors=top_k, fields="deskripsi_vektor")

    # Perform the search using the search client
    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["id", "deskripsi", "path"]
    )

    # Compile the search results into a formatted string
    for result in results:
        knowledges += f"id_kacamata:{result['id']}\ndeskripsi_kacamata:{result['deskripsi']}\n"

    return knowledges

# Function to handle question answering
def rag_qa(question):
    # Perform vector search to get relevant knowledge
    knowledges = vector_search(question)


    # Create a prompt for the AI model
    knowledge_prompt= """
        Katalog: {knowledges}
        """.format(knowledges=knowledges)
    
    messages = [{"role": "system","content": system_prompt},
                *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                {"role": "user","content":knowledge_prompt},
                ]

    # Payload for the API request
    payload = {
        "model":"gpt-4o",
        "temperature": 0,
        "messages": messages}

    # Send the request to the Azure OpenAI endpoint and get the response
    response = requests.post(azure_openai_chat_endpoint, headers=headers, json=payload).json()
    return response

#######################

st.set_page_config(
    page_title="SunglassesApp",
    #page_icon="💬",
    #layout="centered"
)

st.title("Welcome to the Sunglasses App")

#######################

def main():
    # Sidebar menu
    menu = st.radio('Menu', ['Extract Data','Chatbot'])
    
    if menu == 'Extract Data':
    
        left_container, right_container = st.columns(2)
                    
        with left_container:
            # upload and encode data
            uploaded_file = st.file_uploader("Upload Image (single image)", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:            
                if uploaded_file.type.lower().split('/')[1] != 'pdf':
                    Images = Image.open(uploaded_file)
                    st.image(Images, caption=None, use_column_width=True)
                    encode_data = encode_image(Images)
    
                if encode_data:
                    with st.spinner("Extract Data..."):
                        response = extract_image(prompt, encode_data, azure_openai_key, azure_openai_chat_endpoint)
                        result = parse_result(response)
                        with right_container:
                            st.success("Extract Data Success")
                            tab1, tab2 = st.tabs(["JSON", "TABLE"])
                            with tab1:
                                st.json(result)
                            with tab2:
                                df_result = pd.json_normalize(result)
                                st.table(df_result.T)
                        
                else:
                    with right_container:
                        st.write("Please Check Your Data")        
    
    elif menu == 'Chatbot':
        if st.button("Reset Chat"):
            st.session_state.messages = []
    
        if "messages" not in st.session_state:
            st.session_state.messages = []
    
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
        if q := st.chat_input("Ask Question Here ..."):
            st.session_state.messages.append({"role": "user", "content": q})
            with st.chat_message("user"):
                st.markdown(q)
    
    
            with st.chat_message("assistant"):
                with st.spinner("Generating Answer..."):        
                    response = rag_qa(q)
                answer = response['choices'][0]['message']['content']
                st.markdown(answer)
    
            st.session_state.messages.append({"role": "assistant", "content": answer})

if __name__ == "__main__":
    main()
