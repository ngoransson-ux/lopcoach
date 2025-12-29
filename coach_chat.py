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
        # 1. Access Token
        u = "https://www.strava.com/oauth/token"
        p = {'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 
             'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
        access_token = requests.post(u, data=p).json()['access_token']
        
        # 2. Hämta ID för senaste passet
        list_url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        latest_act = requests.get(list_url, headers=headers, params={'per_page': 1}).json()[0]
        activity_id = latest_act['id']

        # 3. Hämta DETALJERAD data (här finns Private Note)
        detail_url = f"https://www.strava.com/api/v3/activities/{activity_id}"
        data = requests.get(detail_url, headers=headers).json()
        
        # 4. Hämta ut data inklusive din privata anteckning
        dist = data.get('distance', 0) / 1000
        tid = data.get('moving_time', 0) / 60
        puls = data.get('average_heartrate', 'N/A')
        # HÄR HÄMTAR VI DIN PRIVATA ANTECKNING
        privat_notering = data.get('private_note', 'Ingen anteckning gjord.')
        
        context = (
            f"Pass: '{data.get('name')}'\n"
            f"Distans: {dist:.2f}km, Tid: {tid:.1f}min, Puls: {puls}\n"
            f"Användarens privata anteckning för detta pass: {privat_notering}"
        )
        return context
    except Exception as e:
        return f"Kunde inte hämta data: {e}"

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
                # Räkna ut tempo (min/km)
                tempo = (act['moving_time'] / 60) / dist if dist > 0 else 0
                history_summary += f"- {date}: {dist:.2f}km, Tempo: {tempo:.2f} min/km, Puls: {act.get('average_heartrate', 'N/A')}\n"
        return history_summary
    except Exception as e:
        return "Historik ej tillgänglig."

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
            # Vi hämtar BÅDE senaste passet och historiken i bakgrunden
            latest_run = get_detailed_strava_context()
            history = get_six_months_history()
            
            system_instruction = (
                f"Idag är det {idag}. Du är en personlig löpcoach. Din adept tränar för 1:30 på halvmaran den 23 maj 2026.\n"
                f"Du har tillgång till historik (6 mån): \n{history}\n"
                f"Du har tillgång till senaste passet: \n{latest_run}\n\n"
                "VIKTIGA INSTRUKTIONER:\n"
                "1. Var konversationsinriktad. Prata som en vanlig människa.\n"
                "2. TJATA INTE om senaste passet i varje svar. Nämn det bara om användaren frågar eller om det är relevant för samtalet.\n"
                "3. Använd historiken för att svara på frågor om trender, rekord eller specifika datum.\n"
                "4. Om användaren bara vill snacka löpning, skor eller motivation – gör det utan att rabbla statistik." 
                "VIKTIGT: Läs användarens privata anteckning noga. Det är där användaren skriver "
                "hur kroppen känns, eventuella skador eller tankar. Använd detta för att föra ett "
                "smart och resonerande samtal. Om användaren nämner en skada i anteckningen, "
                "följ upp det i ditt svar!"
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
