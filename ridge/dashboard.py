import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta, date
import tzlocal

DB_PATH = Path.home() / ".ridge" / "data.db"
LOCAL_TZ = tzlocal.get_localzone()

st.set_page_config(page_title="Ridge — Focus Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@300;400;500;600;700&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,300&display=swap');
html,body,[class*="css"]{font-family:'Outfit',sans-serif!important}
.stApp{background:#060608}
[data-testid="stSidebar"]{background:#0a0a0f;border-right:1px solid rgba(255,255,255,0.06)}
#MainMenu,footer,header{visibility:hidden}
[data-testid="stMetric"]{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:20px!important;transition:border-color 0.2s}
[data-testid="stMetric"]:hover{border-color:rgba(245,166,35,0.3)}
[data-testid="stMetricLabel"] p{font-family:'Space Mono',monospace!important;font-size:9px!important;letter-spacing:0.12em!important;color:rgba(240,238,232,0.35)!important;text-transform:uppercase!important}
[data-testid="stMetricValue"]{font-family:'Fraunces',serif!important;font-size:28px!important;color:#f5a623!important;font-weight:600!important}
.stButton>button{background:rgba(245,166,35,0.08)!important;border:1px solid rgba(245,166,35,0.2)!important;color:#f5a623!important;border-radius:8px!important;font-family:'Space Mono',monospace!important;font-size:11px!important;width:100%!important;padding:8px!important}
.stButton>button:hover{background:rgba(245,166,35,0.18)!important;border-color:rgba(245,166,35,0.45)!important}
[data-baseweb="select"]>div{background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.08)!important;border-radius:8px!important;color:#f0eee8!important}
[data-testid="stDataFrame"]{border:1px solid rgba(255,255,255,0.07)!important;border-radius:12px!important}
h1,h2,h3{color:#f0eee8!important}
::-webkit-scrollbar{width:3px}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}
[data-testid="stDateInput"] input{background:rgba(255,255,255,0.04)!important;border:1px solid rgba(255,255,255,0.08)!important;border-radius:6px!important;color:#f0eee8!important;font-family:Space Mono,monospace!important;font-size:11px!important}
[data-testid="stDateInput"] label{font-family:Space Mono,monospace!important;font-size:9px!important;color:rgba(240,238,232,0.35)!important}
[data-testid="stVerticalBlock"]{gap:0}
div[data-testid="column"]{padding:0 6px}
</style>
""", unsafe_allow_html=True)

BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,255,255,0.015)",
    font=dict(family="Space Mono, monospace", color="rgba(240,238,232,0.45)", size=10),
    margin=dict(l=0, r=0, t=32, b=0),
    hoverlabel=dict(bgcolor="#1a1a24", bordercolor="rgba(255,255,255,0.1)",
                    font=dict(family="Space Mono", color="#f0eee8", size=11)),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.06)", zeroline=False),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)", linecolor="rgba(255,255,255,0.06)", zeroline=False),
)
COLORS = {"deep": "#3ecf8e", "shallow": "#f5c842", "escape": "#f16060"}

def merge_layout(overrides):
    import copy
    out = copy.deepcopy(BASE)
    for k, v in overrides.items():
        if isinstance(v, dict) and k in out and isinstance(out[k], dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out

# ── DATA ────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_events(since_date: str):
    if not DB_PATH.exists(): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM events WHERE ts>=? ORDER BY ts", conn, params=(since_date,))
    conn.close()
    if df.empty: return df
    df["ts"] = pd.to_datetime(df["ts"]).dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
    df["date"] = df["ts"].dt.date
    df["hour"] = df["ts"].dt.hour
    df["category"] = df["category"].fillna("shallow")
    return df

@st.cache_data(ttl=30)
def load_sessions(since_date: str):
    if not DB_PATH.exists(): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM sessions WHERE started_at>=? ORDER BY started_at", conn, params=(since_date,))
    conn.close()
    if df.empty: return df
    df["started_at"] = pd.to_datetime(df["started_at"]).dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
    df["date"] = df["started_at"].dt.date
    return df

def calc_score(df):
    if df.empty: return 0
    total = len(df)
    deep = len(df[df["category"] == "deep"])
    escape = len(df[df["category"] == "escape"])
    switches = (df["app"].dropna() != df["app"].dropna().shift()).sum()
    return min(100, max(0, round((deep/total)*70 + max(0,20-(switches*0.67)) + max(0,10-((escape/total)*50)))))

def hm(n):
    m = round(n * 0.5)
    return f"{m//60}h {m%60:02d}m"

def score_color(s):
    return "#3ecf8e" if s >= 70 else "#f5c842" if s >= 50 else "#f16060"

def score_label(s):
    if s >= 85: return "Exceptional"
    if s >= 70: return "Good"
    if s >= 55: return "Average"
    if s >= 40: return "Scattered"
    return "Distracted"

# ── SIDEBAR ─────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style='padding:16px 0 28px'>
        <div style='font-family:Space Mono,monospace;font-size:20px;font-weight:700;color:#f5a623;letter-spacing:-0.5px'>ridge.</div>
        <div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.2);letter-spacing:0.18em;margin-top:5px'>FOCUS DASHBOARD</div>
    </div>
    <div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.3);letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px'>Time Period</div>
    """, unsafe_allow_html=True)

    today = datetime.now(tz=LOCAL_TZ).date()

    # Quick select
    st.markdown("<div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.3);letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px'>Quick Select</div>", unsafe_allow_html=True)
    period_options = {
        "Today": 0,
        "Yesterday": 1,
        "Last 3 Days": 3,
        "Last 7 Days": 7,
        "Last 14 Days": 14,
        "Last 30 Days": 30,
        "Last Quarter": 90,
    }
    period = st.selectbox("Period", list(period_options.keys()), index=3, label_visibility="collapsed")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.3);letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px'>Custom Range</div>", unsafe_allow_html=True)

    col_from, col_to = st.columns(2)
    with col_from:
        custom_start = st.date_input("From", value=today - timedelta(days=7),
                                      max_value=today, label_visibility="visible",
                                      key="date_start")
    with col_to:
        custom_end = st.date_input("To", value=today,
                                    max_value=today, label_visibility="visible",
                                    key="date_end")

    use_custom = (custom_start != today - timedelta(days=7) or custom_end != today)

    # Compute date range
    if use_custom:
        since_date = custom_start
        until_date = custom_end + timedelta(days=1)
        period = f"{custom_start.strftime('%b %d')} – {custom_end.strftime('%b %d')}"
    else:
        days = period_options[period]
        if period == "Yesterday":
            since_date = today - timedelta(days=1)
            until_date = today
        elif period == "Today":
            since_date = today
            until_date = today + timedelta(days=1)
        else:
            since_date = today - timedelta(days=days)
            until_date = today + timedelta(days=1)

    since_dt = datetime.combine(since_date, datetime.min.time()).isoformat()
    until_dt = datetime.combine(until_date, datetime.min.time()).isoformat()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("""
    <div style='margin:24px 0;height:1px;background:rgba(255,255,255,0.06)'></div>
    """, unsafe_allow_html=True)

    db_ok = DB_PATH.exists()
    dot_color = "#3ecf8e" if db_ok else "#f16060"
    dot_label = "Tracking ready" if db_ok else "No database found"

    st.markdown(f"""
    <div style='font-family:Space Mono,monospace;font-size:10px;line-height:2.2;color:rgba(240,238,232,0.35)'>
        <div style='margin-bottom:8px'>
            <span style='color:{dot_color}'>●</span>
            <span style='margin-left:6px;color:{dot_color}'>{dot_label}</span>
        </div>
        <div style='color:rgba(240,238,232,0.2);font-size:9px'>~/.ridge/data.db</div>
    </div>
    <div style='margin:20px 0;height:1px;background:rgba(255,255,255,0.06)'></div>
    <div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.2);line-height:2.5'>
        <div style='color:rgba(240,238,232,0.4);letter-spacing:0.12em;font-size:8px;margin-bottom:4px'>COMMANDS</div>
        ridge start "task"<br>
        ridge stop<br>
        ridge status<br>
        ridge report<br>
        ridge week<br>
        ridge sites
    </div>
    <div style='margin:20px 0;height:1px;background:rgba(255,255,255,0.06)'></div>
    <div style='font-family:Space Mono,monospace;font-size:8px;color:rgba(240,238,232,0.15)'>v1.1.0 · MIT License</div>
    """, unsafe_allow_html=True)

# ── LOAD DATA ───────────────────────────────────────────────

events = load_events(since_dt)
sessions = load_sessions(since_dt)

# Filter by until date
if not events.empty:
    until_date_obj = datetime.strptime(until_dt, "%Y-%m-%dT%H:%M:%S").date()
    events = events[events["date"] < until_date_obj]
if not sessions.empty:
    until_date_obj = datetime.strptime(until_dt, "%Y-%m-%dT%H:%M:%S").date()
    sessions = sessions[sessions["date"] < until_date_obj]

if events.empty:
    st.markdown(f"""
    <div style='text-align:center;padding:100px 40px'>
        <div style='font-family:Fraunces,serif;font-size:48px;color:#f0eee8;font-weight:600;letter-spacing:-2px'>No data for {period.lower()}.</div>
        <div style='font-family:Space Mono,monospace;font-size:11px;color:rgba(240,238,232,0.3);margin-top:16px;line-height:2.2'>
            Run ridge start in your terminal to begin tracking.<br>
            Come back after a few minutes.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.code('ridge start "deep work session"', language="bash")
    st.stop()

# ── COMPUTE ─────────────────────────────────────────────────

dn = len(events[events["category"] == "deep"])
sn = len(events[events["category"] == "shallow"])
en = len(events[events["category"] == "escape"])
tn = len(events)
dp = round((dn/tn)*100) if tn else 0
sp = round((sn/tn)*100) if tn else 0
ep = round((en/tn)*100) if tn else 0

daily = []
for d, grp in events.groupby("date"):
    daily.append({
        "date": d.strftime("%b %d") if hasattr(d, "strftime") else str(d),
        "date_raw": d,
        "score": calc_score(grp),
        "deep": len(grp[grp["category"]=="deep"]),
        "shallow": len(grp[grp["category"]=="shallow"]),
        "escape": len(grp[grp["category"]=="escape"]),
        "total": len(grp)
    })
ddf = pd.DataFrame(daily) if daily else pd.DataFrame()

# Score: avg across days for multi-day, single calc for one day
if not ddf.empty and len(ddf) > 1:
    score = round(sum(d["score"] for d in daily) / len(daily))
else:
    score = calc_score(events)

color = score_color(score)
label = score_label(score)

# ── HEADER ──────────────────────────────────────────────────

h1, h2 = st.columns([3, 1])
with h1:
    st.markdown(f"""
    <div style='padding:16px 0 24px'>
        <div style='font-family:Space Mono,monospace;font-size:9px;color:#f5a623;letter-spacing:0.18em;margin-bottom:12px'>● {period.upper()}</div>
        <div style='font-family:Fraunces,serif;font-size:42px;font-weight:600;color:#f0eee8;letter-spacing:-1.5px;line-height:1'>
            Your focus, <span style='color:#f5a623;font-style:italic'>honestly.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
with h2:
    st.markdown(f"""
    <div style='text-align:right;padding-top:28px;font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.2);line-height:2.4'>
        {tn} events<br>
        {len(sessions)} sessions<br>
        {datetime.now().strftime('%b %d, %Y')}
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:1px;background:rgba(255,255,255,0.06);margin-bottom:24px'></div>", unsafe_allow_html=True)

# ── SCORE ROW — 3 equal cards ────────────────────────────────

c1, c2, c3 = st.columns(3)

with c1:
    # Determine if multi-day or single-day
    n_days = len(ddf) if not ddf.empty else 1
    score_title = "Avg Focus Score" if n_days > 1 else "Focus Score"
    score_subtitle = f"{n_days}-day average" if n_days > 1 else "today"

    st.markdown(f"""
    <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;text-align:center;position:relative;overflow:hidden;height:220px;display:flex;flex-direction:column;justify-content:center;align-items:center'>
        <div style='position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,{color},transparent)'></div>
        <div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.3);letter-spacing:0.15em;text-transform:uppercase;margin-bottom:12px'>{score_title}</div>
        <div style='font-family:Fraunces,serif;font-size:80px;font-weight:600;line-height:1;color:{color}'>{score}</div>
        <div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.2);margin-top:2px'>/100</div>
        <div style='font-family:Outfit,sans-serif;font-size:14px;font-weight:600;color:{color};margin-top:8px'>{label}</div>
        <div style='font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.25);margin-top:4px'>{score_subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    # Use plotly pie — no HTML rendering issues
    fig_bk = go.Figure(go.Pie(
        labels=["Deep Work", "Shallow", "Escape"],
        values=[max(dn,0.01), max(sn,0.01), max(en,0.01)],
        hole=0.6,
        marker=dict(colors=["#3ecf8e","#f5c842","#f16060"],
                    line=dict(color="#060608", width=3)),
        textinfo="percent",
        textfont=dict(family="Space Mono", size=10),
        hovertemplate="<b>%{label}</b><br>%{percent} · %{value} events<extra></extra>"
    ))
    fig_bk.add_annotation(text="Split", x=0.5, y=0.5,
                           font=dict(family="Space Mono", size=10, color="rgba(240,238,232,0.3)"),
                           showarrow=False)
    layout_bk = merge_layout({"height": 220, "showlegend": True,
                               "legend": dict(orientation="h", yanchor="bottom", y=-0.15,
                                              xanchor="center", x=0.5,
                                              font=dict(size=10, family="Space Mono"),
                                              bgcolor="rgba(0,0,0,0)"),
                               "title": dict(text="Time Breakdown", font=dict(family="Space Mono", size=9,
                                             color="rgba(240,238,232,0.3)"), x=0),
                               "margin": dict(l=0, r=0, t=32, b=40)})
    fig_bk.update_layout(**layout_bk)
    st.plotly_chart(fig_bk, use_container_width=True)

with c3:
    if not ddf.empty:
        fig_tr = go.Figure()
        fig_tr.add_trace(go.Scatter(
            x=ddf["date"], y=ddf["score"],
            mode="lines+markers",
            line=dict(color="#f5a623", width=2),
            marker=dict(size=6, color="#f5a623", line=dict(width=2, color="#060608")),
            fill="tozeroy", fillcolor="rgba(245,166,35,0.07)",
            hovertemplate="<b>%{x|%b %d}</b><br>Score: %{y}/100<extra></extra>"
        ))
        fig_tr.add_hline(y=70, line_dash="dot", line_color="rgba(62,207,142,0.25)")
        layout_tr = merge_layout({"height": 220,
                                   "yaxis": {"range": [0, 100]},
                                   "title": dict(text="Score Trend", font=dict(family="Space Mono", size=9,
                                                 color="rgba(240,238,232,0.3)"), x=0),
                                   "margin": dict(l=0, r=0, t=32, b=0)})
        fig_tr.update_layout(**layout_tr)
        st.plotly_chart(fig_tr, use_container_width=True)
    else:
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;height:220px;display:flex;align-items:center;justify-content:center'>
            <div style='font-family:Space Mono,monospace;font-size:10px;color:rgba(240,238,232,0.2)'>Not enough data for trend</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── 4 METRIC TILES ───────────────────────────────────────────

m1, m2, m3, m4 = st.columns(4)
with m1: st.metric("Deep Work", hm(dn))
with m2: st.metric("Shallow", hm(sn))
with m3: st.metric("Escape", hm(en))
with m4: st.metric("Sessions", len(sessions))

st.markdown("<div style='height:1px;background:rgba(255,255,255,0.06);margin:28px 0'></div>", unsafe_allow_html=True)

# ── HOURLY ACTIVITY ─────────────────────────────────────────

st.markdown("<div style='font-family:Fraunces,serif;font-size:22px;font-weight:600;color:#f0eee8;margin-bottom:6px'>Hourly Activity</div>", unsafe_allow_html=True)
st.markdown("<div style='font-family:Outfit,sans-serif;font-size:14px;color:rgba(240,238,232,0.5);margin-top:6px;margin-bottom:24px;font-weight:400'>Each bar shows events tracked per hour, split by Deep / Shallow / Escape</div>", unsafe_allow_html=True)

# Build full 0–23 hour range so all hours show
all_hours = pd.DataFrame({"hour": range(24)})
hourly = events.groupby(["hour", "category"]).size().reset_index(name="count")

fig_h = go.Figure()
for cat in ["deep", "shallow", "escape"]:
    d = hourly[hourly["category"] == cat]
    # Merge with all hours so gaps show as 0
    merged = all_hours.merge(d[["hour","count"]], on="hour", how="left").fillna(0)
    fig_h.add_trace(go.Bar(
        x=merged["hour"], y=merged["count"],
        name=cat.capitalize(),
        marker_color=COLORS[cat],
        opacity=0.82,
        hovertemplate=f"<b>%{{x}}:00 – %{{x}}:59</b><br>{cat.capitalize()}: %{{y:.0f}} events<extra></extra>"
    ))

layout_h = merge_layout({
    "height": 260,
    "barmode": "stack",
    "bargap": 0.15,
    "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                   font=dict(size=10, family="Space Mono"), bgcolor="rgba(0,0,0,0)"),
    "title": dict(text="Events by Hour of Day (all 24 hours)", font=dict(family="Space Mono", size=9,
                  color="rgba(240,238,232,0.3)"), x=0),
    "xaxis": {"tickmode": "array", "tickvals": list(range(24)),
              "ticktext": [f"{h:02d}:00" for h in range(24)],
              "tickangle": -45},
})
fig_h.update_layout(**layout_h)
st.plotly_chart(fig_h, use_container_width=True)

st.markdown("<div style='height:1px;background:rgba(255,255,255,0.06);margin:24px 0'></div>", unsafe_allow_html=True)

# ── DAILY BREAKDOWN (if multi-day) ───────────────────────────

if not ddf.empty and len(ddf) > 1:
    st.markdown("<div style='font-family:Fraunces,serif;font-size:22px;font-weight:600;color:#f0eee8;margin-bottom:6px'>Daily Focus Scores</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-family:Outfit,sans-serif;font-size:14px;color:rgba(240,238,232,0.5);margin-top:6px;margin-bottom:24px;font-weight:400'>Line shows your focus score each day. Markers are color-coded — green is good, red is distracted</div>", unsafe_allow_html=True)

    fig_cal = go.Figure()
    fig_cal.add_trace(go.Scatter(
        x=ddf["date"],
        y=ddf["score"],
        mode="lines+markers",
        line=dict(width=2.5, color="#f5a623"),
        marker=dict(
            size=10,
            color=ddf["score"],
            colorscale=[[0,"#f16060"],[0.5,"#f5c842"],[1,"#3ecf8e"]],
            cmin=0, cmax=100,
            line=dict(width=2, color="#060608"),
            showscale=False,
        ),
        fill="tozeroy",
        fillcolor="rgba(245,166,35,0.06)",
        text=ddf["score"].astype(str) + "/100",
        hovertemplate="<b>%{x}</b><br>Focus Score: %{y}/100<extra></extra>"
    ))
    fig_cal.add_hline(y=70, line_dash="dot", line_color="rgba(62,207,142,0.35)",
                      annotation_text="Good (70)", annotation_font_color="rgba(62,207,142,0.6)",
                      annotation_position="right")
    fig_cal.add_hline(y=50, line_dash="dot", line_color="rgba(245,200,66,0.25)",
                      annotation_text="Average (50)", annotation_font_color="rgba(245,200,66,0.45)",
                      annotation_position="right")
    layout_cal = merge_layout({
        "height": 260,
        "yaxis": {"range": [0, 100], "tickvals": [0,25,50,70,85,100],
                  "ticktext": ["0","25","50","70","85","100"]},
        "xaxis": {"type": "category", "tickangle": 0},
        "title": dict(text="Daily Focus Score — each dot is one day",
                      font=dict(family="Space Mono", size=9, color="rgba(240,238,232,0.3)"), x=0)
    })
    fig_cal.update_layout(**layout_cal)
    st.plotly_chart(fig_cal, use_container_width=True)

    st.markdown("<div style='height:1px;background:rgba(255,255,255,0.06);margin:24px 0'></div>", unsafe_allow_html=True)

# ── TOP SITES ───────────────────────────────────────────────

st.markdown("<div style='font-family:Fraunces,serif;font-size:22px;font-weight:600;color:#f0eee8;margin-bottom:6px'>Top Sites</div>", unsafe_allow_html=True)
st.markdown("<div style='font-family:Outfit,sans-serif;font-size:14px;color:rgba(240,238,232,0.5);margin-top:6px;margin-bottom:24px;font-weight:400'>Most visited domains this period, split by Deep Work, Shallow, and Escape</div>", unsafe_allow_html=True)

url_ev = events[events["domain"].notna() & (events["domain"] != "")]
cs1, cs2, cs3 = st.columns(3)

def site_chart(df_sites, cat, color, label):
    d = df_sites[df_sites["category"]==cat].groupby("domain").size().reset_index(name="v")
    d = d.sort_values("v", ascending=True).tail(8)
    if d.empty:
        st.markdown(f"<div style='padding:20px;font-family:Space Mono,monospace;font-size:10px;color:rgba(240,238,232,0.25);border:1px solid rgba(255,255,255,0.06);border-radius:12px;height:200px;display:flex;align-items:center;justify-content:center'>No {cat} sites</div>", unsafe_allow_html=True)
        return
    fig = go.Figure(go.Bar(
        x=d["v"], y=d["domain"], orientation="h",
        marker=dict(color=color, opacity=0.75, line=dict(width=0)),
        hovertemplate="<b>%{y}</b><br>%{x} visits<extra></extra>"
    ))
    layout = merge_layout({"height": max(180, len(d)*30+40),
                            "title": dict(text=label, font=dict(family="Space Mono", size=9, color=color), x=0),
                            "margin": dict(l=0, r=0, t=28, b=0)})
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)

with cs1: site_chart(url_ev, "deep", "#3ecf8e", "Deep Work Sites")
with cs2: site_chart(url_ev, "shallow", "#f5c842", "Shallow Sites")
with cs3: site_chart(url_ev, "escape", "#f16060", "Escape Sites")

st.markdown("<div style='height:1px;background:rgba(255,255,255,0.06);margin:24px 0'></div>", unsafe_allow_html=True)

# ── SESSIONS TABLE ───────────────────────────────────────────

st.markdown("<div style='font-family:Fraunces,serif;font-size:22px;font-weight:600;color:#f0eee8;margin-bottom:20px'>Sessions</div>", unsafe_allow_html=True)

if not sessions.empty:
    disp = sessions[["task","started_at","focus_score"]].copy()
    disp.columns = ["Task","Started","Score"]
    disp["Started"] = disp["Started"].dt.strftime("%b %d, %I:%M %p")
    disp["Score"] = disp["Score"].fillna(0).astype(int)
    disp["Task"] = disp["Task"].fillna("—")
    st.dataframe(disp.sort_values("Started", ascending=False), use_container_width=True, hide_index=True)
else:
    st.markdown("<div style='font-family:Space Mono,monospace;font-size:10px;color:rgba(240,238,232,0.25);padding:20px;border:1px solid rgba(255,255,255,0.06);border-radius:12px'>No sessions found for this period.</div>", unsafe_allow_html=True)

# ── FOOTER ──────────────────────────────────────────────────

st.markdown("<div style='height:1px;background:rgba(255,255,255,0.06);margin:28px 0 16px'></div>", unsafe_allow_html=True)
st.markdown("""
<div style='display:flex;justify-content:space-between;padding-bottom:24px;font-family:Space Mono,monospace;font-size:9px;color:rgba(240,238,232,0.18)'>
    <span style='color:#f5a623;font-size:14px;font-weight:700'>ridge.</span>
    <span>~/.ridge/data.db · zero cloud · zero telemetry</span>
    <span>v1.1.0 · MIT</span>
</div>
""", unsafe_allow_html=True)