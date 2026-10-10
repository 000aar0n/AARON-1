"""AARON-1 visual system.

Pure CSS / HTML decoration. Interactive controls stay as real Streamlit
widgets so keyboard accessibility, server state and OAuth are unaffected.
"""
from __future__ import annotations

import html

import streamlit as st


STYLE = r"""
<style>
:root {
  --a-bg:#0b0e14;
  --a-panel:#141923;
  --a-panel-2:#191f2b;
  --a-border:#2a3242;
  --a-text:#f1f2f7;
  --a-muted:#929bac;
  --a-purple:#a79cff;
  --a-teal:#76d6c1;
}
html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"] {
  background:var(--a-bg)!important;
  color:var(--a-text);
}
[data-testid="stHeader"] {background:transparent!important;}
[data-testid="stMainBlockContainer"]{
  max-width:1510px!important;
  padding:1.15rem clamp(1rem,3.5vw,3.4rem) 4rem!important;
}
[data-testid="stSidebar"]{background:#10141d!important;}
[data-testid="stSidebarNav"]{display:none;}
#MainMenu,footer{visibility:hidden;}
h1,h2,h3,h4,p{letter-spacing:-.018em;}
h1,h2,h3{color:var(--a-text)!important;}
[data-testid="stCaptionContainer"] p,.stCaption {
  color:var(--a-muted)!important;
}
div[data-testid="stVerticalBlock"] {gap:.65rem;}
[data-testid="stVerticalBlockBorderWrapper"] > div {
  border-color:var(--a-border)!important;
  border-radius:15px!important;
  background:#141923!important;
}
div[data-testid="stButton"]>button {
  background:#1b2130!important;
  color:#e5e9f7!important;
  border:1px solid #323a4b!important;
  border-radius:10px!important;
  min-height:36px;
  transition:all .14s ease!important;
  box-shadow:none!important;
}
div[data-testid="stButton"]>button:hover {
  background:#282f41!important;
  border-color:#7772ba!important;
  color:#fff!important;
}
div[data-testid="stButton"]>button:focus-visible {
  outline:2px solid var(--a-purple)!important;
  outline-offset:2px!important;
}
div[data-testid="stButton"]>button[kind="primary"],
div[data-testid="stFormSubmitButton"]>button[kind="primary"]{
  background:var(--a-purple)!important;
  color:#0d0b1a!important;
  border-color:var(--a-purple)!important;
  font-weight:750!important;
}
div[data-testid="stFormSubmitButton"]>button{
  border-radius:10px!important;
  border:1px solid #454e65!important;
  background:#262d3e!important;
  color:#f3f4fc!important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
div[data-testid="stTextArea"] textarea {
  background:#10151f!important;
  color:#f1f2f8!important;
  border-color:#353e52!important;
  border-radius:10px!important;
}
[data-testid="stFileUploader"] section {
  background:#111722!important;
  border-color:#424b60!important;
  border-radius:12px!important;
}
[data-testid="stExpander"] {
  background:var(--a-panel)!important;
  border:1px solid var(--a-border)!important;
  border-radius:13px!important;
}
[data-testid="stExpander"] summary:hover{
  background:#1b2230!important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  display:flex;gap:6px;
  background:#151a24!important;
  border:1px solid var(--a-border);
  border-radius:13px;
  padding:5px!important;
  width:fit-content;
  max-width:100%;
  overflow-x:auto;
  margin-bottom:1.5rem;
}
[data-testid="stTabs"] [data-baseweb="tab"]{
  background:transparent!important;
  color:#9da6b7!important;
  border-radius:9px!important;
  padding:9px 19px!important;
  height:auto!important;
  font-weight:650!important;
  border:0!important;
}
[data-testid="stTabs"] [aria-selected="true"]{
  background:#292e41!important;
  color:#fff!important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"],
[data-testid="stTabs"] [data-baseweb="tab-border"]{display:none!important;}
/* Full-title weekly agenda: never truncate a class name. */
[class*="st-key-planner_read_full_"] button {
  width:100%!important;
  height:auto!important;
  min-height:42px!important;
  white-space:normal!important;
  overflow-wrap:anywhere!important;
  word-break:normal!important;
  line-height:1.45!important;
  text-align:left!important;
  justify-content:flex-start!important;
  padding:9px 12px!important;
  font-size:14px!important;
  font-weight:740!important;
}
[class*="st-key-planner_read_full_"] button p {
  white-space:normal!important;
  overflow-wrap:anywhere!important;
  word-break:normal!important;
  line-height:1.45!important;
  text-align:left!important;
}
[class*="st-key-planner_readable_titles_window"] {
  background:#101722!important;
}
[data-testid="stChatMessage"]{
  background:var(--a-panel)!important;
  border:1px solid var(--a-border)!important;
  border-radius:16px!important;
}
[data-testid="stChatInput"]{
  border-radius:14px!important;
  background:#191f2b!important;
}
[data-testid="stAlert"] {border-radius:12px!important;}
hr {border-color:var(--a-border)!important;}

/* Global brand navigation */
.brandbar{
  display:flex;align-items:center;gap:14px;
  padding:11px 0 24px;
  border-bottom:1px solid #252b39;
  margin-bottom:28px;
}
.brandmark{
  height:44px;width:44px;flex:none;
  border:1px solid #5f5a97;
  background:linear-gradient(145deg,#272942,#151925);
  color:#d5d0ff;display:grid;place-items:center;
  border-radius:12px;font-size:16px;font-weight:850;letter-spacing:-.1em;
}
.brandname{color:#f6f7ff;font-size:18px;font-weight:800;letter-spacing:-.055em;}
.brandname span{color:#a79cff;}
.brandcaption{
  margin-top:1px; color:#858d9e;font-size:10px;
  font-weight:750;letter-spacing:.17em;
}
.brand-right{margin-left:auto;display:flex;align-items:center;gap:8px;}
.live-dot{height:7px;width:7px;background:#70ccb5;border-radius:50%;box-shadow:0 0 0 3px #70ccb524}
.live-label{color:#adb8c6;font-size:11px;font-weight:750;letter-spacing:.11em;}
.page-kicker{
  color:#a79cff;font-size:11px;font-weight:800;letter-spacing:.18em;
  margin:4px 0 8px;
}
.page-title{
  font-size:clamp(29px,4vw,43px);line-height:1.12;
  color:#f7f8fd;font-weight:790;letter-spacing:-.055em;margin:0 0 8px;
}
.page-subtitle{font-size:14px;color:#9ca6b7;line-height:1.6;margin:0 0 24px;}
.muted-line{color:#8993a4;font-size:12px;}
.eyebrow{color:#a79cff;letter-spacing:.13em;font-weight:800;font-size:11px;margin-bottom:8px;}
.metricbox{
  background:linear-gradient(145deg,#1b2030,#151a24);
  border:1px solid #2d3546;
  border-radius:14px;
  padding:17px 19px;
  min-height:101px;
  margin:0 0 18px;
}
.metric-label{
  font-size:11px;letter-spacing:.10em;color:#929bae;
  font-weight:780;text-transform:uppercase;
}
.metric-value{
  margin-top:5px;color:#f4f4fa;font-size:29px;
  font-weight:780;letter-spacing:-.055em;line-height:1.2;
}
.metric-note{color:#768292;font-size:11px;margin-top:4px;}
.panel-kicker{font-size:11px;letter-spacing:.15em;color:#969fae;font-weight:800;}

/* Calendar grid */
.calendar-frame{
  background:#131822;border:1px solid #2c3444;
  border-radius:18px;padding:18px;
}
.cal-month{
  font-size:23px;color:#f4f5fa;font-weight:760;letter-spacing:-.045em;
  padding:1px 2px 0;
}
.cal-weekday{
  text-align:center;color:#8894a7;font-size:10px;
  font-weight:850;letter-spacing:.12em;
  padding:10px 0 9px;
}
[class*="st-key-cal-cell-"] {
  background:#171d29!important;
  border:1px solid #2a3140!important;
  border-radius:11px!important;
  padding:8px 9px!important;
  min-height:110px!important;
  transition:border-color .14s ease, background .14s ease;
}
[class*="st-key-cal-cell-"] [data-testid="stVerticalBlock"]{
  gap:3px!important;
}
[class*="st-key-cal-cell-"]:hover{
  border-color:#5e6285!important;
}
[class*="st-key-cal-cell-selected-"]{
  border-color:#a79cff!important;
  background:#25253f!important;
  box-shadow:inset 0 0 0 1px #a79cff40!important;
}
[class*="st-key-cal-cell-today-"]{
  border-color:#526a7a!important;
}
[class*="st-key-cal-cell-outside-"]{
  background:#10151e!important;
  opacity:.44;
}
[class*="st-key-cal-cell-"] [data-testid="stButton"] button {
  border:none!important;
  background:transparent!important;
  border-radius:7px!important;
  min-height:28px!important;
  height:28px!important;
  padding:1px 7px!important;
  font-size:13px!important;
  font-weight:730!important;
  color:#ecedf7!important;
  width:auto!important;
}
[class*="st-key-cal-cell-"] [data-testid="stButton"] button:hover{
  background:#353750!important;
}
[class*="st-key-cal-cell-selected-"] [data-testid="stButton"] button{
  background:#a79cff!important;color:#131123!important;
}
.cal-outside-date{font-weight:650;font-size:13px;color:#677285;padding:4px 5px;}
.cal-events{margin-top:6px;display:flex;flex-direction:column;gap:4px;}
.cal-event{
  border-radius:5px;padding:4px 6px;
  font-size:10px;line-height:1.25;
  font-weight:630;
  white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;
  border-left:2px solid #a79cff;
  color:#dcd7ff;background:#a79cff17;
}
.cal-event.school{background:#80d5c214;color:#a5e8d8;border-color:#80d5c2;}
.cal-more{color:#a6afc1;font-size:10px;font-weight:650;padding:1px 5px;}
.cal-count{display:none;color:#bcb6ff;font-size:10px;padding:1px 5px;font-weight:750;}
.cal-finished{color:#7fcdb7;font-size:10px;font-weight:650;padding:5px 4px;}
.cal-quiet{color:#536074;font-size:11px;padding:5px 4px;}
.cal-today-flag{
  color:#78d6c2;font-size:9px;letter-spacing:.09em;
  font-weight:850;display:inline-block;margin-left:6px;
}
.cal-detail-title{
  color:#f7f8fd;font-size:20px;font-weight:760;
  letter-spacing:-.045em;margin:4px 0 2px;
}
.cal-detail-sub{color:#a0a9b9;font-size:12px;margin-bottom:15px;}
.cal-task-title{color:#e9ebf6;font-size:14px;font-weight:680;margin:2px 0;}
.cal-task-meta{font-size:11px;color:#919aaa;margin-top:4px;}
.cal-no-tasks{
  color:#a1acba;font-size:13px;line-height:1.6;
  background:#101620;border:1px dashed #354052;
  padding:20px 16px;border-radius:12px;margin:10px 0 16px;
}
.task-title{color:#eaedf8;font-weight:730;font-size:14px;line-height:1.35;}
.task-meta{color:#98a3b2;font-size:12px;margin-top:5px;}
.task-status{
  border:1px solid #444a63;padding:4px 8px;
  background:#242a3a;border-radius:8px;
  color:#bdbaff;font-size:10px;font-weight:750;
}
.task-group-label{
  color:#b4bdcb;font-size:12px;font-weight:750;
  letter-spacing:.08em;
  padding-bottom:6px;
}
@media(max-width:1050px){
 [data-testid="stMainBlockContainer"]{
  padding:1rem 1.3rem 3rem!important;
 }
 [class*="st-key-cal-cell-"]{padding:6px 5px!important;}
 .cal-event{font-size:9px;padding:4px;}
}
@media(max-width:700px){
 .brand-right{display:none;}
 .calendar-frame{padding:10px;}
 .metricbox{padding:12px;min-height:85px;}
 .metric-value{font-size:23px;}
 .cal-event{display:none;}
 .cal-count{display:block;}
 .cal-more,.cal-quiet,.cal-finished{font-size:9px;}
 [class*="st-key-cal-cell-"]{min-height:72px!important;padding:4px!important;}
 [class*="st-key-cal-cell-"] [data-testid="stButton"] button{font-size:12px!important;padding:0 5px!important;}
 .cal-weekday{font-size:9px;letter-spacing:0;}
 [data-testid="stTabs"] [data-baseweb="tab"]{padding:8px 12px!important;font-size:12px!important;}
}
</style>
"""


