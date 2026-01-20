from agents.secretariat_agent import SecretariatAgent

def test_agent():
    print("🚀 Initializing Agent...")
    agent = SecretariatAgent()
    
    # Test Case 1: Meeting Request (Should trigger notify_user or draft_email)
    input_text = "Hi, can we meet tomorrow at 10:00 AM for a quick sync? -- John"
    
    print(f"\n📝 Testing Input: '{input_text}'")
    proposal = agent.process(input_text)
    
    print(f"\n💡 Result:")
    print(f"Action: {proposal.action_type}")
    print(f"Reasoning: {proposal.reasoning}")
    print(f"Payload: {proposal.payload}")

if __name__ == "__main__":
    test_agent()
