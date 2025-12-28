import streamlit as st
import requests
from google import genai
import time

# --- 1. KONFIGURATION (Hämtas från Streamlit Secrets) ---
# Se till att du har lagt in dessa under Advanced Settings -> Secrets i Streamlit Cloud
STRAVA_CLIENT_ID = "177985"
STRAVA_CLIENT_SECRET = "2b3cf9adfae953c2716e0e10ef288d0eb26e4c9b"
GEMINI_API_KEY = "AIzaSyAPFas1aeurXsPAqz6nI8mhObta316fvY4"
REFRESH_TOKEN = "3708e8d1bcce1c05cfd864bdc4afd47bf166aed7"

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. FUNKTION FÖR ATT HÄMTA DETALJERAD DATA ---
def get_detailed_strava_context():
    try:
        # Hämta ny access token för att få lov att läsa
        u = "https://www.strava.com/oauth/token"
        p = {
            'client_id': STRAVA_CLIENT_ID, 
            'client_secret': STRAVA_CLIENT_SECRET, 
            'refresh_token': REFRESH_TOKEN, 
            'grant_type': 'refresh_token'
        }
        token_response = requests.post(u, data=p).json()
        access_token = token_response['access_token']
        
        # Hämta ID för det senaste passet
        list_url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        latest_act = requests.get(list_url, headers=headers, params={'per_page': 1}).json()[0]
        activity_id = latest_act['id']

        # Hämta DETALJERAD data för just det passet (puls, splits, kadens etc.)
        detail_url = f"https://www.strava.com/api/v3/activities/{activity_id}"
        data = requests.get(detail_url, headers=headers).json()
        
        # Formatera datan snyggt för AI:n
        dist = data.get('distance', 0) / 1000
        tid = data.get('moving_time', 0) / 60
        puls_avg = data.get('average_heartrate', 'N/A')
        puls_max = data.get('max_heartrate', 'N/A')
        kadens = data.get('average_cadence', 'N/A')
        stigning = data.get('total_elevation_gain', 0)
        
        # Kilometertider
        splits = ""
        if 'splits_metric' in data:
            for s in data['splits_metric']:
                splits += f"Km {s['split']}: {round(s['moving_time']/60, 2)} min/km. "

        context = (
            f"Passets namn: {data.get('name')}\n"
            f"Distans: {dist:.2f} km\n"
            f"Total tid: {tid:.1f} min\n"
            f"Snittpuls: {puls_avg} bpm, Maxpuls: {puls_max} bpm\n"
            f"Kadens (snitt): {kadens}\n"
            f"Höjdmetrar: {stigning} m\n"
            f"Kilometertider: {splits}"
        )
        return context
    except Exception as e:
        return f"Kunde inte hämta detaljerad info från Strava: {e}"

# --- HÄR KLISTRAR DU IN DEN NYA FUNKTIONEN ---
def get_six_months_history():
    try:
        u = "https://www.strava.com/oauth/token"
        p = {'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 
             'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
        access_token = requests.post(u, data=p).json()['access_token']
        
        # Timestamp för 6 månader sedan
        six_months_ago = int(time.time()) - (180 * 24 * 60 * 60)
        
        url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'after': six_months_ago, 'per_page': 200}
        activities = requests.get(url, headers=headers, params=params).json()
        
        history_summary = ""
        for act in activities:
            if act['type'] == 'Run':
                date = act['start_date_local'][:10]
                dist = act['distance'] / 1000
                history_summary += f"- {date}: {dist:.1f}km, Puls: {act.get('average_heartrate', 'N/A')}\n"
        
        return history_summary
    except Exception as e:
        return f"Kunde inte hämta historik: {e}"

# --- 3. CHATT-GRÄNSSNITT ---
st.set_page_config(page_title="AI Löpcoach Pro", page_icon="🏃‍♂️")
st.title("🏃‍♂️ Din Personliga Löpcoach Pro")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hej! Jag har nu tillgång till din detaljerade puls- och tempodata. Fråga mig vad du vill om ditt senaste pass!"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Skriv till coachen..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyserar din löpdata..."):
            # Hämta den djupa datan från Strava
            running_data = get_detailed_strava_context()
            
            system_instruction = (
                "Du är en professionell löpcoach. Här är detaljerad data från användarens senaste pass:\n"
                f"{running_data}\n\n"
                "Använd denna data för att ge specifika, datadrivna tips. Om pulsen är hög för tempot, nämn det. "
                "Om kilometertiderna varierar mycket, ge tips om jämnare fart. Var peppande och svara på svenska."
            )
            
            try:
                # Vi använder 2.5-flash som vi vet att din nyckel har tillgång till
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"{system_instruction}\n\nAnvändarens fråga: {prompt}"
                )
                ai_response = response.text
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
            except Exception as e:
                st.error(f"AI-fel: {e}")
