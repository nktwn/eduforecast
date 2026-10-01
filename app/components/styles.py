GLASS_CSS = """
<style>
.stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    background: #f5f6f8 !important;
}

.main, .block-container, section.main > div,
div[data-testid="stMainBlockContainer"],
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlock"],
div.element-container,
div[data-testid="stHorizontalBlock"] {
    background: transparent !important;
}

header[data-testid="stHeader"] {
    background: #f5f6f8 !important;
    border-bottom: 1px solid #e3e6eb !important;
}
[data-testid="stToolbar"] { background: transparent !important; }

[data-testid="stSidebar"] {
    background: #101c34 !important;
    border-right: 1px solid #1c2c4d !important;
}
[data-testid="stSidebar"] > div { background: transparent !important; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #16233f !important;
    border: 1px solid #2a3b5e !important;
    border-radius: 6px !important;
    color: #f1f5f9 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] svg { fill: #7d8db0 !important; }
[data-testid="stSidebar"] label {
    color: #7d8db0 !important;
    font-weight: 600 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
[data-testid="stSidebar"] option { color: #0b1d3a !important; }

.glass-card {
    background: #ffffff;
    border-radius: 8px;
    border: 1px solid #e3e6eb;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    padding: 20px 22px;
    margin-bottom: 16px;
}

.metric-card {
    background: #ffffff;
    border-radius: 8px;
    border: 1px solid #e3e6eb;
    border-left: 3px solid #2563eb;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    padding: 18px 20px;
}
.metric-card.accent-red   { border-left-color: #dc2626; }
.metric-card.accent-green { border-left-color: #059669; }
.metric-card.accent-amber { border-left-color: #d97706; }

.metric-value {
    font-size: 2rem; font-weight: 700;
    color: #0f172a; line-height: 1.15;
    letter-spacing: -0.01em;
}
.metric-label {
    font-size: 0.72rem; color: #6b7280;
    margin-top: 4px; font-weight: 600;
}
.metric-delta { font-size: 0.8rem; color: #9ca3af; margin-top: 4px; }

.glass-alert {
    background: #ffffff;
    border-radius: 6px;
    padding: 10px 14px; margin-bottom: 6px;
    display: flex; align-items: center; gap: 10px;
    font-size: 0.85rem; color: #0f172a;
    border: 1px solid #e3e6eb;
    border-left: 3px solid #9ca3af;
}

.section-title {
    font-size: 0.92rem; font-weight: 700;
    color: #0f172a;
    margin: 24px 0 12px 0; padding-bottom: 8px;
    border-bottom: 1px solid #e3e6eb;
}

.stButton > button {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    color: #1f2937 !important;
    border-radius: 6px !important;
    font-weight: 500 !important; font-size: 0.85rem !important;
    padding: 7px 14px !important;
    transition: background 0.12s ease, border-color 0.12s ease !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: #f9fafb !important;
    border-color: #9ca3af !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background: #2563eb !important;
    color: #ffffff !important; border-color: #2563eb !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1d4ed8 !important;
    border-color: #1d4ed8 !important;
}

.stSelectbox > div > div {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
}
.stSelectbox label { color: #374151 !important; font-weight: 600 !important; font-size: 0.8rem !important; }

.stMultiSelect > div > div {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
}
.stMultiSelect label { color: #374151 !important; font-weight: 600 !important; }
[data-baseweb="tag"] {
    background: #eff6ff !important;
    border: 1px solid #bfdbfe !important;
    color: #1e40af !important; border-radius: 4px !important;
}

.stTextInput > div > div > input {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
    color: #0f172a !important; font-size: 0.9rem !important;
}
.stTextInput > div > div > input::placeholder { color: #9ca3af !important; }
.stTextInput > div > div > input:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
}
.stTextInput label { color: #374151 !important; font-weight: 600 !important; }

.stDownloadButton > button {
    background: #ffffff !important;
    border: 1px solid #a7f3d0 !important;
    color: #047857 !important; border-radius: 6px !important; font-weight: 500 !important;
}
.stDownloadButton > button:hover {
    background: #ecfdf5 !important;
    border-color: #6ee7b7 !important;
}

[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid #e3e6eb !important;
    border-radius: 8px !important;
}
[data-testid="stExpander"] summary { color: #374151 !important; font-weight: 600 !important; }

[data-testid="stMetric"] {
    background: #ffffff !important;
    border-radius: 8px !important; padding: 12px 16px !important;
    border: 1px solid #e3e6eb !important;
}
[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #6b7280 !important; font-weight: 600 !important; font-size: 0.75rem !important; }
[data-testid="stMetricDelta"]  { color: #2563eb !important; }

[data-testid="stDataFrame"] {
    background: #ffffff !important;
    border-radius: 8px !important;
    border: 1px solid #e3e6eb !important;
    overflow: hidden;
}

[data-testid="stAlert"] {
    background: #ffffff !important;
    border-radius: 6px !important;
    border: 1px solid #e3e6eb !important;
}

div[data-testid="stPlotlyChart"] { border-radius: 6px !important; overflow: hidden; }

h1, h2 { color: #0f172a !important; font-weight: 700 !important; letter-spacing: -0.01em !important; }
h3, h4 { color: #0f172a !important; font-weight: 600 !important; }
h5, h6 { color: #1f2937 !important; font-weight: 600 !important; }
.stMarkdown p { color: #4b5563; }

[data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #e3e6eb !important;
    gap: 4px !important;
}
[data-baseweb="tab"] { color: #6b7280 !important; font-weight: 500 !important; }
[aria-selected="true"][data-baseweb="tab"] {
    color: #2563eb !important; font-weight: 600 !important;
}

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #f1f3f5; }
::-webkit-scrollbar-thumb { background: #c9cdd4; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
</style>
"""


def sidebar_logo(selected_code, faculty_map):
    import streamlit as st
    with st.sidebar:
        st.markdown("""
        <div style="padding:18px 0 16px 0; border-bottom:1px solid #1c2c4d; margin-bottom:14px;">
            <div style="font-size:1.05rem; font-weight:700; color:#f1f5f9;">EduForecast-SIS</div>
            <div style="font-size:0.68rem; color:#7d8db0; font-weight:500; margin-top:2px;">
                Astana IT University
            </div>
        </div>
        """, unsafe_allow_html=True)

        code = st.selectbox(
            "Факультет",
            options=list(faculty_map.keys()),
            format_func=lambda x: f"{x} — {faculty_map[x]}",
            index=list(faculty_map.keys()).index(selected_code)
                  if selected_code in faculty_map else 0,
            key="selected_faculty",
        )

        st.markdown("""
        <div style="margin-top:22px; padding-top:14px;
                    border-top:1px solid #1c2c4d;
                    font-size:0.68rem; color:#5b6b8c; line-height:1.9;">
            Данные: набор OULAD<br>
            Модель: Случайный лес + SHAP<br>
            ИИ: Llama 3.3 70B (Groq)
        </div>
        """, unsafe_allow_html=True)

    return code
