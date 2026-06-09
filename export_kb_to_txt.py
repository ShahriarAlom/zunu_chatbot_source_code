import urllib.request
import json
import os
import sys

def export_kb():
    print("==================================================")
    print("RealDealRide Knowledge Base Export to TXT Utility")
    print("==================================================")

    # 1. Prompt for Backend URL
    default_url = "http://localhost:8085"
    url_input = input(f"Enter the chatbot backend API URL [default: {default_url}]: ").strip()
    base_url = url_input if url_input else default_url

    # Clean URL slashes
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    export_url = f"{base_url}/knowledge/export"
    print(f"\nFetching knowledge documents from {export_url}...")

    # 2. Query the /knowledge/export API
    try:
        req = urllib.request.Request(export_url, method="GET")
        with urllib.request.urlopen(req) as res:
            documents = json.loads(res.read().decode('utf-8'))
    except Exception as e:
        print(f"\nERROR: Failed to connect or retrieve backup from chatbot API: {e}")
        print("Please verify the chatbot backend is running and the URL is correct.")
        sys.exit(1)

    if not documents:
        print("\nNo policy documents found in the database to export.")
        return

    # 3. Create Export Directory
    out_dir = "exported_kb_txt"
    os.makedirs(out_dir, exist_ok=True)
    print(f"\nFound {len(documents)} documents. Exporting to folder: '{out_dir}/'...")

    # 4. Save each document to its own TXT file
    success_count = 0
    for idx, doc in enumerate(documents, start=1):
        title = doc.get("title", f"Document_{idx}")
        source_text = doc.get("source_text", "")
        file_name = doc.get("file_name")

        if not file_name:
            # Construct a clean filename if not present
            clean_title = title.replace(" ", "_").lower()
            file_name = f"{clean_title}.txt"
        else:
            # Replace extension to .txt to comply with the new txt-first standard
            file_name = os.path.splitext(file_name)[0] + ".txt"

        file_path = os.path.join(out_dir, file_name)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(source_text)
            print(f"  [{idx}/{len(documents)}] Exported: {file_name}")
            success_count += 1
        except Exception as e:
            print(f"  [{idx}/{len(documents)}] Failed to save {file_name}: {e}")

    print("\n==================================================")
    print(f"EXPORT COMPLETED! Successfully exported {success_count} files.")
    print(f"To populate a new Docker container with these policies:")
    print(f"1. Copy the .txt files from the '{out_dir}' folder.")
    print(f"2. Paste them into the 'requirements/knowledge_Base_doc/' directory.")
    print(f"3. Rebuild the containers using: docker-compose up -d --build")
    print("==================================================")

if __name__ == "__main__":
    export_kb()
