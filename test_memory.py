import sys
from agents.information_agent import InformationAgent

def main():
    print("🧠 Ultimate Memory Tester...")
    agent = InformationAgent()

    while True:
        print("\n------------------------------------------------")
        print("1. 🔮 Semantic Search (Raw results)")
        print("2. 🎯 Exact Search (Specific word)")
        print("3. 🧠 Ask the Brain (Summarize & Analyze) <--- NEW!")
        print("q. Quit")
        
        mode = input("Select: ")
        
        if mode == 'q': break
        
        query = input("\n💬 What do you want to know? > ")
        
        if mode == '1':
            res = agent.recall(query)
            print(res)
        elif mode == '2':
            res = agent.search_exact(query)
            print(res)
        elif mode == '3':
            # כאן קורה הקסם
            answer = agent.ask_brain(query)
            print("\n🤖 AI Answer:\n")
            print(answer)

if __name__ == "__main__":
    main()
