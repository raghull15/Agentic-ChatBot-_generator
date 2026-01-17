import sys
from rag_agent_system import RAGAgentSystem

def print_header():
    print("\n" + "="*60)
    print("RAG AGENT SYSTEM - COMMAND LINE INTERFACE")
    print("="*60 + "\n")

def print_menu():
    print("\nAvailable Commands:")
    print("  1. list           - List all agents")
    print("  2. create         - Create a new agent")
    print("  3. query          - Query an agent")
    print("  4. info           - Get agent information")
    print("  5. delete         - Delete an agent")
    print("  6. exit           - Exit the program")
    print()

def list_agents(rag_system):
    agents = rag_system.list_agents()
    if not agents:
        print("\n[INFO] No agents found.")
        return
    
    print(f"\n{'='*60}")
    print(f"TOTAL AGENTS: {len(agents)}")
    print(f"{'='*60}")
    for i, agent in enumerate(agents, 1):
        print(f"\n{i}. Agent: {agent['name']}")
        print(f"   Domain: {agent['domain'] or 'N/A'}")
        print(f"   Description: {agent['description'] or 'N/A'}")
        print(f"   Documents: {agent['num_documents']} chunks")
        print(f"   PDF Files: {len(agent['pdf_files'])}")

def create_agent(rag_system):
    print("\n--- CREATE NEW AGENT ---")
    agent_name = input("Enter agent name: ").strip()
    if not agent_name:
        print("[ERROR] Agent name cannot be empty")
        return
    
    domain = input("Enter domain (e.g., Medical, Legal): ").strip()
    description = input("Enter description (optional): ").strip()
    
    pdf_paths = []
    print("\nEnter PDF file paths (one per line, press Enter twice to finish):")
    while True:
        path = input("PDF path: ").strip()
        if not path:
            break
        pdf_paths.append(path)
    
    if not pdf_paths:
        print("[ERROR] At least one PDF file is required")
        return
    
    result = rag_system.create_agent(
        agent_name=agent_name,
        pdf_paths=pdf_paths,
        description=description,
        domain=domain
    )
    
    if result["success"]:
        print(f"\n[SUCCESS] {result['message']}")
    else:
        print(f"\n[ERROR] {result['error']}")

def query_agent(rag_system):
    print("\n--- QUERY AGENT ---")
    agents = rag_system.list_agents()
    
    if not agents:
        print("[ERROR] No agents available")
        return
    
    print("\nAvailable agents:")
    for i, agent in enumerate(agents, 1):
        print(f"  {i}. {agent['name']} ({agent['domain'] or 'General'})")
    
    choice = input("\nSelect agent number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(agents):
            print("[ERROR] Invalid selection")
            return
        agent_name = agents[idx]['name']
    except ValueError:
        print("[ERROR] Invalid input")
        return
    
    query = input("\nEnter your question: ").strip()
    if not query:
        print("[ERROR] Question cannot be empty")
        return
    
    k = input("Number of documents to retrieve (default 4): ").strip()
    k = int(k) if k.isdigit() else 4
    
    result = rag_system.query_agent(agent_name, query, k)
    
    if result["success"]:
        print(f"\n{'='*60}")
        print(f"ANSWER:")
        print(f"{'='*60}")
        print(f"\n{result['answer']}\n")
        print(f"{'='*60}")
        print(f"Sources used: {result['num_sources']} documents")
        print(f"{'='*60}")
    else:
        print(f"\n[ERROR] {result['error']}")

def show_agent_info(rag_system):
    print("\n--- AGENT INFORMATION ---")
    agents = rag_system.list_agents()
    
    if not agents:
        print("[ERROR] No agents available")
        return
    
    print("\nAvailable agents:")
    for i, agent in enumerate(agents, 1):
        print(f"  {i}. {agent['name']}")
    
    choice = input("\nSelect agent number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(agents):
            print("[ERROR] Invalid selection")
            return
        agent_name = agents[idx]['name']
    except ValueError:
        print("[ERROR] Invalid input")
        return
    
    info = rag_system.get_agent_info(agent_name)
    if info:
        print(f"\n{'='*60}")
        print(f"AGENT: {info['name']}")
        print(f"{'='*60}")
        print(f"Domain: {info['domain'] or 'N/A'}")
        print(f"Description: {info['description'] or 'N/A'}")
        print(f"Documents: {info['num_documents']} chunks")
        print(f"Storage Path: {info['storage_path']}")
        print(f"\nPDF Files:")
        for pdf in info['pdf_files']:
            print(f"  - {pdf}")
        print(f"{'='*60}")

def delete_agent(rag_system):
    print("\n--- DELETE AGENT ---")
    agents = rag_system.list_agents()
    
    if not agents:
        print("[ERROR] No agents available")
        return
    
    print("\nAvailable agents:")
    for i, agent in enumerate(agents, 1):
        print(f"  {i}. {agent['name']}")
    
    choice = input("\nSelect agent number to delete: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(agents):
            print("[ERROR] Invalid selection")
            return
        agent_name = agents[idx]['name']
    except ValueError:
        print("[ERROR] Invalid input")
        return
    
    confirm = input(f"\nAre you sure you want to delete '{agent_name}'? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("[INFO] Deletion cancelled")
        return
    
    result = rag_system.delete_agent(agent_name)
    if result["success"]:
        print(f"\n[SUCCESS] {result['message']}")
    else:
        print(f"\n[ERROR] {result['error']}")

def main():
    print_header()
    rag_system = RAGAgentSystem()
    
    while True:
        print_menu()
        command = input("Enter command: ").strip().lower()
        
        if command in ['1', 'list']:
            list_agents(rag_system)
        elif command in ['2', 'create']:
            create_agent(rag_system)
        elif command in ['3', 'query']:
            query_agent(rag_system)
        elif command in ['4', 'info']:
            show_agent_info(rag_system)
        elif command in ['5', 'delete']:
            delete_agent(rag_system)
        elif command in ['6', 'exit', 'quit']:
            print("\n[INFO] Exiting... Goodbye!\n")
            sys.exit(0)
        else:
            print("[ERROR] Invalid command. Please try again.")

if __name__ == "__main__":
    main()