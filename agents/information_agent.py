import os
import chromadb
import google.generativeai as genai
import uuid
from datetime import datetime

# --- הגדרות ---
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = 8000


# ⚠️ הדבק כאן את המפתח שלך (בתוך המרכאות):
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class InformationAgent:
    def __init__(self):
        print(f"📚 InformationAgent: Connecting to ChromaDB...")
        try:
            self.client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
            self.collection = self.client.get_or_create_collection("my_knowledge")
            
            # חיבור למוח של ג'ימני
            if not GOOGLE_API_KEY:
                print("⚠️ WARNING: No Google API Key provided! The 'brain' won't work.")
            else:
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model = genai.GenerativeModel('gemini-1.5-pro-latest') # מודל מהיר וחכם
                print("✅ Connected to Knowledge Base & Gemini Brain!")
                
        except Exception as e:
            print(f"❌ Connection Error: {e}")

    def memorize(self, text: str, source: str = "user_input"):
        try:
            # מניעת כפילויות גסה
            existing = self.collection.get(where_document={"$contains": text[:50]})
            if existing and len(existing['ids']) > 0:
                return False 

            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            self.collection.add(
                documents=[text],
                metadatas=[{"source": source, "created_at": timestamp}],
                ids=[doc_id]
            )
            print(f"💾 Saved: '{text[:30]}...'")
            return True
        except Exception as e:
            print(f"❌ Error saving: {e}")
            return False

    def recall(self, query: str, n_results: int = 15):
        """ שליפת מידע גולמי """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return results['documents'][0]
        except Exception as e:
            return []

    def search_exact(self, keyword: str):
        """ חיפוש מדויק """
        try:
            results = self.collection.get(where_document={"$contains": keyword})
            return results['documents']
        except Exception as e:
            return []

    def ask_brain(self, user_question: str):
        """ 🧠 RAG: שליפת מידע + ניתוח של AI """
        try:
            print("   🔍 Brain is reading relevant emails...")
            
            # 1. שליפת המיילים הרלוונטיים ביותר לשאלה
            relevant_docs = self.recall(user_question, n_results=20)
            
            if not relevant_docs:
                return "לא מצאתי מיילים שקשורים לנושא הזה בזיכרון שלי."

            # 2. בניית ה-Prompt (ההוראות ל-AI)
            context_text = "\n\n".join(relevant_docs)
            
            prompt = f"""
            You are a helpful personal assistant. 
            Analyze the following email snippets from the user's inbox and answer the user's question.
            
            User Question: "{user_question}"
            
            --- EMAILS CONTEXT ---
            {context_text}
            ----------------------
            
            Instructions:
            1. Extract specific details (Company names, Roles, Status).
            2. If the user asks for rejections vs. receipts, categorize them clearly.
            3. Answer in Hebrew (unless asked otherwise).
            4. Be concise and organized (use bullet points).
            5. If you don't find the answer in the text, say you didn't find it.
            """

            # 3. שליחה ל-Gemini
            print("   🤔 Brain is thinking...")
            response = self.model.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"❌ Brain Error: {e}"
