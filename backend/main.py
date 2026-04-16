from fastapi import FastAPI
import json
import re
import os
import httpx

app = FastAPI()

@app.get("/")
def root():
    return {"status": "backend running"}

@app.post("/ai-proposal")
def ai():
    return {
        "voorstel": "Voorziening toegekend",
        "onderbouwing": "Voldoet aan beleid",
        "risico_score": 0.2
    }

@app.post("/build-wmo-prompt")
def build_wmo_prompt(applicant: dict):
    prompt = f"""
Je bent een WMO-beoordelaar bij een Nederlandse gemeente. 
Beoordeel de onderstaande aanvraag op basis van de Wet maatschappelijke ondersteuning 2015.

## Beoordelingscriteria (WMO 2015):
1. De aanvrager is ingezetene van de gemeente
2. De aanvrager heeft beperkingen in zelfredzaamheid of participatie
3. De aanvrager kan de beperking niet zelf of met hulp van het sociale netwerk oplossen
4. De ondersteuning is niet al gedekt door een andere wet (zoals Zvw of Wlz)
5. Eigen kracht en sociaal netwerk zijn onvoldoende om de hulpvraag op te lossen

## Aanvraaggegevens:
- Naam: {applicant.get('naam')}
- Leeftijd: {applicant.get('leeftijd')}
- Woonplaats: {applicant.get('woonplaats')}
- Hulpvraag: {applicant.get('hulpvraag')}
- Beperking(en): {applicant.get('beperkingen')}
- Sociaal netwerk beschikbaar: {applicant.get('sociaalNetwerk')}
- Reeds andere zorg/ondersteuning: {applicant.get('andereZorg')}
- Toelichting aanvrager: {applicant.get('toelichting')}

## Instructies:
Geef je beoordeling ALLEEN als JSON in dit formaat, zonder extra tekst:
{{
  "eligible": true of false,
  "verdict": "Toegekend" of "Afgewezen" of "Nader onderzoek vereist",
  "score": 1-10,
  "onderbouwing": "Korte motivatie van het besluit",
  "aandachtspunten": ["punt 1", "punt 2"],
  "aanbevolen_voorziening": "bijv. huishoudelijke hulp, begeleiding, etc. of null"
}}
"""
    return {"prompt": prompt, "applicant": applicant}

@app.post("/call-API-wmo")
async def call_api_wmo(data: dict):
    prompt = data.get("prompt")
    api_key = os.getenv("GOOGLE_AI_KEY")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "systemInstruction": {
            "parts": [{
                "text": "Je bent een WMO-beoordelaar bij een Nederlandse gemeente. \nJe beoordeelt aanvragen op basis van de Wet maatschappelijke ondersteuning 2015.\nJe geeft je beoordeling ALTIJD en UITSLUITEND als geldig JSON object, zonder extra tekst, uitleg of markdown."
            }]
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1000,
            "responseMimeType": "application/json",
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=30.0)
        
        if response.status_code != 200:
            error_text = response.text
            raise Exception(f"Gemini API error {response.status_code}: {error_text}")

        resp_data = response.json()
        raw_text = resp_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
        
        if not raw_text:
            raise Exception("No response content from Gemini")
            
        return {"text": raw_text}

@app.post("/parse-wmo-response")
def parse_wmo_response(data: dict):
    raw = data.get("text", "")
    # Remove markdown code blocks if the AI included them
    cleaned = re.sub(r"```json|```", "", raw).strip()

    try:
        result = json.loads(cleaned)
    except Exception:
        result = {
            "eligible": None,
            "verdict": "Onbekend",
            "score": None,
            "onderbouwing": "Kon niet worden geparsed.",
            "aandachtspunten": ["JSON parsing mislukt", raw[:200]],
            "aanbevolen_voorziening": None
        }

    # Pass along the original applicant data too for the fairness check
    applicant = data.get("applicant")

    return {"wmoResult": result, "applicant": applicant}