def install_theme():
    """Inject stable Streamlit CSS after set_page_config."""
    st.markdown(STYLE, unsafe_allow_html=True)


def header():
    st.markdown(
        '<div class="brandbar">'
        '<div class="brandmark">A<span style="color:#a79cff;">1</span></div>'
        '<div><div class="brandname">AARON<span>—1</span></div>'
        '<div class="brandcaption">PERSONAL WORKSPACE</div></div>'
        '<div class="brand-right"><span class="live-dot"></span>'
        '<span class="live-label">LOCAL MODE</span></div>'
        '</div>', unsafe_allow_html=True
    )


def page_heading(kicker, title, description):
    st.markdown(
        '<div class="page-kicker">' + html.escape(kicker.upper()) + '</div>'
        '<div class="page-title">' + html.escape(title) + '</div>'
        '<div class="page-subtitle">' + html.escape(description) + '</div>',
        unsafe_allow_html=True,
    )


def metric(label, value, note=""):
    st.markdown(
        '<div class="metricbox">'
        '<div class="metric-label">' + html.escape(str(label)) + '</div>'
        '<div class="metric-value">' + html.escape(str(value)) + '</div>'
        + ('<div class="metric-note">' + html.escape(str(note)) + '</div>' if note else '')
        + '</div>',
        unsafe_allow_html=True,
    )
