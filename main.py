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
    #converting json to a beauty text
    parts = []
    for topic in faq_json["topics"]:
        parts.append(f"=== ТЕМА {topic['id']}: {topic['title']} ===\n")
        for q_a in topic['questions']:
            parts.append(f"В: {q_a['q']}\nО: {q_a['a']}\n")
        parts.append("")
    return "\n".join(parts)

def load_data():
    with open ('faq.json') as f:
        faq_json = json.load(f) # not read - read for stirng
        faq_content = format_json(faq_json) 
    with open('prompt.md') as f:
        prompt_content = f.read()

    return faq_content, prompt_content

def save_unknown_questions(user):

    today = date.today()
    with open("unknown_data.txt", 'a') as f:
        f.write(f'{today} - {user}\n')

def main():

    logging.info("Initializing a client...")
    client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

    logging.info("Updating data...")
    faq_content, system_prompt = load_data()

    logging.info("Starting an app...")
    intro = ask_question('Представься кратко - кто ты и чем можешь помочь', client, faq_content, system_prompt)
    print(f"{intro}\n\n")

    while True:
        user = input("Ваш вопрос (0 для выхода)\n> ")
        if user.strip() == '0': break
        answer = ask_question(user, client, faq_content, system_prompt)
        print(f"\n{answer}\n\n")
        st.write(answer)
        
        if "К сожалению, в моей базе данных нет" in answer:
            save_unknown_questions(user)  # ← log it

    print("Bye!")





if __name__ == '__main__':
    
    main()