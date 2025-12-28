import streamlit as st
import requests
from google import genai
import time
from datetime import date

# --- NYTT: LÖSENORDSSKYDD ---
def check_password():
    """Returnerar True om användaren har skrivit rätt lösenord."""
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        # Visa en ruta där man skriver lösenord
        user_password = st.text_input("Lösenord för löpcoachen:", type="password")
        if st.button("Logga in"):
            # VÄLJ DITT LÖSENORD HÄR (eller lägg det i st.secrets för extra säkerhet)
            if user_password == st.secrets["APP_PASSWORD"]: 
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Fel lösenord!")
        return False
    return True

# Om lösenordet inte är rätt, stoppa resten av appen från att köras
if not check_password():
    st.stop()

# --- 1. KONFIGURATION ---
STRAVA_CLIENT_ID = "177985"
STRAVA_CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
REFRESH_TOKEN = "3708e8d1bcce1c05cfd864bdc4afd47bf166aed7"

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. FUNKTIONER ---

def get_detailed_strava_context():
    try:
        u = "https://www.strava.com/oauth/token"
        p = {'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 
             'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
        token_response = requests.post(u, data=p).json()
        access_token = token_response['access_token']
        
        list_url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        latest_act = requests.get(list_url, headers=headers, params={'per_page': 1}).json()[0]
        activity_id = latest_act['id']

        detail_url = f"https://www.strava.com/api/v3/activities/{activity_id}"
        data = requests.get(detail_url, headers=headers).json()
        
        dist = data.get('distance', 0) / 1000
        tid = data.get('moving_time', 0) / 60
        puls_avg = data.get('average_heartrate', 'N/A')
        puls_max = data.get('max_heartrate', 'N/A')
        kadens = data.get('average_cadence', 'N/A')
        stigning = data.get('total_elevation_gain', 0)
        
        splits = ""
        if 'splits_metric' in data:
            for s in data['splits_metric']:
                splits += f"Km {s['split']}: {round(s['moving_time']/60, 2)} min/km. "

        return (f"Passets namn: {data.get('name')}\nDistans: {dist:.2f} km\nTotal tid: {tid:.1f} min\n"
                f"Snittpuls: {puls_avg} bpm, Maxpuls: {puls_max} bpm\nKadens: {kadens}\nHöjd: {stigning}m\n"
                f"Kilometertider: {splits}")
    except Exception as e:
        return f"Kunde inte hämta detaljerad info: {e}"

def get_six_months_history():
    try:
        u = "https://www.strava.com/oauth/token"
        p = {'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 
             'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
        access_token = requests.post(u, data=p).json()['access_token']
        
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

# --- 3. GRÄNSSNITT ---
st.set_page_config(page_title="AI Löpcoach Pro", page_icon="🏃‍♂️")
st.title("🏃‍♂️ Din Personliga Löpcoach Pro")

# Sidomeny för historik
with st.sidebar:
    st.header("Träningshistorik")
    if st.button("Analysera senaste 6 månaderna"):
        with st.spinner("Analyserar trender..."):
            history = get_six_months_history()
            prompt_history = f"Här är min löphistorik senaste 6 månaderna:\n{history}\nAnalysera min utveckling och trender på svenska."
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_history)
            st.success("### Historisk Analys")
            st.write(response.text)

# Chat-historik
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hej! Jag har koll på dina senaste pass och din historik. Vad vill du veta?"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Hantera chat-input
if prompt := st.chat_input("Skriv till coachen..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Tänker..."):
            idag = date.today()
            running_data = get_detailed_strava_context()
            system_instruction = (
                f"Idag är det {idag}. Du är en expert-coach specialiserad på halvmaraton. "
                "Ditt mål är att hjälpa användaren att springa under 1:30:00 (tempo 4:15 min/km) den 23 maj 2026.\n\n"
                f"Här är data från senaste passet:\n{running_data}\n\n"
                "Din uppgift:\n"
                f"1. Berätta först hur många veckor det är kvar från idag ({idag}) till tävlingen den 23 maj 2026.\n"
                "2. Analysera passet baserat på målet (1:30 på halvmaran).\n"
                "3. Om passet var snabbt: Jämför tempot med tävlingstempot på 4:15.\n"
                "4. Om passet var lugnt: Bedöm om pulsen var tillräckligt låg för att bygga uthållighet.\n"
                "5. Var peppande men professionell och ärlig. Svara på svenska."
            )
            
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"{system_instruction}\n\nFråga: {prompt}"
                )
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"AI-fel: {e}")
