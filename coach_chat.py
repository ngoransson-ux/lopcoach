import streamlit as st
import requests
from google import genai

# --- KONFIGURATION ---
STRAVA_CLIENT_ID = "177985"
STRAVA_CLIENT_SECRET = "2b3cf9adfae953c2716e0e10ef288d0eb26e4c9b"
GEMINI_API_KEY = "AIzaSyAPFas1aeurXsPAqz6nI8mhObta316fvY4"
REFRESH_TOKEN = "3708e8d1bcce1c05cfd864bdc4afd47bf166aed7"

client = genai.Client(api_key=GEMINI_API_KEY)

# --- FUNKTIONER ---
def get_strava_data():
    """Hämtar senaste rundan för att ge AI:n kontext"""
    try:
        # Hämta ny access token
        u = "https://www.strava.com/oauth/token"
        p = {'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 
             'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
        access_token = requests.post(u, data=p).json()['access_token']
        
        # Hämta senaste runda
        url = "https://www.strava.com/api/v3/athlete/activities"
        headers = {'Authorization': f'Bearer {access_token}'}
        activity = requests.get(url, headers=headers, params={'per_page': 1}).json()[0]
        
        dist = activity.get('distance') / 1000
        tid = activity.get('moving_time') / 60
        namn = activity.get('name')
        return f"Senaste passet: '{namn}', Distans: {dist:.2f}km, Tid: {tid:.0f}min."
    except:
        return "Kunde inte hämta Strava-data just nu."

# --- STRUKTUR FÖR CHATTEN ---
st.set_page_config(page_title="Löpcoach AI", page_icon="🏃‍♂️")
st.title("🏃‍♂️ Din Personliga Löpcoach")

# Initiera chat-historik om den inte finns
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hej! Jag är din löpcoach. Hur går det med träningen?"}
    ]

# Visa alla meddelanden från historiken
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Användarens input
if prompt := st.chat_input("Skriv till coachen..."):
    # Lägg till användarens meddelande i historiken
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generera svar från AI:n
    with st.chat_message("assistant"):
        with st.spinner("Tänker..."):
            # Hämta dagsfärsk Strava-info för att AI:n alltid ska veta senaste status
            strava_context = get_strava_data()
            
            # Skapa den fullständiga instruktionen till AI:n
            full_prompt = (
                f"Du är en peppande löpcoach. Här är användarens senaste Strava-data: {strava_context}\n"
                f"Användaren säger: {prompt}\n"
                "Svara kort, professionellt och på svenska."
            )
            
            try:
                # Vi använder Gemini 2.5 Flash som vi vet fungerar för dig
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=full_prompt
                )
                ai_response = response.text
                st.markdown(ai_response)
                # Spara AI:ns svar i historiken
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
            except Exception as e:
                st.error(f"AI-fel: {e}")