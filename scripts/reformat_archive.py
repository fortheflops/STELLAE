import os
import json
import shutil
from google import genai
from google.genai import types

# Connect using the modern Google GenAI SDK
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_ID = 'gemini-3.5-flash'

CONTENT_DIR = "content"

LIBRARIAN_PROMPT = """
You are an expert digital librarian and culinary archivist for Cucina Mezzaluna.
Your task is to take an older, poorly formatted recipe markdown file and standardize it into our strict archival schema.

CRITICAL LIBRARIAN RULES:
1. "title": Clean, proper Title Case (e.g., "Mocha Rolls", "Chilled Spiced Rhubarb Soup").
2. "category": Strictly ONE of: Appetizers, Beverages, Bread, Desserts, Entrees, Salads, Sauces, Sides, Snacks, Soups.
3. "author": Extract the author or attribution if mentioned in the text (default to "Unknown" if not found).
4. "tags": Include descriptive archival tags (e.g., dish type, primary ingredients, historical era like "vintage" or "1960s").
5. "ingredients_table": Parse all ingredients into an array of objects with "measurement" and "ingredient". Wrap foundational ingredients in wikilinks (e.g., [[Rhubarb]], [[Vanilla]]).
6. "instructions": Chronological steps. MUST BOLD all ingredient names and exact measurements inside the steps (e.g., "Whisk the **2 Tbsp cornstarch** into the **cold water**...").
7. "existing_image_path": If the raw markdown contains an image link (e.g., ![](/assets/scans/foo.webp) or ![](Assets/foo.webp)), extract exactly that path string so we can preserve it! If none exists, return null.

Return ONLY a raw JSON object with:
{
    "title": "Clean Title Case Name",
    "category": "Desserts",
    "author": "Patsy's collection",
    "tags": ["vintage", "rhubarb", "dessert-soup"],
    "prep_time": "15 mins",
    "cook_time": "20 mins",
    "servings": "4",
    "description": "A 2-sentence SEO optimized archival description.",
    "existing_image_path": "/assets/scans/example.webp",
    "ingredients_table": [
        {"measurement": "4 Cups", "ingredient": "Diced [[Rhubarb]]"}
    ],
    "instructions": [
        "In a saucepan, combine the diced **rhubarb** and **4 cups of water**...",
        "Simmer for **20 minutes**."
    ],
    "json_ld_schema": "A valid stringified JSON-LD Recipe schema object."
}
"""

def reformat_archive():
    print(f"🔍 Searching for recipe files in '{CONTENT_DIR}/' subfolders...")
    
    # Recursively traverse every subfolder inside content/
    all_md_files = []
    for root, dirs, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.lower().endswith('.md'):
                all_md_files.append(os.path.join(root, file))
                
    print(f"📖 Found {len(all_md_files)} markdown recipe file(s).")
    
    for file_path in all_md_files:
        filename = os.path.basename(file_path)
        
        # Skip system landing pages and Quartz navigation files
        if filename.lower() in ["index.md", "about.md", "contact.md", "404.md"]:
            continue
            
        print(f"📚 Librarian AI processing: {filename} ({file_path})...")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
                
            config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[LIBRARIAN_PROMPT, f"RAW RECIPE FILE TO REFORMAT:\n\n{raw_content}"],
                config=config
            )
            
            data = json.loads(response.text)
            save_upgraded_recipe(file_path, data)
            
        except Exception as e:
            print(f"❌ Failed librarian reformat on {filename}: {e}")

def save_upgraded_recipe(old_file_path, data):
    raw_title = data.get('title', 'Untitled Dish').strip().title()
    safe_title = raw_title.replace("/", "-").replace("\\", "-")
    new_filename = safe_title + ".md"
    
    category = data.get('category', 'Other').strip().title()
    if category not in ["Appetizers", "Beverages", "Bread", "Desserts", "Entrees", "Salads", "Sauces", "Sides", "Snacks", "Soups"]:
        category = "Other"
        
    img_path = data.get('existing_image_path')
    webp_embed = ""
    
    if img_path:
        old_img_full_path = os.path.join(CONTENT_DIR, img_path.lstrip('/'))
        if os.path.exists(old_img_full_path):
            img_name = os.path.basename(old_img_full_path)
            new_img_full_path = os.path.join("content/assets/scans", img_name)
            os.makedirs("content/assets/scans", exist_ok=True)
            
            if os.path.abspath(old_img_full_path) != os.path.abspath(new_img_full_path):
                shutil.move(old_img_full_path, new_img_full_path)
                
            webp_embed = f"\n---\n## Original Recipe Card\n![Original Handwritten Card](/assets/scans/{img_name})\n"
        else:
            webp_embed = f"\n---\n## Original Recipe Card\n![Original Handwritten Card]({img_path})\n"

    # Clean up empty legacy Assets folders
    old_dir = os.path.dirname(old_file_path)
    legacy_assets_folder = os.path.join(old_dir, "Assets")
    if os.path.exists(legacy_assets_folder) and not os.listdir(legacy_assets_folder):
        os.rmdir(legacy_assets_folder)

    table_rows = "\n".join([f"| {row.get('measurement', '')} | {row.get('ingredient', '')} |" for row in data.get('ingredients_table', [])])
    
    markdown_content = f"""---
title: "{safe_title}"
description: "{data.get('description', '')}"
draft: false
tags: {json.dumps(data.get('tags', []))}
date: "2026-07-24"
recipe: {json.dumps(data.get('json_ld_schema', '{}'))}
---

*{data.get('description', '')}*

### Author
{data.get('author', 'Unknown')}

---

## Recipe

| Measurements | Ingredients |
| :--- | :--- |
{table_rows}

---

## Instructions
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(data.get('instructions', []))])}
{webp_embed}
"""
    cat_dir = os.path.join(CONTENT_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)
    new_file_path = os.path.join(cat_dir, new_filename)
    
    with open(new_file_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"✨ Upgraded -> [{category}]: {new_filename}")
    
    if os.path.abspath(old_file_path) != os.path.abspath(new_file_path):
        os.remove(old_file_path)
        print(f"🗑️ Cleaned up old file: {old_file_path}")

if __name__ == "__main__":
    reformat_archive()
