import streamlit as st
import plotly.graph_objects as go
import random
import math

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monty Hall · Bayesian Explorer",
    page_icon="🚪",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
.stApp { background: #0d0d14; color: #e8e4d9; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; letter-spacing: -0.03em; }

.stTabs [data-baseweb="tab-list"] { background: #0d0d14; border-bottom: 1px solid #1e1e2e; gap: 8px; }
.stTabs [data-baseweb="tab"] {
    background: transparent; color: #6b6b80;
    font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
    padding: 0.5rem 1.2rem; border-radius: 6px 6px 0 0;
    border: 1px solid transparent; border-bottom: none;
}
.stTabs [aria-selected="true"] { background: #16161f !important; color: #e8e4d9 !important; border-color: #2a2a3a !important; }

.door-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.12em;
    color: #6b6b80; text-align: center; margin-top: 4px;
}
.metric-card {
    background: #16161f; border: 1px solid #2a2a3a;
    border-radius: 12px; padding: 1rem 1.2rem; text-align: center;
}
.metric-label { font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; color: #6b6b80; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.3rem; }
.metric-value { font-size: 1.8rem; font-weight: 800; color: #e8e4d9; }

.insight-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-left: 3px solid #f5a623; border-radius: 0 8px 8px 0;
    padding: 1rem 1.4rem; margin: 0.8rem 0;
    font-size: 0.88rem; line-height: 1.6; color: #c8c4b9;
}
.log-table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }
.log-table th { color: #6b6b80; text-transform: uppercase; letter-spacing: 0.08em; padding: 6px 10px; border-bottom: 1px solid #1e1e2e; text-align: left; }
.log-table td { padding: 5px 10px; border-bottom: 1px solid #16161f; }
.win  { color: #4ade80; }
.lose { color: #e05c5c; }

div[data-testid="stSidebar"] { background: #0a0a10 !important; border-right: 1px solid #1e1e2e; }
</style>
""", unsafe_allow_html=True)


# ── Bayesian math ─────────────────────────────────────────────────────────────
def compute_posterior(n_doors: int, n_opened: int):
    """Returns (p_stay, p_each_switch)."""
    if n_doors - 1 - n_opened == 0:
        return 1.0, 0.0
    lr = (n_doors - 1) / (n_doors - 1 - n_opened)
    unnorm_stay   = (1 / n_doors) * lr
    unnorm_switch = (1 / n_doors) * 1.0
    n_rem = n_doors - 1 - n_opened
    total = unnorm_stay + n_rem * unnorm_switch
    return unnorm_stay / total, unnorm_switch / total


# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = dict(
        phase="pick",
        n_doors=3,
        n_opened=1,
        player_door=None,
        car_door=None,
        opened_doors=[],
        final_door=None,
        won=None,
        history=[],
        round_num=0,
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()
S = st.session_state


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚪 Game Settings")
    st.markdown("---")

    n_doors = st.slider("Total doors (N)", 3, 20, S.n_doors, key="sb_ndoors")

    max_open = n_doors - 2
    # FIX: clamp default value so it always falls within [1, max_open]
    safe_n_opened = max(1, min(S.n_opened, max_open))
    n_opened = st.slider("Doors host opens (k)", 1, max_open, safe_n_opened, key="sb_nopened")
    S.n_opened = n_opened  # keep state in sync

    # Reset game state if settings changed
    if n_doors != S.n_doors or n_opened != S.n_opened:
        S.n_doors   = n_doors
        S.n_opened  = n_opened
        S.phase       = "pick"
        S.player_door = None
        S.car_door    = None
        S.opened_doors = []
        S.final_door  = None
        S.won         = None

    S.n_doors  = n_doors
    S.n_opened = n_opened

    st.markdown("---")
    if st.button("🔄 Reset History", use_container_width=True):
        S.history   = []
        S.round_num = 0
        S.phase       = "pick"
        S.player_door = None
        S.car_door    = None
        S.opened_doors = []
        S.final_door  = None
        S.won         = None

    stay_w = sum(1 for r in S.history if r["action"] == "stay"   and r["won"])
    stay_t = sum(1 for r in S.history if r["action"] == "stay")
    sw_w   = sum(1 for r in S.history if r["action"] == "switch" and r["won"])
    sw_t   = sum(1 for r in S.history if r["action"] == "switch")

    st.markdown("---")
    st.markdown(
        f"<div style='font-family:JetBrains Mono;font-size:0.78rem;line-height:2'>"
        f"<span style='color:#6b6b80'>Rounds played:</span> <b>{len(S.history)}</b><br>"
        f"<span style='color:#f5a623'>Stay wins:</span> <b>{stay_w}/{stay_t}</b>"
        f"{'  ('+f'{stay_w/stay_t:.0%}'+')' if stay_t else ''}<br>"
        f"<span style='color:#4ade80'>Switch wins:</span> <b>{sw_w}/{sw_t}</b>"
        f"{'  ('+f'{sw_w/sw_t:.0%}'+')' if sw_t else ''}"
        f"</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='font-family:JetBrains Mono;font-size:0.7rem;color:#3a3a4a;margin-top:1rem;line-height:1.8'>"
        "🟡 Your pick &nbsp; 🔴 Opened &nbsp; 🟢 Switch<br>"
        "🏆 Car + your door &nbsp; 🚗 Car (missed)</div>",
        unsafe_allow_html=True
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:0'>Monty Hall</h1>"
    "<h2 style='color:#6b6b80;font-weight:400;margin-top:0;font-size:1rem;letter-spacing:0.06em'>"
    "INTERACTIVE BAYESIAN EXPLORER</h2>",
    unsafe_allow_html=True
)

tab_game, tab_theory = st.tabs(["🎮  Play the Game", "📐  Bayesian Theory"])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — GAME
# ═══════════════════════════════════════════════════════════════════════════════
with tab_game:

    phase_info = {
        "pick":    ("01 / PICK A DOOR",       "Choose any door. The car is hidden randomly behind one of them."),
        "decide":  ("02 / STAY OR SWITCH?",   f"The host opened {n_opened} goat door(s). Click your original door to stay, or any other remaining door to switch."),
        "outcome": ("03 / OUTCOME",           ""),
    }
    ph_title, ph_sub = phase_info[S.phase]
    st.markdown(
        f"<div style='margin:0.5rem 0 1rem 0'>"
        f"<span style='font-family:JetBrains Mono;font-size:0.7rem;color:#6b6b80;letter-spacing:0.15em'>{ph_title}</span>"
        f"<p style='margin:0.2rem 0 0 0;color:#c8c4b9;font-size:0.9rem'>{ph_sub}</p>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Door grid ─────────────────────────────────────────────────────────────
    doors = list(range(1, n_doors + 1))
    COLS  = min(n_doors, 10)
    n_rows = math.ceil(n_doors / COLS)

    door_idx = 0
    for row in range(n_rows):
        cols_ui = st.columns(COLS)
        for ci in range(COLS):
            if door_idx >= n_doors:
                break
            d = doors[door_idx]
            door_idx += 1

            is_player = (d == S.player_door)
            is_opened = (d in S.opened_doors)
            is_car    = (S.phase == "outcome" and d == S.car_door)
            is_final  = (d == S.final_door)

            # Emoji + colour
            if S.phase == "outcome":
                if is_opened:
                    emoji, clr = "🐐", "#e05c5c"
                elif is_car and is_final:
                    emoji, clr = "🏆", "#f5a623"
                elif is_car:
                    emoji, clr = "🚗", "#4ade80"
                elif is_final:
                    emoji, clr = "😞", "#e05c5c"
                else:
                    emoji, clr = "🚪", "#3a3a4a"
            elif is_opened:
                emoji, clr = "🐐", "#e05c5c"
            elif is_player:
                emoji, clr = "👆", "#f5a623"
            else:
                emoji, clr = "🚪", "#2a2a3a"

            # Sub-label
            sub = ""
            if S.phase == "decide":
                if is_opened:   sub = "goat"
                elif is_player: sub = "your pick"
                else:           sub = "switch?"
            elif S.phase == "outcome":
                if is_opened:              sub = "goat"
                elif is_final and is_car:  sub = "WIN 🎉"
                elif is_final:             sub = "your choice"
                elif is_car:               sub = "car was here"

            disabled = (
                is_opened
                or S.phase == "outcome"
            )

            with cols_ui[ci]:
                clicked = st.button(
                    f"{emoji} {d}",
                    key=f"door_{d}_r{S.round_num}",
                    disabled=disabled,
                    use_container_width=True,
                    type="primary" if (is_player and S.phase == "decide") else "secondary",
                )
                st.markdown(
                    f"<div class='door-label' style='color:{clr}'>{sub or f'door {d}'}</div>",
                    unsafe_allow_html=True
                )

            if clicked:
                if S.phase == "pick":
                    S.player_door = d
                    S.car_door    = random.choice(doors)
                    # Host picks k goat doors: not player's door, not the car door
                    eligible = [x for x in doors if x != S.player_door and x != S.car_door]
                    if S.car_door == S.player_door:
                        eligible = [x for x in doors if x != S.player_door]
                    S.opened_doors = random.sample(eligible, n_opened)
                    S.phase = "decide"
                    st.rerun()

                elif S.phase == "decide":
                    S.final_door = d
                    S.won        = (d == S.car_door)
                    action       = "stay" if d == S.player_door else "switch"
                    S.round_num += 1
                    S.history.append(dict(
                        round=S.round_num,
                        n_doors=n_doors,
                        n_opened=n_opened,
                        player_door=S.player_door,
                        car_door=S.car_door,
                        final_door=d,
                        action=action,
                        won=S.won,
                    ))
                    S.phase = "outcome"
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Outcome banner ────────────────────────────────────────────────────────
    if S.phase == "outcome":
        action_taken = S.history[-1]["action"]
        if S.won:
            st.success(f"🏆 **You won!** You chose to **{action_taken}** and the car was behind door {S.final_door}.")
        else:
            st.error(f"😞 **You lost.** You chose to **{action_taken}** — the car was behind door {S.car_door}.")

        p_st, p_sw = compute_posterior(n_doors, n_opened)
        n_rem = n_doors - 1 - n_opened
        st.markdown(
            f"<div class='insight-box'>"
            f"<b style='color:#f5a623'>Bayesian odds at decision time</b><br>"
            f"P(car at your original door) = <b>{p_st:.4f}</b> &nbsp;·&nbsp; "
            f"P(car at each switch door) = <b>{p_sw:.4f}</b><br>"
            f"Switching gave a <b style='color:#4ade80'>{(n_rem * p_sw / p_st):.2f}× total advantage</b> "
            f"({n_rem} switch door{'s' if n_rem > 1 else ''} × {p_sw:.4f} vs {p_st:.4f})"
            f"</div>",
            unsafe_allow_html=True
        )

        if st.button("▶ Play Next Round", type="primary"):
            S.phase        = "pick"
            S.player_door  = None
            S.car_door     = None
            S.opened_doors = []
            S.final_door   = None
            S.won          = None
            st.rerun()

    # ── Session history ───────────────────────────────────────────────────────
    if S.history:
        st.markdown("---")
        st.markdown("### Session Results")

        c1, c2, c3, c4 = st.columns(4)
        def mcard(col, label, val, color="#e8e4d9"):
            col.markdown(
                f"<div class='metric-card'><div class='metric-label'>{label}</div>"
                f"<div class='metric-value' style='color:{color}'>{val}</div></div>",
                unsafe_allow_html=True
            )

        total_w = sum(1 for r in S.history if r["won"])
        mcard(c1, "Rounds",          len(S.history))
        mcard(c2, "Overall win %",   f"{total_w / len(S.history):.0%}")
        mcard(c3, f"Stay  {stay_w}/{stay_t}",   f"{stay_w/stay_t:.0%}"  if stay_t else "—", "#f5a623")
        mcard(c4, f"Switch {sw_w}/{sw_t}", f"{sw_w/sw_t:.0%}" if sw_t else "—", "#4ade80")

        st.markdown("<br>", unsafe_allow_html=True)

        # Cumulative win-rate chart
        if len(S.history) >= 2:
            xs = list(range(1, len(S.history) + 1))
            cum_stay, cum_sw = [], []
            st2 = sw2 = st_w2 = sw_w2 = 0
            for r in S.history:
                if r["action"] == "stay":
                    st2 += 1; st_w2 += r["won"]
                else:
                    sw2 += 1; sw_w2 += r["won"]
                cum_stay.append(st_w2 / st2 if st2 else None)
                cum_sw.append(sw_w2 / sw2   if sw2 else None)

            p_st_th, p_sw_th = compute_posterior(n_doors, n_opened)
            n_rem_th = n_doors - 1 - n_opened

            fig = go.Figure()
            fig.add_hline(y=p_st_th, line_dash="dot", line_color="rgba(245,166,35,0.3)",
                          annotation_text=f"theory stay {p_st_th:.1%}",
                          annotation_font_color="#f5a62388", annotation_position="right")
            fig.add_hline(y=n_rem_th * p_sw_th, line_dash="dot", line_color="rgba(74,222,128,0.3)",
                          annotation_text=f"theory switch {n_rem_th*p_sw_th:.1%}",
                          annotation_font_color="#4ade8088", annotation_position="right")
            fig.add_trace(go.Scatter(
                x=xs, y=cum_stay, mode="lines+markers", name="Stay win rate",
                line=dict(color="#f5a623", width=2.5), marker=dict(size=5), connectgaps=True,
                hovertemplate="Round %{x}<br>Stay win rate: %{y:.1%}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=xs, y=cum_sw, mode="lines+markers", name="Switch win rate",
                line=dict(color="#4ade80", width=2.5, dash="dash"), marker=dict(size=5), connectgaps=True,
                hovertemplate="Round %{x}<br>Switch win rate: %{y:.1%}<extra></extra>",
            ))
            fig.update_layout(
                plot_bgcolor="#16161f", paper_bgcolor="#16161f",
                font=dict(family="Syne", color="#c8c4b9"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)",
                            font=dict(family="JetBrains Mono", size=11)),
                xaxis=dict(title="Round", showgrid=True, gridcolor="#1e1e2e",
                           tickfont=dict(family="JetBrains Mono", size=10)),
                yaxis=dict(title="Cumulative win rate", showgrid=True, gridcolor="#1e1e2e",
                           tickformat=".0%", range=[0, 1],
                           tickfont=dict(family="JetBrains Mono", size=10)),
                margin=dict(l=10, r=90, t=40, b=10), height=280,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Round-by-round log
        st.markdown("#### Round log")
        rows_html = ""
        for r in reversed(S.history[-50:]):
            wc = "win" if r["won"] else "lose"
            ws = "✓ Win" if r["won"] else "✗ Lose"
            ac = "#f5a623" if r["action"] == "stay" else "#4ade80"
            rows_html += (
                f"<tr>"
                f"<td>#{r['round']}</td>"
                f"<td>{r['n_doors']}D / {r['n_opened']}open</td>"
                f"<td>Door {r['player_door']}</td>"
                f"<td>Door {r['car_door']}</td>"
                f"<td style='color:{ac}'>{r['action'].upper()}</td>"
                f"<td>Door {r['final_door']}</td>"
                f"<td class='{wc}'>{ws}</td>"
                f"</tr>"
            )
        st.markdown(
            f"<table class='log-table'><thead><tr>"
            f"<th>#</th><th>Game</th><th>First pick</th><th>Car</th><th>Action</th><th>Final</th><th>Result</th>"
            f"</tr></thead><tbody>{rows_html}</tbody></table>",
            unsafe_allow_html=True
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THEORY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_theory:
    st.markdown("### Bayesian Probability Explorer")
    st.markdown(
        "<p style='color:#6b6b80;font-size:0.88rem;margin-top:-0.5rem'>"
        "Adjust the sliders in the sidebar to explore any N-door, k-open scenario.</p>",
        unsafe_allow_html=True
    )

    p_prior = 1 / n_doors
    p_st_th, p_sw_th = compute_posterior(n_doors, n_opened)
    n_rem_th = n_doors - 1 - n_opened
    p_all_sw = n_rem_th * p_sw_th

    c1, c2, c3, c4 = st.columns(4)
    def mcard2(col, label, val, color="#e8e4d9"):
        col.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value' style='color:{color}'>{val}</div></div>",
            unsafe_allow_html=True
        )
    mcard2(c1, "Prior (uniform)",  f"{p_prior:.3f}")
    mcard2(c2, "P(Stay) door 1",   f"{p_st_th:.3f}",  "#f5a623")
    mcard2(c3, "P(Switch) each",   f"{p_sw_th:.3f}",  "#4ade80")
    mcard2(c4, "Switch advantage", f"{p_all_sw / p_st_th:.2f}×", "#c084fc")

    st.markdown("<br>", unsafe_allow_html=True)

    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown("#### Door-by-door probabilities")
        all_doors  = list(range(1, n_doors + 1))
        opened_set = set(range(2, 2 + n_opened))

        bar_prior_v, bar_post_v, bar_clrs = [], [], []
        for d in all_doors:
            bar_prior_v.append(p_prior)
            if d == 1:
                bar_post_v.append(p_st_th); bar_clrs.append("#f5a623")
            elif d in opened_set:
                bar_post_v.append(0.0);     bar_clrs.append("#e05c5c")
            else:
                bar_post_v.append(p_sw_th); bar_clrs.append("#4ade80")

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=[f"D{d}" for d in all_doors], y=bar_prior_v, name="Prior",
            marker_color="rgba(255,255,255,0.1)",
            marker_line_color="rgba(255,255,255,0.25)", marker_line_width=1,
        ))
        fig_bar.add_trace(go.Bar(
            x=[f"D{d}" for d in all_doors], y=bar_post_v, name="Posterior",
            marker_color=bar_clrs,
            marker_line_color="rgba(0,0,0,0.3)", marker_line_width=1,
            text=[f"{v:.1%}" if v > 0.001 else "0%" for v in bar_post_v],
            textposition="outside",
            textfont=dict(family="JetBrains Mono", size=9, color="#c8c4b9"),
        ))
        fig_bar.update_layout(
            barmode="overlay", plot_bgcolor="#16161f", paper_bgcolor="#16161f",
            font=dict(family="Syne", color="#c8c4b9"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)",
                        font=dict(family="JetBrains Mono", size=11)),
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(family="JetBrains Mono", size=10)),
            yaxis=dict(showgrid=True, gridcolor="#1e1e2e", zeroline=False, tickformat=".0%",
                       tickfont=dict(family="JetBrains Mono", size=10)),
            margin=dict(l=10, r=10, t=40, b=10), height=320,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_r:
        st.markdown("#### Stay vs. Switch share")
        fig_donut = go.Figure(go.Pie(
            labels=["Stay (Door 1)", f"{n_rem_th} Switch door{'s' if n_rem_th > 1 else ''}", f"{n_opened} Opened"],
            values=[p_st_th, p_all_sw, n_opened / n_doors],
            hole=0.62,
            marker=dict(colors=["#f5a623", "#4ade80", "#e05c5c"], line=dict(color="#0d0d14", width=3)),
            textfont=dict(family="JetBrains Mono", size=10),
            textinfo="label+percent", sort=False,
        ))
        fig_donut.update_layout(
            plot_bgcolor="#16161f", paper_bgcolor="#16161f",
            font=dict(family="Syne", color="#c8c4b9"), showlegend=False,
            margin=dict(l=10, r=10, t=30, b=10), height=320,
            annotations=[dict(
                text=f"<b>{p_all_sw / p_st_th:.1f}×</b><br>switch edge",
                x=0.5, y=0.5, font=dict(size=16, family="Syne", color="#e8e4d9"), showarrow=False,
            )]
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Updating line chart
    st.markdown("#### Bayesian updating as each door is opened")
    steps = list(range(0, n_opened + 1))
    ps_line, pw_line = [], []
    for k in steps:
        a, b = compute_posterior(n_doors, k)
        ps_line.append(a)
        pw_line.append(b)

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=steps, y=ps_line, mode="lines+markers", name="P(Stay)",
        line=dict(color="#f5a623", width=2.5),
        marker=dict(size=7, color="#f5a623", line=dict(color="#0d0d14", width=2)),
        hovertemplate="k=%{x}<br>P(stay): %{y:.4f}<extra></extra>",
    ))
    fig_line.add_trace(go.Scatter(
        x=steps, y=pw_line, mode="lines+markers", name="P(Switch) per door",
        line=dict(color="#4ade80", width=2.5, dash="dash"),
        marker=dict(size=7, color="#4ade80", line=dict(color="#0d0d14", width=2)),
        hovertemplate="k=%{x}<br>P(each switch): %{y:.4f}<extra></extra>",
    ))
    fig_line.add_vline(x=n_opened, line_dash="dot", line_color="rgba(255,255,255,0.15)")
    fig_line.update_layout(
        plot_bgcolor="#16161f", paper_bgcolor="#16161f",
        font=dict(family="Syne", color="#c8c4b9"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)",
                    font=dict(family="JetBrains Mono", size=11)),
        xaxis=dict(title="Doors opened (k)", showgrid=True, gridcolor="#1e1e2e", dtick=1,
                   tickfont=dict(family="JetBrains Mono", size=10)),
        yaxis=dict(title="Probability", showgrid=True, gridcolor="#1e1e2e", tickformat=".1%",
                   tickfont=dict(family="JetBrains Mono", size=10)),
        margin=dict(l=10, r=10, t=40, b=10), height=260,
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown(
        f"<div class='insight-box'>"
        f"<b style='color:#f5a623'>🔍 Bayesian Insight</b> &nbsp; N={n_doors}, k={n_opened}<br><br>"
        f"Prior: <b>1/{n_doors} = {p_prior:.4f}</b> per door. "
        f"After the host reveals {n_opened} goat door{'s' if n_opened > 1 else ''}, "
        f"the likelihood ratio is <b>(N−1)/(N−1−k) = {n_doors-1}/{n_doors-1-n_opened} "
        f"= {(n_doors-1)/(n_doors-1-n_opened):.3f}</b>, "
        f"boosting the stay door to <b>{p_st_th:.4f}</b> while each of the {n_rem_th} "
        f"remaining switch door{'s' if n_rem_th > 1 else ''} reaches <b>{p_sw_th:.4f}</b>. "
        f"Switching in total is <b style='color:#4ade80'>{p_all_sw / p_st_th:.2f}× more likely to win</b>."
        f"</div>",
        unsafe_allow_html=True
    )

    with st.expander("📐 Show the maths"):
        st.markdown(r"""
**Uniform prior:** $P(\text{car at door } d) = 1/N$ for all $d$.

**Likelihoods** — let $E$ = "host opens exactly these $k$ doors":

$$P(E \mid \text{car at door 1}) = 1, \qquad P(E \mid \text{car at door } d^* \neq 1) = \frac{N-1-k}{N-1}$$

**Posterior via Bayes:**

$$P(\text{stay wins}) = \frac{1}{N-k}, \qquad P(\text{each switch door wins}) = \frac{N-1}{(N-k)(N-1-k)}$$

**Total switching advantage:**

$$\frac{(N-1-k) \cdot P(\text{switch per door})}{P(\text{stay})} = \frac{N-1}{N-1-k}$$

For the classic 3-door / 1-open case: stay = **1/3**, switch = **2/3** — exactly **2× better** to switch.
""")
