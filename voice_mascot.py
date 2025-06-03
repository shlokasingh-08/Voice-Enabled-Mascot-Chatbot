import streamlit as st
import speech_recognition as sr
import pyttsx3
from openai import OpenAI
import os
from PIL import Image
import time
from dotenv import load_dotenv
import threading
import queue
import wave
import pyaudio
import numpy as np

# Load environment variables
load_dotenv()

# Initialize OpenAI client with API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Please check your .env file.")
    st.stop()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Set page config
st.set_page_config(
    page_title="AI Mascot",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-title {
        text-align: center;
        font-size: 3rem;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        margin-top: 10px;
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .clear-button {
        background-color: #f44336 !important;
    }
    .clear-button:hover {
        background-color: #da190b !important;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e3f2fd;
    }
    .mascot-message {
        background-color: #f5f5f5;
    }
    .status-message {
        color: #666;
        font-style: italic;
    }
    .button-container {
        display: flex;
        gap: 10px;
        margin-top: 10px;
    }
    .listening-status {
        color: #4CAF50;
        font-weight: bold;
        text-align: center;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

class VoiceMascot:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.is_speaking = False
        self._lock = threading.Lock()
        
        # Adjust recognition settings
        self.recognizer.energy_threshold = 3000  # Increase sensitivity
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8  # Shorter pause threshold
    
    def start_listening(self):
        with sr.Microphone() as source:
            # Adjust for ambient noise with longer duration
            st.markdown('<div class="listening-status">Adjusting for ambient noise... Please wait.</div>', unsafe_allow_html=True)
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            
            st.markdown('<div class="listening-status">Listening... Speak now!</div>', unsafe_allow_html=True)
            try:
                # Increase timeout and phrase_time_limit
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                return text
            except sr.WaitTimeoutError:
                st.warning("No speech detected. Please try again and speak clearly.")
                return None
            except sr.UnknownValueError:
                st.error("Could not understand audio. Please speak more clearly.")
                return None
            except sr.RequestError as e:
                st.error(f"Could not request results; {e}")
                return None
            except Exception as e:
                st.error(f"An error occurred: {e}")
                return None
    
    def speak(self, text):
        try:
            with self._lock:
                if self.is_speaking:
                    return False
                
                self.is_speaking = True
                
                # Create a new engine instance for this speech
                engine = pyttsx3.init()
                engine.setProperty('rate', 150)
                engine.setProperty('volume', 1.0)
                
                # Get available voices and set a female voice if available
                voices = engine.getProperty('voices')
                for voice in voices:
                    if "female" in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
                
                # Speak the text
                engine.say(text)
                engine.runAndWait()
                
                # Clean up
                try:
                    engine.stop()
                except:
                    pass
                
                return True
                
        except Exception as e:
            st.error(f"Error in speech output: {e}")
            return False
            
        finally:
            self.is_speaking = False

def load_mascot_image():
    try:
        image = Image.open("1.png")
        return image
    except:
        return Image.new('RGB', (300, 300), color='#f0f2f6')

def get_ai_response(user_input):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a friendly Rajasthan Royals cricket mascot. Keep responses short, engaging, and cricket-themed. Include occasional cricket jokes and facts."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=100
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error getting AI response: {e}")
        return "I'm having trouble thinking right now. Would you like to hear a cricket joke instead?"

def initialize_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'mascot_image' not in st.session_state:
        st.session_state.mascot_image = load_mascot_image()
    if 'voice_mascot' not in st.session_state:
        st.session_state.voice_mascot = VoiceMascot()
    if 'last_question' not in st.session_state:
        st.session_state.last_question = None
    if 'current_response' not in st.session_state:
        st.session_state.current_response = None
    if 'should_speak' not in st.session_state:
        st.session_state.should_speak = False
    if 'last_spoken_message' not in st.session_state:
        st.session_state.last_spoken_message = None
    if 'button_counter' not in st.session_state:
        st.session_state.button_counter = 0

def handle_voice_chat():
    try:
        # Get voice input
        user_input = st.session_state.voice_mascot.start_listening()
        
        if user_input:
            # Store last question to prevent duplicates
            st.session_state.last_question = user_input
            
            # Add user message to chat
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # Get AI response
            response = get_ai_response(user_input)
            st.session_state.current_response = response
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Try to speak the response immediately
            try:
                st.session_state.voice_mascot.speak(response)
            except Exception as e:
                st.error(f"Error generating speech: {e}")
            
            # Increment button counter
            st.session_state.button_counter += 1
            
            # Force a UI update
            st.rerun()
            
    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.rerun()

def main():
    # Initialize session state first
    initialize_session_state()
    
    # Centered title with custom styling
    st.markdown('<h1 class="main-title">🏏 Voice-Enabled Rajasthan Royals Mascot 🎙️</h1>', unsafe_allow_html=True)
    
    # Create two columns with adjusted widths
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Display mascot image
        st.image(st.session_state.mascot_image, caption="Your Rajasthan Royals Mascot", use_container_width=True)
        
        # Button container for voice chat and clear chat
        st.markdown('<div class="button-container">', unsafe_allow_html=True)
        
        # Voice input button with unique key based on counter
        if st.button("🎤 Start Voice Chat", key=f"voice_chat_{st.session_state.button_counter}"):
            handle_voice_chat()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", key="clear_chat"):
            st.session_state.messages = []
            st.session_state.last_question = None
            st.session_state.current_response = None
            st.session_state.button_counter = 0
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Add voice chat tips
        st.markdown("""
            <div class="status-message">
                <p>💡 Tips for better voice recognition:</p>
                <ul>
                    <li>Speak clearly and at a normal pace</li>
                    <li>Ensure your microphone is working</li>
                    <li>Reduce background noise</li>
                    <li>Wait for "Listening..." before speaking</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Display chat messages
        for message in st.session_state.messages:
            with st.container():
                if message["role"] == "user":
                    st.markdown(f"""
                        <div class="chat-message user-message">
                            <b>You:</b> {message["content"]}
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="chat-message mascot-message">
                            <b>Mascot:</b> {message["content"]}
                        </div>
                    """, unsafe_allow_html=True)
        
        # Add instructions
        st.markdown("""
            <div class="status-message">
                <p>👆 Click the "Start Voice Chat" button to begin speaking with the mascot!</p>
                <p>🎤 Speak clearly and wait for the mascot's response.</p>
                <p>💬 The conversation will appear in the chat window.</p>
            </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()