from memory import collection

results = collection.get()

if not results["metadatas"]:
    print("Memory is empty.")
else:
    print(f"Total investigations stored: {len(results['metadatas'])}\n")
    print("=" * 60)
    for i, (doc, metadata, entry_id) in enumerate(zip(results["documents"], results["metadatas"], results["ids"]), 1):
        print(f"\n[{i}] ID: {entry_id}")
        print(f"    Subject: {metadata.get('subject', 'Unknown')}")
        print(f"    Query: {metadata.get('query', 'Unknown')}")
        print(f"    Date: {metadata.get('timestamp', 'Unknown')}")
        print(f"    Report length: {len(doc)} chars")
        print(f"    Report preview: {doc[:300]}...")
        print("-" * 60)
