import os
import time
from pydantic import BaseModel
from typing import Optional, Dict, Any
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from dotenv import load_dotenv
import psutil
import traceback
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Load API keys
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://kea.mywire.org:5300",
    "https://aoinstore.com"
]

def add_headers(response):
    origin = request.headers.get('Origin')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = 'null'

    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRF-Token'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '3600'
    return response

def create_chatbot_app():
    """Application factory for chatbot."""
    app = Flask(__name__)

    # Configure CORS
    CORS(app, 
         resources={
             r"/api/*": {
                 "origins": ALLOWED_ORIGINS,
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                 "allow_headers": ["Content-Type", "Authorization"]
             }
         },
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         max_age=3600)

    try:
        logger.info("Initializing embeddings and LLM...")
        # Initialize embeddings and LLM
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        llm = ChatGroq(groq_api_key=groq_api_key, model_name="llama-3.1-8b-instant")
        logger.info("Embeddings and LLM initialized successfully")

        # Create prompt template
        prompt = ChatPromptTemplate.from_template(
            
            """You are AOIN's AI assistant. Your goal is to be helpful, accurate, and conversational when answering questions.

    Important guidelines:
    - Respond naturally as if you are part of the AOIN team
    - Never mention "context," "documents," or that you're retrieving information
    - Speak directly and confidently about AOIN's features, partner programs, and shopping experience
    - Keep responses concise, friendly, and informative
    - Highlight unique features like AOIN Live and the themed in-house shops when relevant
    - If information isn't available in the provided content, simply say "I don't have complete details on that specific question, but I’d be happy to connect you with someone from our team who can help"
    - Don't make up information about AOIN's specific policies, services, or pricing),
    ("human", "{input}"),

            <content>
            {context}
            </content>

            Question: {input}
            """
        )

        # Initialize vector store
        def create_vector_embedding():
            try:
                aoin_file = os.path.join(os.path.dirname(__file__), "Aoin.txt")
                if not os.path.exists(aoin_file):
                    logger.error(f"Aoin.txt not found at {aoin_file}")
                    raise FileNotFoundError(f"Aoin.txt not found at {aoin_file}")
                
                logger.info(f"Loading documents from {aoin_file}")
                loader = TextLoader(aoin_file)
                documents = loader.load()
                
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200
                )
                texts = text_splitter.split_documents(documents)
                logger.info(f"Split documents into {len(texts)} chunks")
                
                start_time = time.time()
                vectorstore = FAISS.from_documents(texts, embeddings)
                logger.info(f"Vector store created in {time.time() - start_time:.2f} seconds")
                
                return vectorstore
            except Exception as e:
                logger.error(f"Error creating vector store: {str(e)}")
                logger.error(traceback.format_exc())
                return None

        # Initialize vector store at startup
        logger.info("Initializing vector store...")
        vectorstore = create_vector_embedding()
        if not vectorstore:
            raise RuntimeError("Failed to initialize the knowledge base.")
        logger.info("Vector store initialized successfully")

        # Create document chain
        document_chain = create_stuff_documents_chain(llm, prompt)
        retriever = vectorstore.as_retriever()
        retrieval_chain = create_retrieval_chain(retriever, document_chain)
        logger.info("Retrieval chain created successfully")

    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        logger.error(traceback.format_exc())
        raise

    # Add monitoring middleware
    @app.before_request
    def before_request():
        request.start_time = time.time()
        logger.info(f"Received {request.method} request to {request.path}")

    @app.after_request
    def after_request(response):
        if hasattr(request, 'start_time'):
            response_time = (time.time() - request.start_time) * 1000
            logger.info(f"Request processed in {response_time:.2f}ms")
        return add_headers(response)

    @app.errorhandler(Exception)
    def handle_error(error):
        error_type = type(error).__name__
        error_message = str(error)
        error_stack = traceback.format_exc()
        
        logger.error(f"Error Type: {error_type}")
        logger.error(f"Error Message: {error_message}")
        logger.error(f"Stack Trace: {error_stack}")
        
        return jsonify({
            'error': error_message,
            'type': error_type
        }), getattr(error, 'code', 500)

    # Chat endpoint
    @app.route('/api/chat', methods=['POST'])
    def chat_endpoint():
        try:
            data = request.get_json()
            logger.info(f"Received chat request: {data}")
            
            if not data or 'query' not in data:
                logger.warning("Missing query parameter in request")
                return jsonify({'error': 'Missing query parameter'}), 400

            start_time = time.time()
            logger.info(f"Processing query: {data['query']}")
            
            # Get response from LLM
            response = retrieval_chain.invoke({"input": data['query']})
            processing_time = time.time() - start_time
            
            logger.info(f"Query processed in {processing_time:.2f} seconds")
            logger.info(f"Response: {response}")

            # Extract the actual response from the LLM
            llm_response = response.get("answer", "")
            if not llm_response:
                # If no direct answer, try to generate a greeting response
                if data['query'].lower() in ['hi', 'hello', 'hey']:
                    llm_response = "Hello! Welcome to AOIN. How can I assist you today?"
                else:
                    llm_response = "I'm here to help! Could you please rephrase your question?"

            return jsonify({
                "answer": llm_response,
                "processing_time": f"{processing_time:.2f} seconds",
                "user_id": data.get('user_id')
            })
        except Exception as e:
            logger.error(f"Error processing chat request: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({
                'error': f"Error processing question: {str(e)}",
                'details': traceback.format_exc()
            }), 500

    # Health check endpoint
    @app.route('/api/chatbot/health')
    def health_check():
        return jsonify({
            "status": "healthy",
            "version": "1.0.0",
            "uptime_seconds": time.time() - psutil.boot_time()
        })

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app

if __name__ == "__main__":
    app = create_chatbot_app()
    app.run(host='0.0.0.0', port=5901)