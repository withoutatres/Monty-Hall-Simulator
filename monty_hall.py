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
.stTabs [aria-selected="true"] {
    background: #16161f !important; color: #e8e4d9 !important;
    border-color: #2a2a3a !important;
}

.door-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.1em;
    text-align: center; margin-top: 2px;
}
.prob-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; font-weight: 600;
    text-align: center; margin-top: 1px;
}
.metric-card {
    background: #16161f; border: 1px solid #2a2a3a;
    border-radius: 12px; padding: 1rem 1.2rem; text-align: center;
}
.metric-label {
    font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
    color: #6b6b80; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.3rem;
}
.metric-value { font-size: 1.8rem; font-weight: 800; color: #e8e4d9; }

.insight-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-left: 3px solid #f5a623; border-radius: 0 8px 8px 0;
    padding: 1rem 1.4rem; margin: 0.8rem 0;
    font-size: 0.88rem; line-height: 1.6; color: #c8c4b9;
}
.phase-banner {
    margin: 0.5rem 0 1rem 0;
}
.phase-step {
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    color: #6b6b80; letter-spacing: 0.15em;
}
.phase-desc {
    margin: 0.2rem 0 0 0; color: #c8c4b9; font-size: 0.9rem;
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
    """Returns (p_stay, p_each_switch). Works for any n_opened >= 0.

    Correct Bayesian logic:
      L(stay door)   = P(host opens k doors | car at player door) = 1
      L(switch door) = P(host opens k doors | car at specific other door)
                     = (n-1-k)/(n-1)   [host must avoid that door]

    So the likelihood FAVOURS the switch doors:
      unnorm_stay   = (1/n) * 1
      unnorm_switch = (1/n) * (n-1)/(n-1-k)   <-- this is > 1/n, correctly rising
    """
    if n_doors <= 1:
        return 1.0, 0.0
    n_remaining_others = n_doors - 1 - n_opened
    if n_remaining_others <= 0:
        return 1.0, 0.0
    unnorm_stay   = 1.0 / n_doors
    unnorm_switch = (1.0 / n_doors) * (n_doors - 1) / (n_doors - 1 - n_opened)
    total = unnorm_stay + n_remaining_others * unnorm_switch
    return unnorm_stay / total, unnorm_switch / total


def door_posteriors(n_doors, opened_doors, player_door):
    """Return dict {door: posterior_prob} for all doors."""
    n_opened = len(opened_doors)
    p_stay, p_switch = compute_posterior(n_doors, n_opened)
    result = {}
    for d in range(1, n_doors + 1):
        if d in opened_doors:
            result[d] = 0.0
        elif d == player_door:
            result[d] = p_stay
        else:
            result[d] = p_switch
    return result


# ── Session state ─────────────────────────────────────────────────────────────
def init_state():
    defaults = dict(
        phase="pick",        # pick | reveal | decide | outcome
        n_doors=3,
        n_opened_max=1,
        player_door=None,
        car_door=None,
        opened_doors=[],     # doors opened so far this round
        all_goat_doors=[],   # pre-computed pool host can open
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


def reset_round():
    S.phase        = "pick"
    S.player_door  = None
    S.car_door     = None
    S.opened_doors = []
    S.all_goat_doors = []
    S.final_door   = None
    S.won          = None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚪 Game Settings")
    st.markdown("---")

    n_doors  = st.slider("Total doors (N)", 3, 20, S.n_doors, key="sb_ndoors")
    max_open = n_doors - 2  # maximum doors host can ever open (always >= 1)

    # Only show the k-slider when there is actually a choice (i.e. N > 3)
    if max_open > 1:
        safe_max     = max(1, min(S.n_opened_max, max_open))
        n_opened_max = st.slider("Max doors host can open (k)", 1, max_open, safe_max, key="sb_nopened")
    else:
        # N=3 → only 1 door can ever be opened; skip slider to avoid range error
        n_opened_max = 1
        st.markdown(
            "<div style='font-family:JetBrains Mono;font-size:0.75rem;color:#6b6b80'>"
            "Doors host opens (k): <b style='color:#e8e4d9'>1</b> (fixed for N=3)</div>",
            unsafe_allow_html=True
        )

    S.n_opened_max = n_opened_max

    if n_doors != S.n_doors:
        S.n_doors = n_doors
        reset_round()

    S.n_doors = n_doors

    st.markdown("---")
    if st.button("🔄 Reset History", use_container_width=True):
        S.history   = []
        S.round_num = 0
        reset_round()

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
        "🟡 Your pick &nbsp; 🔴 Opened &nbsp; 🟢 Switch candidate<br>"
        "🏆 Car + your door &nbsp; 🚗 Car was here</div>",
        unsafe_allow_html=True
    )

n_doors      = S.n_doors
n_opened_max = S.n_opened_max


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

    # ── Phase banner ──────────────────────────────────────────────────────────
    n_currently_open  = len(S.opened_doors)
    can_open_more     = (S.phase == "reveal") and (n_currently_open < n_opened_max)
    remaining_goats   = [d for d in S.all_goat_doors if d not in S.opened_doors]

    phase_descs = {
        "pick":    ("01 / PICK A DOOR",
                    "Choose any door. The car is hidden randomly behind one of them."),
        "reveal":  ("02 / OPEN DOORS & WATCH PROBABILITIES",
                    f"{'Open another goat door to watch probabilities update, or make your final choice when ready.' if can_open_more else 'All doors opened — now make your final choice.'}"),
        "decide":  ("03 / MAKE YOUR FINAL CHOICE",
                    "Click any remaining door to lock in your answer."),
        "outcome": ("04 / OUTCOME", ""),
    }
    ph_title, ph_sub = phase_descs[S.phase]
    st.markdown(
        f"<div class='phase-banner'>"
        f"<div class='phase-step'>{ph_title}</div>"
        f"<p class='phase-desc'>{ph_sub}</p>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Compute current posteriors ────────────────────────────────────────────
    if S.player_door is not None:
        posteriors = door_posteriors(n_doors, S.opened_doors, S.player_door)
    else:
        posteriors = {d: 1 / n_doors for d in range(1, n_doors + 1)}

    # ── Door grid ─────────────────────────────────────────────────────────────
    doors  = list(range(1, n_doors + 1))
    COLS   = min(n_doors, 10)
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
            prob      = posteriors.get(d, 1 / n_doors)

            # Emoji
            if S.phase == "outcome":
                if is_opened:                emoji = "🐐"
                elif is_car and is_final:    emoji = "🏆"
                elif is_car:                 emoji = "🚗"
                elif is_final:               emoji = "😞"
                else:                        emoji = "🚪"
            elif is_opened:                  emoji = "🐐"
            elif is_player:                  emoji = "👆"
            else:                            emoji = "🚪"

            # Colour for labels
            if is_opened:                    clr = "#e05c5c"
            elif is_player:                  clr = "#f5a623"
            elif S.phase == "outcome" and is_car: clr = "#4ade80"
            else:                            clr = "#4ade80" if S.player_door else "#6b6b80"

            # Sub text
            if S.phase == "outcome":
                if is_opened:              sub = "goat"
                elif is_final and is_car:  sub = "WIN 🎉"
                elif is_final:             sub = "your choice"
                elif is_car:               sub = "car was here"
                else:                      sub = ""
            elif S.phase in ("reveal", "decide"):
                if is_opened:   sub = "goat"
                elif is_player: sub = "your pick"
                else:           sub = "switch?"
            else:
                sub = f"door {d}"

            # Probability label (shown once a door has been picked)
            if S.player_door is not None and S.phase != "outcome":
                if is_opened:
                    prob_text = "eliminated"
                    prob_clr  = "#3a3a4a"
                else:
                    prob_text = f"p = {prob:.3f}"
                    prob_clr  = clr
            elif S.phase == "outcome":
                prob_text = ""
                prob_clr  = clr
            else:
                prob_text = f"p = {prob:.3f}"
                prob_clr  = "#6b6b80"

            # Disable rules
            disabled = (
                is_opened
                or S.phase == "outcome"
                or S.phase == "pick" and False   # all clickable when picking
                or S.phase == "reveal"            # no door clicks during reveal phase
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
                    f"<div class='door-label' style='color:{clr}'>{sub}</div>"
                    f"<div class='prob-label' style='color:{prob_clr}'>{prob_text}</div>",
                    unsafe_allow_html=True
                )

            # Handle click
            if clicked:
                if S.phase == "pick":
                    S.player_door = d
                    S.car_door    = random.choice(doors)
                    # Pre-compute ALL goat doors the host could potentially open
                    if S.car_door == S.player_door:
                        eligible = [x for x in doors if x != S.player_door]
                    else:
                        eligible = [x for x in doors if x != S.player_door and x != S.car_door]
                    random.shuffle(eligible)
                    S.all_goat_doors = eligible      # host will draw from front of this list
                    S.opened_doors   = []
                    S.phase          = "reveal"
                    st.rerun()

                elif S.phase == "decide":
                    S.final_door = d
                    S.won        = (d == S.car_door)
                    action       = "stay" if d == S.player_door else "switch"
                    S.round_num += 1
                    S.history.append(dict(
                        round=S.round_num,
                        n_doors=n_doors,
                        n_opened=n_currently_open,
                        player_door=S.player_door,
                        car_door=S.car_door,
                        final_door=d,
                        action=action,
                        won=S.won,
                    ))
                    S.phase = "outcome"
                    st.rerun()

    # ── Action buttons (reveal phase) ─────────────────────────────────────────
    if S.phase == "reveal":
        st.markdown("<br>", unsafe_allow_html=True)
        btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 3])

        remaining_goats = [d for d in S.all_goat_doors if d not in S.opened_doors]
        can_open_more   = len(remaining_goats) > 0 and n_currently_open < n_opened_max

        with btn_col1:
            if can_open_more:
                if st.button("🚪 Open Another Door", type="primary", use_container_width=True):
                    # Reveal the next goat from the pre-shuffled list
                    S.opened_doors.append(remaining_goats[0])
                    st.rerun()
            else:
                st.button("🚪 Open Another Door", disabled=True, use_container_width=True)

        with btn_col2:
            if n_currently_open >= 1:
                if st.button("✅ Make My Final Choice", type="secondary", use_container_width=True):
                    S.phase = "decide"
                    st.rerun()
            else:
                st.button("✅ Make My Final Choice", disabled=True, use_container_width=True,
                          help="Open at least one door first")

        with btn_col3:
            opened_str = f"{n_currently_open} door{'s' if n_currently_open != 1 else ''} opened"
            max_str    = f"(max {n_opened_max})"
            st.markdown(
                f"<div style='font-family:JetBrains Mono;font-size:0.8rem;color:#6b6b80;"
                f"padding-top:0.6rem'>{opened_str} {max_str}</div>",
                unsafe_allow_html=True
            )

    # ── Live probability bar chart ────────────────────────────────────────────
    if S.phase in ("reveal", "decide") and S.player_door is not None:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Live Posterior Probabilities")

        all_d   = list(range(1, n_doors + 1))
        bar_clr = []
        bar_val = []
        bar_txt = []
        for d in all_d:
            p = posteriors[d]
            bar_val.append(p)
            bar_txt.append(f"{p:.3f}" if p > 0.0001 else "0")
            if d in S.opened_doors:  bar_clr.append("#2a1a1a")
            elif d == S.player_door: bar_clr.append("#f5a623")
            else:                    bar_clr.append("#4ade80")

        # Prior reference line
        p_prior = 1 / n_doors

        fig_live = go.Figure()
        fig_live.add_hline(
            y=p_prior, line_dash="dot", line_color="rgba(255,255,255,0.2)",
            annotation_text=f"prior 1/{n_doors} = {p_prior:.3f}",
            annotation_font_color="rgba(255,255,255,0.3)",
            annotation_position="right",
        )
        fig_live.add_trace(go.Bar(
            x=[f"D{d}" for d in all_d],
            y=bar_val,
            marker_color=bar_clr,
            marker_line_color="rgba(0,0,0,0.4)", marker_line_width=1,
            text=bar_txt,
            textposition="auto",
            textfont=dict(family="JetBrains Mono", size=12, color="#ffffff"),
            cliponaxis=False,
            insidetextanchor="middle",
            hovertemplate="%{x}<br>P = %{y:.4f}<extra></extra>",
        ))
        y_max = max(bar_val) if bar_val else 1.0
        fig_live.update_layout(
            plot_bgcolor="#16161f", paper_bgcolor="#16161f",
            font=dict(family="Syne", color="#c8c4b9"),
            showlegend=False,
            xaxis=dict(showgrid=False, zeroline=False,
                       tickfont=dict(family="JetBrains Mono", size=10)),
            yaxis=dict(showgrid=True, gridcolor="#1e1e2e", zeroline=False,
                       tickformat=".0%", tickfont=dict(family="JetBrains Mono", size=10),
                       range=[0, min(y_max * 1.25, 1.05)]),
            margin=dict(l=10, r=80, t=30, b=10), height=260,
        )
        st.plotly_chart(fig_live, use_container_width=True)

        # Live Bayesian insight
        p_st, p_sw = compute_posterior(n_doors, n_currently_open)
        n_rem      = n_doors - 1 - n_currently_open
        if p_st > 0 and n_rem > 0:
            lr_num = n_doors - 1
            lr_den = n_doors - 1 - n_currently_open
            st.markdown(
                f"<div class='insight-box'>"
                f"<b style='color:#f5a623'>📊 After {n_currently_open} door{'s' if n_currently_open != 1 else ''} opened</b><br>"
                f"Switch likelihood boost: <b>(N−1)/(N−1−k) = {lr_num}/{lr_den} = {lr_num/lr_den:.3f}</b><br>"
                f"Your door (D{S.player_door}): <b style='color:#f5a623'>p = {p_st:.4f}</b> &nbsp;·&nbsp; "
                f"Each of {n_rem} switch door{'s' if n_rem != 1 else ''}: "
                f"<b style='color:#4ade80'>p = {p_sw:.4f}</b> &nbsp;·&nbsp; "
                f"Total switch advantage: <b style='color:#c084fc'>{(n_rem * p_sw / p_st):.2f}×</b>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── Decide phase prompt ───────────────────────────────────────────────────
    if S.phase == "decide":
        st.info(f"👆 Click any door above to make your final choice. Your original pick was **Door {S.player_door}**.")

    # ── Outcome ───────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    if S.phase == "outcome":
        action_taken = S.history[-1]["action"]
        n_open_used  = S.history[-1]["n_opened"]

        if S.won:
            st.success(f"🏆 **You won!** You chose to **{action_taken}** — the car was behind door {S.final_door}.")
        else:
            st.error(f"😞 **You lost.** You chose to **{action_taken}** — the car was behind door {S.car_door}.")

        p_st, p_sw = compute_posterior(n_doors, n_open_used)
        n_rem = n_doors - 1 - n_open_used
        st.markdown(
            f"<div class='insight-box'>"
            f"<b style='color:#f5a623'>Bayesian odds at your decision</b> ({n_open_used} doors opened)<br>"
            f"P(car at your original door) = <b>{p_st:.4f}</b> &nbsp;·&nbsp; "
            f"P(car at each switch door) = <b>{p_sw:.4f}</b><br>"
            f"Switching gave a <b style='color:#4ade80'>{(n_rem * p_sw / p_st):.2f}× total advantage</b> "
            f"over staying at the moment you chose."
            f"</div>",
            unsafe_allow_html=True
        )

        if st.button("▶ Play Next Round", type="primary"):
            reset_round()
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
        mcard(c1, "Rounds",        len(S.history))
        mcard(c2, "Overall win %", f"{total_w / len(S.history):.0%}")
        mcard(c3, f"Stay  {stay_w}/{stay_t}",  f"{stay_w/stay_t:.0%}"  if stay_t else "—", "#f5a623")
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

            # Use most recent round's settings for theory lines
            last = S.history[-1]
            p_st_th, p_sw_th = compute_posterior(last["n_doors"], last["n_opened"])
            n_rem_th = last["n_doors"] - 1 - last["n_opened"]

            fig = go.Figure()
            fig.add_hline(y=p_st_th, line_dash="dot", line_color="rgba(245,166,35,0.3)",
                          annotation_text=f"theory stay {p_st_th:.1%}",
                          annotation_font_color="rgba(245,166,35,0.5)", annotation_position="right")
            fig.add_hline(y=n_rem_th * p_sw_th, line_dash="dot", line_color="rgba(74,222,128,0.3)",
                          annotation_text=f"theory switch {n_rem_th*p_sw_th:.1%}",
                          annotation_font_color="rgba(74,222,128,0.5)", annotation_position="right")
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

        # Round log
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
            f"<th>#</th><th>Game</th><th>First pick</th><th>Car</th>"
            f"<th>Action</th><th>Final</th><th>Result</th>"
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
        "Use the sliders to explore how posteriors shift as more doors are opened.</p>",
        unsafe_allow_html=True
    )

    t_n_doors  = st.slider("Total doors (N)",        3, 20, n_doors,      key="th_ndoors")
    t_max_open = t_n_doors - 2
    t_n_opened = st.slider("Doors opened (k)",       0, t_max_open, min(n_opened_max, t_max_open), key="th_nopened")

    p_prior   = 1 / t_n_doors
    p_st_th, p_sw_th = compute_posterior(t_n_doors, t_n_opened)
    n_rem_th  = t_n_doors - 1 - t_n_opened
    p_all_sw  = n_rem_th * p_sw_th

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
    mcard2(c4, "Switch advantage", f"{p_all_sw / p_st_th:.2f}×" if p_st_th > 0 else "—", "#c084fc")

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        st.markdown("#### Door-by-door probabilities")
        all_d2     = list(range(1, t_n_doors + 1))
        opened_set = set(range(2, 2 + t_n_opened))

        bpv, bpov, bclr = [], [], []
        for d in all_d2:
            bpv.append(p_prior)
            if d == 1:
                bpov.append(p_st_th); bclr.append("#f5a623")
            elif d in opened_set:
                bpov.append(0.0);     bclr.append("#e05c5c")
            else:
                bpov.append(p_sw_th); bclr.append("#4ade80")

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=[f"D{d}" for d in all_d2], y=bpv, name="Prior",
            marker_color="rgba(255,255,255,0.1)",
            marker_line_color="rgba(255,255,255,0.25)", marker_line_width=1,
        ))
        fig_bar.add_trace(go.Bar(
            x=[f"D{d}" for d in all_d2], y=bpov, name="Posterior",
            marker_color=bclr,
            marker_line_color="rgba(0,0,0,0.3)", marker_line_width=1,
            text=[f"{v:.1%}" if v > 0.001 else "0%" for v in bpov],
            textposition="outside",
            textfont=dict(family="JetBrains Mono", size=9, color="#c8c4b9"),
        ))
        fig_bar.update_layout(
            barmode="overlay", plot_bgcolor="#16161f", paper_bgcolor="#16161f",
            font=dict(family="Syne", color="#c8c4b9"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)",
                        font=dict(family="JetBrains Mono", size=11)),
            xaxis=dict(showgrid=False, zeroline=False,
                       tickfont=dict(family="JetBrains Mono", size=10)),
            yaxis=dict(showgrid=True, gridcolor="#1e1e2e", zeroline=False, tickformat=".0%",
                       tickfont=dict(family="JetBrains Mono", size=10)),
            margin=dict(l=10, r=10, t=40, b=10), height=320,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_r:
        st.markdown("#### Stay vs. Switch share")
        fig_donut = go.Figure(go.Pie(
            labels=["Stay (Door 1)", f"{n_rem_th} Switch door{'s' if n_rem_th > 1 else ''}", f"{t_n_opened} Opened"],
            values=[p_st_th, p_all_sw, t_n_opened / t_n_doors if t_n_opened > 0 else 0.0001],
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
                text=f"<b>{p_all_sw / p_st_th:.1f}×</b><br>switch edge" if p_st_th > 0 else "—",
                x=0.5, y=0.5, font=dict(size=16, family="Syne", color="#e8e4d9"), showarrow=False,
            )]
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Updating line chart
    st.markdown("#### Bayesian updating — probability vs. doors opened")
    steps = list(range(0, t_max_open + 1))
    ps_l, pw_l = [], []
    for k in steps:
        a, b = compute_posterior(t_n_doors, k)
        ps_l.append(a); pw_l.append(b)

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=steps, y=ps_l, mode="lines+markers", name="P(Stay)",
        line=dict(color="#f5a623", width=2.5),
        marker=dict(size=7, color="#f5a623", line=dict(color="#0d0d14", width=2)),
        hovertemplate="k=%{x}<br>P(stay): %{y:.4f}<extra></extra>",
    ))
    fig_line.add_trace(go.Scatter(
        x=steps, y=pw_l, mode="lines+markers", name="P(Switch) per door",
        line=dict(color="#4ade80", width=2.5, dash="dash"),
        marker=dict(size=7, color="#4ade80", line=dict(color="#0d0d14", width=2)),
        hovertemplate="k=%{x}<br>P(each switch): %{y:.4f}<extra></extra>",
    ))
    # Highlight current k
    fig_line.add_vline(x=t_n_opened, line_dash="dot", line_color="rgba(255,255,255,0.2)",
                       annotation_text=f" k={t_n_opened}", annotation_font_color="#6b6b80")
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

    if p_st_th > 0 and n_rem_th > 0:
        st.markdown(
            f"<div class='insight-box'>"
            f"<b style='color:#f5a623'>🔍 Bayesian Insight</b> &nbsp; N={t_n_doors}, k={t_n_opened}<br><br>"
            f"Prior: <b>1/{t_n_doors} = {p_prior:.4f}</b> per door. "
            f"After {t_n_opened} door{'s' if t_n_opened != 1 else ''} opened, "
            f"switch doors get a likelihood boost of <b>(N−1)/(N−1−k) = {t_n_doors-1}/{t_n_doors-1-t_n_opened} "
            f"= {(t_n_doors-1)/(t_n_doors-1-t_n_opened):.3f}</b> while the stay door is unchanged. "
            f"Stay door: <b>{p_st_th:.4f}</b> · each of {n_rem_th} switch doors: <b>{p_sw_th:.4f}</b>. "
            f"Total switch advantage: <b style='color:#4ade80'>{p_all_sw / p_st_th:.2f}×</b>."
            f"</div>",
            unsafe_allow_html=True
        )

    with st.expander("📐 Show the maths"):
        st.markdown(r"""
**Uniform prior:** $P(\text{car at door } d) = 1/N$ for all $d$.

**Likelihoods** — let $E$ = "host opens exactly these $k$ doors":

$$P(E \mid \text{car at player's door}) = 1$$
(host can freely pick any $k$ of the $N-1$ goat doors)

$$P(E \mid \text{car at a specific switch door } d^*) = \frac{N-1-k}{N-1}$$
(host must avoid $d^*$, so picks $k$ from the remaining $N-2$ goats)

Since $\frac{N-1-k}{N-1} < 1$, the host is **less likely** to have opened these specific doors if the car is at a switch door — meaning switch doors carry **more** posterior weight.

**Unnormalised posteriors:**

$$\tilde{p}_\text{stay} = \frac{1}{N} \cdot 1, \qquad \tilde{p}_\text{switch} = \frac{1}{N} \cdot \frac{N-1}{N-1-k}$$

**After normalisation:**

$$P(\text{stay wins}) = \frac{1}{N-k}, \qquad P(\text{each switch door wins}) = \frac{N-1}{(N-k)(N-1-k)}$$

**Total switching advantage** (all switch doors combined vs. staying):

$$\frac{(N-1-k) \cdot P(\text{switch per door})}{P(\text{stay})} = \frac{N-1}{N-1-k}$$

For the classic 3-door / 1-open case: stay = **1/3**, switch = **2/3** — exactly **2× better** to switch.
""")
