import os
import glob
import json
import shutil
import time
from google import genai
from google.genai import types
from PIL import Image

# Connect using the official Google GenAI SDK
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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

    # THE FAIL-SAFE RELAY RACE: Automatically shifts gears if a model is overloaded or out of quota!
    model_fallback_list = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite']

    for file_path in all_files:
        if os.path.isdir(file_path) or file_path.endswith('.gitkeep'):
            continue

        filename = os.path.basename(file_path)
        rel_path = os.path.relpath(file_path, INTAKE_DIR)
        path_parts = os.path.split(rel_path)
        collection_name = path_parts[0] if len(path_parts) > 1 and path_parts[0] != "" else "General Archive"

        print(f"🥘 Processing [{collection_name}] scan: {filename}...")
        
        file_success = False
        current_model_index = 0
        
        while current_model_index < len(model_fallback_list):
            active_model = model_fallback_list[current_model_index]
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
                
                if file_path.lower().endswith('.pdf'):
                    sample_file = client.files.upload(file=file_path)
                    response = client.models.generate_content(
                        model=active_model,
                        contents=[SYSTEM_PROMPT, sample_file],
                        config=config
                    )
                    client.files.delete(name=sample_file.name)
                    save_and_archive(response.text, [file_path], filename, collection_name, is_pdf=True)
                elif file_path.lower().endswith(('png', 'jpg', 'jpeg', 'heic')):
                    img = Image.open(file_path)
                    response = client.models.generate_content(
                        model=active_model,
                        contents=[SYSTEM_PROMPT, img],
                        config=config
                    )
                    save_and_archive(response.text, [file_path], filename, collection_name, img_obj=img)
                
                file_success = True
                time.sleep(4.5)
                break # Success! Move to next file
                
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    print(f"⚠️ Model {active_model} is busy or rate-limited (503/429).")
                    current_model_index += 1
                    if current_model_index < len(model_fallback_list):
                        print(f"🔄 FAIL-SAFE ACTIVATED: Switching to backup model -> {model_fallback_list[current_model_index]}...")
                        time.sleep(3)
                    else:
                        print("🛑 All backup models are currently experiencing high demand!")
                        break
                else:
                    print(f"❌ Failed processing on {filename}: {e}")
                    break

        if not file_success:
            print(f"⚠️ Skipping {filename} for this run due to server errors.")

def save_and_archive(json_text, source_files, archive_name, collection_name, is_pdf=False, img_obj=None):
    data = json.loads(json_text)
    title = data.get('title', 'Untitled Dish').strip().title()
    safe_title = title.replace("/", "-").replace("\\", "-")
    
    category = data.get('category', 'Other').strip().title()
    if category not in ["Appetizers", "Beverages", "Bread", "Desserts", "Entrees", "Salads", "Sauces", "Sides", "Snacks", "Soups"]:
        category = "Other"

    safe_base = safe_title.lower().replace(" ", "-")
    safe_filename = safe_base + ".md"
    webp_filename = safe_base + ".webp"
    
    webp_embed = ""
    if img_obj:
        webp_path = os.path.join(ASSET_DIR, webp_filename)
        img_obj.convert("RGB").save(webp_path, "WEBP", quality=82)
        webp_embed = f"\n![Original Handwritten Card](/assets/scans/{webp_filename})\n"
    
    # FIXED: json.dumps() used for all metadata fields to perfectly escape internal quotes and prevent Cloudflare crashes!
    markdown_content = f"""---
title: {json.dumps(safe_title)}
category: {json.dumps(category)}
collection: {json.dumps(collection_name)}
source: {json.dumps(data.get('source', 'Unattributed'))}
tags: {json.dumps(data.get('tags', []))}
description: {json.dumps(data.get('description', ''))}
prep_time: {json.dumps(data.get('prep_time', ''))}
cook_time: {json.dumps(data.get('cook_time', ''))}
servings: {json.dumps(data.get('servings', ''))}
date: "2026-07-30"
draft: false
recipe: {json.dumps(data.get('json_ld_schema', dict()))}
---

# {safe_title}

> **Collection:** {collection_name} | **Original Attribution:** {data.get('source', 'Unattributed')}
> *{data.get('description', '')}*
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
