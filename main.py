import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import logging
import os
import json
from datetime import date
import streamlit as st

load_dotenv()


@st.cache_resource
def get_client():
    return genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@st.cache_data
def load_data():
    with open('faq.json') as f:
        faq_json = json.load(f)
        faq_content = format_json(faq_json)
    with open('prompt.md') as f:
        prompt_content = f.read()
    return faq_content, prompt_content

def ask_question(user_input, client, faq_content, system_prompt):
    full_system_instruction = f"{system_prompt}\n\n{'='*60}\n БАЗА ЗНАНИЙ:\n{'='*60}\n\n{faq_content}"
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=full_system_instruction
        ),
        contents=user_input
    )
    return response.text

def format_json(faq_json):
    parts = []
    for topic in faq_json["topics"]:
        parts.append(f"=== ТЕМА {topic['id']}: {topic['title']} ===\n")
        for q_a in topic['questions']:
            parts.append(f"В: {q_a['q']}\nО: {q_a['a']}\n")
        parts.append("")
    return "\n".join(parts)

def save_unknown_questions(user):
    today = date.today()
    with open("unknown_data.txt", 'a') as f:
        f.write(f'{today} - {user}\n')

def main():
    client = get_client()
    faq_content, system_prompt = load_data()

    st.title("🎓 AI-консультант по обучению в Китае")
    st.caption("Актуальная информация о поступлении, грантах и документах")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Привет! Я ваш консультант по Китаю. Чем могу помочь?"}]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.form(key='sample_form', clear_on_submit=True):
        user_query = st.text_input("Ваш вопрос", key='user_question')
        submit_button = st.form_submit_button(label="Спросить")

    if submit_button:
        if not user_query:
            st.warning("Пожалуйста, введите вопрос!")
        else:
            st.session_state.messages.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.spinner('Думаю над ответом...'):
                answer = ask_question(user_query, client, faq_content, system_prompt)

                st.session_state.messages.append({"role": "assistant", "content": answer})
                with st.chat_message("assistant"):
                    st.markdown(answer)

                if "К сожалению, в моей базе данных нет" in answer:
                    save_unknown_questions(user_query)
    
    
    


if __name__ == '__main__':
    
    main()