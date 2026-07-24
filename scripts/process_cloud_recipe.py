import os
import glob
import json
import shutil
from google import genai
from google.genai import types
from PIL import Image

# Connect using the new official Google GenAI SDK
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_ID = 'gemini-2.5-flash'

INTAKE_DIR = "intake"
ARCHIVE_DIR = "archive/scans"
OUTPUT_DIR = "content"
ASSET_DIR = "content/assets/scans"

SYSTEM_PROMPT = """
You are an expert culinary archivist for Cucina Mezzaluna. 
SYNTHESIZE ALL PAGES INTO ONE SINGLE, COHESIVE RECIPE OBJECT.

CRITICAL ORGANIZATION RULES:
1. "category" MUST be strictly ONE of these broad top-level folders: Appetizers, Beverages, Bread, Desserts, Entrees, Salads, Sauces, Sides, Snacks, Soups. Do not create sub-categories!
2. Use "tags" for granular micro-organization. Include specific descriptors (e.g., cake, layered, vintage, chocolate).
3. Look closely at the handwriting for any attribution or author names and extract it as "source".

Return ONLY a raw JSON object with:
{
    "title": "Clean Recipe Name",
    "category": "Desserts",
    "source": "Name written on card, or 'Unattributed'",
    "tags": ["cake", "layered", "vintage", "chocolate"],
    "prep_time": "15 mins",
    "cook_time": "45 mins",
    "servings": "4",
    "description": "A 2-sentence description.",
    "ingredients": ["1 cup flour"],
    "instructions": ["Step 1..."],
    "json_ld_schema": "A valid stringified JSON-LD Recipe schema object."
}
"""

def process_intake():
    os.makedirs(INTAKE_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ASSET_DIR, exist_ok=True)

    all_files = glob.glob(os.path.join(INTAKE_DIR, "**", "*.*"), recursive=True)

    for file_path in all_files:
        if os.path.isdir(file_path) or file_path.endswith('.gitkeep'):
            continue

        filename = os.path.basename(file_path)
        rel_path = os.path.relpath(file_path, INTAKE_DIR)
        path_parts = os.path.split(rel_path)
        collection_name = path_parts[0] if len(path_parts) > 1 and path_parts[0] != "" else "General Archive"

        print(f"🥘 Processing [{collection_name}] scan: {filename}...")
        
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
            
            if file_path.lower().endswith('.pdf'):
                sample_file = client.files.upload(file=file_path)
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[SYSTEM_PROMPT, sample_file],
                    config=config
                )
                client.files.delete(name=sample_file.name)
                save_and_archive(response.text, [file_path], filename, collection_name, is_pdf=True)
            elif file_path.lower().endswith(('png', 'jpg', 'jpeg', 'heic')):
                img = Image.open(file_path)
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=[SYSTEM_PROMPT, img],
                    config=config
                )
                save_and_archive(response.text, [file_path], filename, collection_name, img_obj=img)
        except Exception as e:
            print(f"❌ Failed processing on {filename}: {e}")

def save_and_archive(json_text, source_files, archive_name, collection_name, is_pdf=False, img_obj=None):
    data = json.loads(json_text)
    title = data.get('title', 'Untitled Dish')
    
    category = data.get('category', 'Other').strip().title()
    if category not in ["Appetizers", "Beverages", "Bread", "Desserts", "Entrees", "Salads", "Sauces", "Sides", "Snacks", "Soups"]:
        category = "Other"

    safe_base = title.lower().replace(" ", "-").replace("/", "-")
    safe_filename = safe_base + ".md"
    webp_filename = safe_base + ".webp"
    
    webp_embed = ""
    if img_obj:
        webp_path = os.path.join(ASSET_DIR, webp_filename)
        img_obj.convert("RGB").save(webp_path, "WEBP", quality=82)
        webp_embed = f"\n![Original Handwritten Card](/assets/scans/{webp_filename})\n"
    
    markdown_content = f"""---
title: "{title}"
category: "{category}"
collection: "{collection_name}"
source: "{data.get('source', 'Unattributed')}"
tags: {json.dumps(data.get('tags', []))}
description: "{data.get('description', '')}"
prep_time: "{data.get('prep_time', '')}"
cook_time: "{data.get('cook_time', '')}"
servings: "{data.get('servings', '')}"
published: true
---

# {title}

> **Collection:** {collection_name} | **Original Attribution:** {data.get('source', 'Unattributed')}
> {data.get('description', '')}
{webp_embed}
| Prep Time | Cook Time | Servings |
| :--- | :--- | :--- |
| {data.get('prep_time', 'N/A')} | {data.get('cook_time', 'N/A')} | {data.get('servings', 'N/A')} |

## Ingredients
{chr(10).join([f"- [ ] {ing}" for ing in data.get('ingredients', [])])}

## Instructions
{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(data.get('instructions', []))])}

---
*Digitized for Cucina Mezzaluna Archive*

<script type="application/ld+json">
{data.get('json_ld_schema', '{}')}
</script>
"""
    cat_dir = os.path.join(OUTPUT_DIR, category)
    os.makedirs(cat_dir, exist_ok=True)
    out_path = os.path.join(cat_dir, safe_filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"✅ Generated Page in [{category}]: {out_path}")

    archive_dest = os.path.join(ARCHIVE_DIR, collection_name)
    os.makedirs(archive_dest, exist_ok=True)
    for file_path in source_files:
        shutil.move(file_path, os.path.join(archive_dest, os.path.basename(file_path)))

if __name__ == "__main__":
    process_intake()
