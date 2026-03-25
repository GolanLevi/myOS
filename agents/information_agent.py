import os
import uuid
from datetime import datetime

import chromadb
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq

from utils.logger import agent_logger

load_dotenv()

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = 8000
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class KnowledgeAgent:
    def __init__(self):
        agent_logger.info("Connecting to ChromaDB (LangChain)...")
        load_dotenv()
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

        try:
            self.client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

            if not self.google_api_key:
                agent_logger.warning("No Google API Key provided. Knowledge workflows will be limited.")
                self.embeddings = None
                self.llm = None
            else:
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-001",
                    google_api_key=self.google_api_key,
                )
                self.llm = ChatGroq(
                    model="llama-3.3-70b-versatile",
                    groq_api_key=os.getenv("GROQ_API_KEY"),
                    max_retries=3,
                )

            self.vector_store = Chroma(
                client=self.client,
                collection_name="my_knowledge_lc",
                embedding_function=self.embeddings,
            )
            agent_logger.info(
                f"KnowledgeAgent initialized (API Key found: {bool(self.google_api_key)})"
            )

        except Exception as e:
            agent_logger.error(f"Connection Error: {e}")

    def memorize(self, text: str, source: str = "user_input"):
        try:
            if not self.embeddings:
                agent_logger.warning("Missing embeddings, cannot save.")
                return False

            results = self.vector_store.similarity_search_with_score(text[:200], k=1)
            if results and results[0][1] < 0.05:
                agent_logger.info("Duplicate detected, not saving.")
                return False

            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()

            doc = Document(page_content=text, metadata={"source": source, "created_at": timestamp})
            self.vector_store.add_documents([doc], ids=[doc_id])

            agent_logger.info(f"Saved to Knowledge Base: '{text[:30]}...'")
            return True
        except Exception as e:
            agent_logger.error(f"Error saving: {e}")
            return False

    def ask_brain(self, user_question: str):
        if not self.llm:
            return "Model unavailable due to missing API key."

        try:
            agent_logger.info("KnowledgeAgent is reading relevant context via LangChain...")
            docs = self.vector_store.similarity_search(user_question, k=15)

            if not docs:
                return "לא מצאתי מידע רלוונטי בזיכרון (ChromaDB) שלי."

            context_text = "\n\n".join([doc.page_content for doc in docs])

            prompt = f"""
            You are a helpful personal assistant.
            Analyze the following contextual snippets from the user's archives and answer the user's question.

            User Question: "{user_question}"

            --- KNOWLEDGE CONTEXT ---
            {context_text}
            ----------------------

            Instructions:
            1. Extract specific details related to the question.
            2. Answer clearly and correctly within the given context.
            3. Answer in Hebrew (unless asked otherwise).
            4. Be concise and organized (use bullet points if applicable).
            5. If you don't find the answer in the text, say you didn't find it.
            """

            agent_logger.info("KnowledgeAgent is generating an answer...")
            response = self.llm.invoke(prompt)
            return response.content

        except Exception as e:
            return f"Brain Error: {e}"


# Backward-compatible alias during the naming transition.
InformationAgent = KnowledgeAgent
