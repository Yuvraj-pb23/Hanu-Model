import google.generativeai as genai
import PIL.Image
import pandas as pd
import json
import re
import os
import time

# ==========================================
# CONFIGURATION
# ==========================================
# PASTE YOUR GEMINI API KEY HERE
API_KEY = "AIzaSyC5H5h0KSIvpbs_nDDKk1aHRZ65GFX9G1k"

# Folder Configuration
INPUT_FOLDER = "31+140 - 51+300  PAGE 1"
OUTPUT_FOLDER = "output_processed"
OUTPUT_EXCEL_FILE = "31+140 - 51+300  PAGE 1.xlsx"

# Configure the API
genai.configure(api_key=API_KEY)

# Ensure output directory exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ==========================================
# ADVANCED SIGN RULES CONFIGURATION
# ==========================================
SIGN_CATEGORIES = {
    "MANDATORY": {
        "ref_image": "mandatory.png",
        "rules": (
            "in the ref_image i will provide you one example of mandatory sign it will look excatly like that only symbol should change on applying this on data or in rare case the colour should be blue in blue colour sign only arrow are give in white colour other wise the symbol in black  "
        )
    },
    "CAUTIONARY": {
        "ref_image": "caustonary.png",
        "rules": (
            "In the refrence image i will provide you one example of caustonary sign. the caustonary sign exactly look same as shown in refrence image the symbol should be changed at a time of applying on data."
        )
    },
    "CHEVRON": {
        "ref_image": "cevron.png",
        "rules": (
            "the ref_image show exactly how cevron is looking the small sign in this yellow colour and v shape is made from black colour"
        )
    },
    "HAZARD": {
        "ref_image": "hazard.png",
        "rules": (
            "the ref_image show how the hazard look the black and yellow strip it will look exact same "
        )
    },
    "INFORMATORY": {
        "ref_image": "informatory.png", # Optional
        "rules": (
            "it is a guide sign who can guide the people in road example:petrol pump sign after some distance like that it will give the direction.also i will provide you the ref_image the symbol and name of the city and icon of basic thing like hospital ,school, bustand and how much the city far like this kind of info is given in this type of sign they general are rectangular and green bg also they are blue yellow etc. but not with white baground"
        )
    }
}

def load_reference_images():
    """Loads reference images into memory if they exist in the folder."""
    loaded_images = {}
    for category, config in SIGN_CATEGORIES.items():
        img_path = config["ref_image"]
        if os.path.exists(img_path):
            try:
                loaded_images[category] = PIL.Image.open(img_path)
                print(f"  [+] Loaded reference image for {category}: {img_path}")
            except Exception as e:
                print(f"  [-] Failed to load {img_path}: {e}")
                loaded_images[category] = None
        else:
            loaded_images[category] = None
    return loaded_images

def detect_specific_sign(plan_img, category, rules, ref_img):
    """Makes a dedicated API call to find ONLY one specific type of sign."""
    model = genai.GenerativeModel('gemini-2.5-pro')

    prompt_intro = f"You are an expert Civil Engineer. Your ONLY task right now is to find and extract data for **{category}** signs."

    prompt_task = f"""
    RULES FOR {category} SIGNS:
    {rules}

    DO NOT detect any other type of sign. ONLY detect {category} signs.

    Data to extract for each {category} sign found:
    1. Identify Chainage: Look at the exact location of the detected sign on the drawing. Find the geographically NEAREST chainage which is writen like 42+950 etc. like that 
       - For example, if the sign is closest to the text "7+100", output "7+100". 
       - If it is closer to the text "7+200", output "7+200". 
       - It MUST be the absolute closest chainage marker text to the sign.
    2. Identify Side: Determine if the sign is "MCW LHS" or "MCW RHS" relative to increasing chainage.

    Output Format:
    Return a strictly formatted JSON list of objects. If NO {category} signs are found, return an empty list: []
    
    Format Example:[
      {{"label": "{category}", "chainage": "7+100", "side": "MCW LHS"}},
      {{"label": "{category}", "chainage": "7+200", "side": "MCW RHS"}}
    ]
    """

    prompt_parts = [prompt_intro]

    # Insert reference image and specific instruction if it exists
    if ref_img:
        prompt_parts.append(f"*** VISUAL TEMPLATE / REFERENCE FOR {category} ***")
        prompt_parts.append(ref_img)
        prompt_parts.append(f"Use the image above as the rule for {category}. Remember the specific rules applied to this template.")

    prompt_parts.extend([
        "Now, analyze the following Highway Sign Board Plan:",
        plan_img,
        prompt_task
    ])

    try:
        response = model.generate_content(prompt_parts)
        text_response = response.text.strip()
        
        # Clean Markdown formatting from JSON
        if text_response.startswith("```"):
            text_response = re.sub(r"^```json|^```|```$", "", text_response, flags=re.MULTILINE).strip()
            
        data = json.loads(text_response)
        return data
        
    except Exception as e:
        # If the model errors out or returns blank, assume 0 found
        return []

