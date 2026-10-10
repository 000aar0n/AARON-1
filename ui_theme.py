"""AARON-1 interface: restrained, typography-first design system.

Visual customization only; all controls remain native accessible Streamlit widgets.
"""
from __future__ import annotations

import html
import streamlit as st

STYLE = r"""
<style>
:root {
  --a-bg:#0d0f11;
  --a-panel:#141719;
  --a-panel-2:#191c1f;
  --a-border:#303439;
  --a-text:#eeeff0;
  --a-muted:#9ba1a5;
  --a-accent:#e5e7e9;
}
html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"] {
  background:var(--a-bg)!important;color:var(--a-text)!important;
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stMainBlockContainer"] {
  max-width:1320px!important;
  padding:1.8rem clamp(1.2rem,4vw,4.2rem) 4rem!important;
}
[data-testid="stSidebar"]{
  background:#121416!important;
  border-right:1px solid var(--a-border)!important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{font-size:13px}
[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"]{
  border-radius:3px!important;
  padding:9px 12px!important;
  font-size:13px!important;
}
[data-testid="stSidebarNav"] a[aria-current="page"]{
  background:#24282b!important;color:#fff!important;
}
[data-testid="stSegmentedControl"] button,
[data-testid="stSegmentedControl"] [role="radiogroup"] label,
[data-testid="stSegmentedControl"] [role="radio"]{
  border-radius:3px!important;
}
[data-testid="stPill"],[data-testid="stPillContainer"] button{
  border-radius:3px!important;
}
[data-testid="stSidebar"] [role="radiogroup"]{gap:5px!important}
[data-testid="stSidebar"] [role="radiogroup"] label{
  border-radius:3px!important;
  padding:8px 9px!important;
  border:1px solid transparent!important;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){
  background:#222629!important;border-color:#3e4449!important;
}
#MainMenu,footer{visibility:hidden}
h1,h2,h3,h4{color:var(--a-text)!important;letter-spacing:-.028em!important}
p{line-height:1.6}
[data-testid="stCaptionContainer"] p,.stCaption{color:var(--a-muted)!important}
div[data-testid="stVerticalBlock"]{gap:.65rem}
[data-testid="stVerticalBlockBorderWrapper"] > div{
  border:1px solid var(--a-border)!important;
  border-radius:4px!important;
  background:var(--a-panel)!important;
}
button,button[kind],button[data-baseweb],input,textarea,select{
  font-family:inherit!important;
}
div[data-testid="stButton"]>button,
div[data-testid="stFormSubmitButton"]>button,
div[data-testid="stDownloadButton"]>button,
[data-testid="stPopover"] button{
  background:#202427!important;color:var(--a-text)!important;
  border:1px solid #454a4e!important;
  border-radius:3px!important;box-shadow:none!important;
  min-height:37px;
  font-weight:560!important;
  transition:background .1s ease,border-color .1s ease!important;
}
div[data-testid="stButton"]>button:hover,
div[data-testid="stFormSubmitButton"]>button:hover,
div[data-testid="stDownloadButton"]>button:hover{
  background:#33383c!important;border-color:#7d8489!important;
}
div[data-testid="stButton"]>button[kind="primary"],
div[data-testid="stFormSubmitButton"]>button[kind="primary"]{
  background:#e5e7e9!important;border-color:#e5e7e9!important;
  color:#141719!important;font-weight:690!important;
}
div[data-testid="stButton"]>button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"]>button[kind="primary"]:hover{
  background:#fff!important;
}
button:focus-visible,input:focus-visible,textarea:focus-visible{
  outline:2px solid #aeb5ba!important;outline-offset:2px!important;
}
[data-testid="stTextInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stNumberInput"] input,
[data-baseweb="input"]>div,
[data-baseweb="select"]>div {
  border-radius:3px!important;
  background:#111417!important;
  border-color:#40464b!important;
  color:var(--a-text)!important;
  box-shadow:none!important;
}
[data-baseweb="tag"],[data-baseweb="tag"]>span,
[data-baseweb="segmented-control"],[data-baseweb="segmented-control"] button{
  border-radius:3px!important;
}
[data-testid="stFileUploader"] section{
  border-radius:3px!important;
  border-color:var(--a-border)!important;
  background:#15181a!important;
}
[data-testid="stExpander"]{
  background:transparent!important;
  border:1px solid var(--a-border)!important;
  border-radius:3px!important;
}
[data-testid="stExpander"] summary:hover{background:#1b1f21!important}
[data-testid="stAlert"]{border-radius:3px!important}
[data-testid="stDialog"] [role="dialog"],
[role="dialog"],[data-testid="stModal"]{
  border-radius:4px!important;
}
[data-testid="stChatMessage"]{
  background:transparent!important;border:0!important;
  border-bottom:1px solid #292e31!important;
  border-radius:0!important;padding:14px 5px!important;
}
[data-testid="stChatInput"]{
  border:1px solid #50565a!important;border-radius:4px!important;
  background:#1b1e20!important;
}
[data-testid="stChatInput"] textarea{border-radius:3px!important}
[data-testid="stChatInput"] button{border-radius:3px!important}
[data-testid="stSelectSlider"] [role="slider"]{border-radius:3px!important}
[data-testid="stSlider"] [role="slider"]{border-radius:3px!important}
[data-testid="stMetric"],[data-testid="stDataFrame"]{border-radius:3px!important}
hr{border-color:var(--a-border)!important}

/* Unadorned identity and section hierarchy. */
.brandbar{
  display:flex;align-items:center;gap:14px;padding:3px 0 24px;
  border-bottom:1px solid var(--a-border);margin-bottom:32px;
}
.brandmark{
  width:34px;height:34px;display:grid;place-items:center;
  border:1px solid #727a7f;background:transparent;border-radius:3px;
  font-size:13px;font-weight:720;color:var(--a-text);
  letter-spacing:-.06em;
}
.brandname{font-size:16px;letter-spacing:-.03em;font-weight:680;color:#f0f1f2}
.brandcaption{color:var(--a-muted);font-size:10px;letter-spacing:.13em;margin-top:2px}
.brand-right{margin-left:auto;color:#a1a7aa;font-size:11px;letter-spacing:.07em}
.page-kicker{font-size:11px;font-weight:670;letter-spacing:.13em;color:#9ea5aa;margin:0 0 10px}
.page-title{font-size:clamp(27px,3.8vw,38px);font-weight:690;
  line-height:1.17;color:#f1f2f3;letter-spacing:-.04em;margin:0 0 9px}
.page-subtitle{font-size:14px;color:#adb3b7;line-height:1.6;margin:0 0 26px;max-width:740px}
.muted-line{color:#92999e;font-size:11px}
.metricbox{padding:16px 18px;min-height:92px;border:1px solid var(--a-border);
  border-radius:3px;background:#15181a;margin:0 0 12px}
.metric-label{font-size:11px;color:#a6acaf;font-weight:620;
  text-transform:uppercase;letter-spacing:.08em}
.metric-value{margin-top:7px;color:#eff1f2;font-size:26px;font-weight:680;
  letter-spacing:-.04em;line-height:1.25;overflow-wrap:anywhere}
.metric-note{font-size:11px;color:#949da2;margin-top:5px}

/* Calendar keeps functional event colors, but loses decorative chrome. */
.fc{--fc-border-color:#34393e;--fc-page-bg-color:#111416;
  --fc-neutral-bg-color:#191d20;--fc-today-bg-color:#c0c7cc0b;
  color:#e8eaed!important;font-family:inherit!important}
.fc .fc-button-primary{border-radius:3px!important;background:#252a2d!important;
  border-color:#51585d!important;color:#d9dddf!important;box-shadow:none!important}
.fc .fc-button-primary:not(:disabled).fc-button-active{
  background:#e7e9e9!important;color:#181a1c!important;border-color:#e7e9e9!important}
.fc .fc-view-harness,.fc .fc-daygrid-event,.fc .fc-timegrid-event,
.fc .fc-popover{border-radius:3px!important}
.fc .fc-toolbar-title{font-size:19px!important;font-weight:650!important;letter-spacing:-.035em!important}
.fc .fc-col-header-cell{background:#1b1f22!important}
.fc .fc-daygrid-day.fc-day-today{background:#d2d8dc0a!important}
.fc .fc-timegrid-slot-label-cushion{color:#aab1b5!important}
.fc .fc-daygrid-event:hover,.fc .fc-timegrid-event:hover{filter:brightness(1.12)!important}

@media(max-width:800px){
 [data-testid="stMainBlockContainer"]{padding:1.1rem 1.1rem 3rem!important}
 .brand-right{display:none}
 .brandbar{margin-bottom:20px}
 .page-title{font-size:28px}
 .fc .fc-toolbar-title{font-size:15px!important}
}
</style>
"""

def install_theme():
    st.markdown(STYLE, unsafe_allow_html=True)

def header():
    st.markdown(
        '<div class="brandbar">'
        '<div class="brandmark">A1</div>'
        '<div><div class="brandname">AARON—1</div>'
        '<div class="brandcaption">PERSONAL WORKSPACE</div></div>'
        '<div class="brand-right">CALENDAR / ASSISTANT / MODEL</div>'
        '</div>', unsafe_allow_html=True
    )

def page_heading(kicker, title, description):
    st.markdown(
        '<div class="page-kicker">' + html.escape(kicker.upper()) + '</div>'
        '<div class="page-title">' + html.escape(title) + '</div>'
        '<div class="page-subtitle">' + html.escape(description) + '</div>',
        unsafe_allow_html=True
    )

def metric(label, value, note=""):
    st.markdown(
        '<div class="metricbox">'
        '<div class="metric-label">' + html.escape(str(label)) + '</div>'
        '<div class="metric-value">' + html.escape(str(value)) + '</div>'
        + ('<div class="metric-note">' + html.escape(str(note)) + '</div>' if note else '')
        + '</div>',
        unsafe_allow_html=True
    )