@app.post("/fairness-prompt")
def fairness_prompt(data: dict):
    wmoResult = data.get("wmoResult", {})
    applicant = data.get("applicant", {})

    prompt = f"""
Je bent een onafhankelijke AI-ethiek beoordelaar. Je taak is om een WMO-besluit te controleren op eerlijkheid, bias en risico.

## Het oorspronkelijke besluit:
- Verdict: {wmoResult.get('verdict')}
- Score: {wmoResult.get('score')}/10
- Onderbouwing: {wmoResult.get('onderbouwing')}
- Aandachtspunten: {json.dumps(wmoResult.get('aandachtspunten', []))}

## Aanvrager profiel:
- Leeftijd: {applicant.get('leeftijd')}
- Hulpvraag: {applicant.get('hulpvraag')}
- Beperkingen: {applicant.get('beperkingen')}
- Sociaal netwerk: {applicant.get('sociaalNetwerk')}
- Andere zorg: {applicant.get('andereZorg')}

## Controleer op de volgende risicofactoren:
1. **Bias risico** — Is het besluit mogelijk beïnvloed door leeftijd, geslacht, etniciteit of sociaaleconomische factoren die niet relevant zijn voor de WMO?
2. **Onderbouwing kwaliteit** — Is de motivatie concreet en traceerbaar, of vaag en generiek?
3. **Afwijkingsrisico** — Wijkt dit besluit significant af van wat een menselijke beoordelaar waarschijnlijk zou beslissen?
4. **Kwetsbare aanvrager** — Zijn er signalen dat de aanvrager extra kwetsbaar is (hoge leeftijd, complexe situatie, geen sociaal netwerk)?
5. **Ontbrekende informatie** — Zijn er cruciale gegevens die ontbreken voor een verantwoord besluit?

## Instructies:
Geef je beoordeling ALLEEN als JSON in dit formaat, zonder extra tekst:
{{
  "riskLevel": "low" of "high",
  "riskScore": 1-10,
  "biasIndicators": ["indicator 1", "indicator 2"],
  "fairnessIssues": ["issue 1", "issue 2"],
  "missingInformation": ["ontbrekend gegeven 1"],
  "recommendHumanReview": true of false,
  "reviewReason": "Korte uitleg waarom menselijke review wel/niet nodig is",
  "overallAssessment": "Kort oordeel over de kwaliteit en eerlijkheid van het besluit"
}}

Regels:
- riskLevel is "high" als riskScore >= 6, of als recommendHumanReview true is
- Een afwijzing (verdict = Afgewezen) is NIET automatisch hoog risico — beoordeel puur op eerlijkheid en onderbouwing
- Een toewijzing kan ook hoog risico zijn als de onderbouwing zwak is
"""
    return {"fairnessPrompt": prompt, "wmoResult": wmoResult, "applicant": applicant}

@app.post("/call-API-fairness")
async def call_api_fairness(data: dict):
    fairness_prompt = data.get("fairnessPrompt")
    wmo_result = data.get("wmoResult")
    applicant = data.get("applicant")
    api_key = os.getenv("GOOGLE_AI_KEY")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "systemInstruction": {
            "parts": [{
                "text": "Je bent een onafhankelijke AI-ethiek beoordelaar voor overheidsbesluitvorming.\nJe geeft je beoordeling ALTIJD en UITSLUITEND als geldig JSON object, zonder extra tekst of markdown."
            }]
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": fairness_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json",
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            
            resp_data = response.json()
            raw_text = resp_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
            
            if not raw_text:
                raise ValueError("No text in response")
                
            return {"text": raw_text, "wmoResult": wmo_result, "applicant": applicant}
            
        except Exception as e:
            # If fairness check fails, default to high risk to be safe
            error_result = {
                "riskLevel": "high",
                "riskScore": 10,
                "biasIndicators": [],
                "fairnessIssues": [f"Fairness check kon niet worden uitgevoerd: {str(e)}"],
                "missingInformation": [],
                "recommendHumanReview": True,
                "reviewReason": "Technische fout in fairness check — automatisch doorgestuurd naar menselijke review",
                "overallAssessment": "Onbekend"
            }
            return {
                "text": json.dumps(error_result),
                "wmoResult": wmo_result,
                "applicant": applicant
            }

@app.post("/parse-fairness-response")
def parse_fairness_response(data: dict):
    text = data.get("text", "")
    wmo_result = data.get("wmoResult")
    applicant = data.get("applicant")
    
    # Remove markdown code blocks if the AI included them
    cleaned = re.sub(r"```json|```", "", text).strip()

    try:
        fairness_result = json.loads(cleaned)
    except Exception:
        # Parsing failed — treat as high risk
        fairness_result = {
            "riskLevel": "high",
            "riskScore": 10,
            "biasIndicators": [],
            "fairnessIssues": ["Fairness output kon niet worden geparsed"],
            "missingInformation": [],
            "recommendHumanReview": True,
            "reviewReason": "Parsing mislukt — automatisch doorgestuurd naar menselijke review",
            "overallAssessment": "Onbekend"
        }

    requires_human_review = (
        fairness_result.get("riskLevel") == "high" or 
        fairness_result.get("recommendHumanReview") is True
    )

    return {
        "applicant": applicant,
        "wmoResult": wmo_result,
        "fairnessResult": fairness_result,
        "requiresHumanReview": requires_human_review
    }
