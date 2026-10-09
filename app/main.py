import streamlit as st

st.set_page_config(page_title="EduForecast-SIS", layout="wide", initial_sidebar_state="expanded")

navigation = st.navigation([
    st.Page("home.py", title="Главная", default=True),
    st.Page("pages/01_Students.py", title="Студенты", url_path="Students"),
    st.Page("pages/02_Analytics.py", title="Аналитика", url_path="Analytics"),
    st.Page("pages/03_AI_Advisor.py", title="ИИ-советник", url_path="AI_Advisor"),
    st.Page("pages/04_Research.py", title="Научная продуктивность", url_path="Research"),
    st.Page("pages/05_Finance.py", title="Финансы (бета)", url_path="Finance"),
])
navigation.run()
