import os
import json
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
from core.protocols import ActionProposal, ActionType

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

class FinanceAgent:
    def __init__(self):
        self.name = "finance_agent"
        self.model = genai.GenerativeModel('gemini-3-flash-preview')
        
    def process(self, user_input: str) -> ActionProposal:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        prompt = f"""
        You are the FINANCE AGENT for the myOS system.
        CURRENT DATE/TIME: {current_time}
        
        YOUR ROLE:
        Analyze incoming content (emails, text) specifically for FINANCIAL data: Invoices, Bills, Receipts, Salary slips, or Payment requests.
        
        USER INPUT: "{user_input}"
        
        ---------------------------------------------------------
        ### PROTOCOLS ###
        
        1. **BILL / INVOICE DETECTED**:
           - Extract: Vendor Name, Amount, Due Date.
           - Action: 'schedule_event' (to schedule the payment) OR 'notify_user' (if details are missing).
           - Risk Level: 'critical' (Always require user approval for payments).
           - Summary: "Payment to [Vendor]: [Amount] due on [Date]".
           
        2. **RECEIPT / INFO**:
           - Action: 'log_info' (or 'archive' generic emails).
           - Risk Level: 'safe'.
           
        3. **NOT FINANCIAL**:
           - If the input is NOT related to finance, return Action: 'none' (let other agents handle it) or 'notify_user' saying it's irrelevant.

        ---------------------------------------------------------
        ### OUTPUT FORMAT (JSON ONLY) ###
        {{
            "source_agent": "{self.name}",
            "action_type": "...",
            "risk_level": "...", 
            "payload": {{ ... }},
            "reasoning": "..."
        }}
        """

        try:
            response = self.model.generate_content(
                prompt, 
                generation_config={"response_mime_type": "application/json"}
            )
            
            data_dict = json.loads(response.text)
            if isinstance(data_dict, list):
                data_dict = data_dict[0]
            
            return ActionProposal(**data_dict)

        except Exception as e:
            print(f"❌ Finance Agent Error: {e}")
            return None
