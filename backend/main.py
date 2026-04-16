from fastapi import FastAPI

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
    