def process_folder():
    master_excel_data =[]
    
    print("--- Initialization ---")
    reference_images = load_reference_images()
    print("-" * 40)

    valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(valid_extensions)]
    
    if not files:
        print(f"No plan images found in '{INPUT_FOLDER}'.")
        return

    print(f"Found {len(files)} plan images. Starting isolated batch processing...\n")

    for i, filename in enumerate(files):
        print(f"=== Processing Image {i+1}/{len(files)}: {filename} ===")
        file_path = os.path.join(INPUT_FOLDER, filename)
        
        try:
            plan_img = PIL.Image.open(file_path)
        except Exception as e:
            print(f"  > Error opening {filename}: {e}")
            continue

        # Loop through each category independently
        for category, config in SIGN_CATEGORIES.items():
            print(f"  > Hunting for {category} signs... ", end="", flush=True)
            
            ref_img = reference_images.get(category)
            detected_items = detect_specific_sign(plan_img, category, config["rules"], ref_img)
            
            print(f"Found {len(detected_items)}")
            
            # Store results
            for item in detected_items:
                master_excel_data.append({
                    "Type of Sign Board": item.get('label', category).upper(),
                    "Chainage Location": item.get('chainage', 'N/A'),
                    "Side": item.get('side', 'MCW LHS') 
                })
            
            # Sleep between API calls to prevent Rate Limit Errors
            time.sleep(3) 

        print(f"  > Finished all categories for {filename}\n")

    # Export Combined Excel
    if master_excel_data:
        df = pd.DataFrame(master_excel_data)
        
        cols = ["Type of Sign Board", "Chainage Location", "Side"]
        df = df[cols]
        
        # Sort output neatly by Chainage
        df = df.sort_values(by=["Chainage Location"])
        
        full_excel_path = os.path.join(OUTPUT_FOLDER, OUTPUT_EXCEL_FILE)
        df.to_excel(full_excel_path, index=False)
        print(f"==========================================")
        print(f"SUCCESS! Excel generated: {full_excel_path}")
        print(f"Total Signs Detected Across All Categories: {len(df)}")
        print(f"==========================================")
    else:
        print("\nNo signs detected in any images.")

def process_uploaded_images(image_paths):
    master_data = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    reference_images = {}
    
    for category, config in SIGN_CATEGORIES.items():
        img_path = os.path.join(base_dir, config["ref_image"])
        if os.path.exists(img_path):
            try:
                reference_images[category] = PIL.Image.open(img_path)
            except Exception:
                reference_images[category] = None
        else:
            reference_images[category] = None

    for i, file_path in enumerate(image_paths):
        try:
            plan_img = PIL.Image.open(file_path)
        except Exception as e:
            continue

        for category, config in SIGN_CATEGORIES.items():
            ref_img = reference_images.get(category)
            detected_items = detect_specific_sign(plan_img, category, config["rules"], ref_img)
            
            for index, item in enumerate(detected_items):
                master_data.append({
                    "id": f"SB-{category[:3].upper()}-{i+1}-{index+1}",
                    "page": os.path.basename(file_path),
                    "coords": item.get('chainage', 'N/A') + " " + item.get('side', ''),
                    "class": item.get('label', category).upper(),
                    "conf": 99.0
                })
            time.sleep(2)

    return master_data

if __name__ == "__main__":
    process_folder()