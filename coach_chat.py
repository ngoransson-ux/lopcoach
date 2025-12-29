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
            st.markdown("---")
    if st.button("🚀 Vad ska jag köra nästa pass?"):
        # Detta simulerar att du skriver frågan i chatten
        st.session_state.messages.append({"role": "user", "content": "Baserat på min data och mitt mål, vad föreslår du att jag kör för nästa pass? Ge mig ett specifikt pass med distans, tempo och förklaring."})
        st.rerun()

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
            
            # Beräkna veckor kvar för att ge AI:n tidsperspektiv
            tavlingsdatum = date(2026, 5, 23)
            veckor_kvar = (tavlingsdatum - idag).days // 7

            # HÄR ÄR DEN SAMMANSLAGNA INSTRUKTIONEN (Allt i ett)
            system_instruction = (
                f"Idag är det {idag}. Du är en elit-löpcoach. Din adept tränar för att springa "
                f"en halvmaraton under 1:30:00 (4:15 min/km tempo) den 23 maj 2026.\n"
                f"Det är just nu {veckor_kvar} veckor kvar till tävlingen.\n\n"
                
                f"DATA TILLGÄNGLIG FÖR DIG:\n"
                f"1. Senaste passet (inkl. detaljer & privata noter): {running_data}\n"
                f"2. Historik (6 månader bakåt): {history_data}\n\n"
                
                "DINA INSTRUKTIONER:\n"
                "- Var konversationsinriktad och kom ihåg tidigare dialoger.\n"
                "- Läs alltid de privata noteringarna för att se hur kroppen känns (skador/trötthet).\n"
                "- Tjata inte om statistik i varje svar, men använd den när det är relevant.\n\n"
                
                "NÄR ANVÄNDAREN FRÅGAR OM NÄSTA PASS:\n"
                "Ge ett specifikt förslag baserat på modern träningslära (t.ex. 80/20-regeln):\n"
                "1. TYP: Intervaller, Tempolopp, Långpass eller Återhämtning.\n"
                "2. DISTANS/TID: Exakt antal km eller minuter.\n"
                "3. INTENSITET: Måltempo och puls-zon.\n"
                "4. VARFÖR: Förklara hur passet bygger formen mot 1:30-målet.\n\n"
                "Svara alltid på peppande svenska."
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
