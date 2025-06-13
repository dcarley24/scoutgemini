# gemini_utils.py

import os
import json
import re
import google.generativeai as genai

if os.getenv("GEMINI_API_KEY_SCOUT"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY_SCOUT"))
else:
    print("Warning: GEMINI_API_KEY_SCOUT environment variable not set.")

model = genai.GenerativeModel('gemini-1.5-flash')

# MODIFICATION: New function to process debrief notes
def generate_debrief(snapshot, raw_notes):
    """
    Processes raw meeting notes and generates a structured debrief summary.
    """
    prospect_role = snapshot['persona']
    prompt = f"""
You are an AI assistant helping a sales rep process their raw, messy meeting notes. Your task is to turn these notes into a clean, structured summary that can be saved to a CRM.

**Original Prospect Info:**
- Name: {snapshot['name']}
- Role: {prospect_role}
- Pre-Meeting Discovery Points: {snapshot['discovery']}

**Raw Meeting Notes:**
---
{raw_notes}
---

**Instructions:**
Analyze the raw notes and generate a debrief with the following sections:
1.  **Key Takeaways:** A 2-4 sentence summary of the most important points from the conversation.
2.  **Identified Pain Points:** A bulleted list of specific problems, needs, or challenges the prospect mentioned.
3.  **Next Steps & Action Items:** A bulleted list of concrete actions for the sales rep.
4.  **Updated Discovery:** Briefly note if the conversation confirmed or changed any of the initial discovery points.
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating debrief with Gemini: {e}")
        return f"Error processing notes: {str(e)}"

def generate_snapshot(name, industry, size, region, tags, prospect_role):
    """
    Generates the initial company snapshot, summary, and discovery points,
    tailored to the prospect's likely role.
    """
    tag_string = ', '.join(tags)
    prompt = f"""
You are helping a consultative AE prep for an unexpected meeting. Your goal is to provide talking points tailored to the prospect's specific role.

**Prospect's Role:** {prospect_role}

**Company Info:**
- Name: {name}
- Industry: {industry}
- Size: {size}
- Region: {region}
- Inferred Needs: {tag_string}

**Instructions:**
First, write a 3–5 sentence summary of the company, framed for a sales conversation.

Then, tailor the following points specifically for a **{prospect_role}**:
1.  **Three Conversation Starters:** Questions or observations to open the dialogue.
2.  **Anticipated Focus Areas:** What this person likely cares about most (e.g., budget, security, team skills, strategy).
3.  **Potential Objections:** Hurdles or pushback you might expect from this role.

**Role-Based Guidance:**
-   **Executive:** Focus on business value, ROI, strategic impact. Avoid deep technical jargon.
-   **Executive Technical:** Bridge strategy with technology. Discuss business outcomes of tech choices, scalability, and security.
-   **Technical:** Focus on implementation, features, and how it works. Be prepared for detailed questions.
-   **Technical Decision Maker:** Blend technical credibility with a business case. They care about how it solves a team/budget problem.
"""
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        lines = content.splitlines()
        split_index = next((i for i, line in enumerate(lines) if line.strip().lstrip('*- ').startswith("1.")), None)
        if split_index is not None:
            summary = "\n".join(lines[:split_index]).strip()
            discovery = "\n".join(lines[split_index:]).strip()
        else:
            summary = "Could not parse summary from response."
            discovery = content
        return summary, discovery
    except Exception as e:
        print(f"Error generating snapshot with Gemini: {e}")
        return f"Error: {e}", ""

def generate_nudge_update(snapshot, new_nudge):
    """
    Generates updated discovery points based on a user's nudge and the original prospect role.
    """
    prospect_role = snapshot['persona']
    prompt = f"""
Update the AE's discovery plan based on new info, keeping the prospect's role in mind.

**Original Role:** {prospect_role}

**New Information (Nudge):** {new_nudge}

**Original Snapshot:**
- Prospect: {snapshot['name']}
- Industry: {snapshot['industry']}
- Size: {snapshot['size']}

Based on the new information, provide three updated follow-up questions or talking points that are sharply focused for a **{prospect_role}**.
1. ...
2. ...
3. ...
"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating nudge update with Gemini: {e}")
        return f"Error generating new insights: {str(e)}"

def autofill_company_details(name):
    """
    Autofills company details by returning a JSON object.
    """
    prompt = f"""
Given the company name "{name}", estimate and return this JSON:
{{
  "industry": "...",
  "size": "...",
  "region": "..."
}}
Only return valid JSON. Do not include ```json or any other text.
"""
    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
            return json.loads(json_text)
        else:
            print(f"Error: No valid JSON found in Gemini response for '{name}'")
            return {'error': 'Failed to extract JSON from response.'}
    except Exception as e:
        print(f"Error parsing autofill JSON from Gemini: {e}")
        return {'error': str(e)}
