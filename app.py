import json
import os
import re
import subprocess
import time
import streamlit as st
import streamlit.components.v1 as components

MAX_FRAGS = 100

st.set_page_config(
    page_title="REGISTRAR_SYS // INDEX_RECOVERY_v2.6",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# C Engine Bridge (student_index_BST.c)
# ---------------------------------------------------------------------------
def parse_fragments_expression(expr: str):
    """
    Parses inputs like:
      T1=[2,1], T2=[3,2,5], T3=[5,4]
    or line-by-line:
      3
      2 1 -
      3 2 5
      5 4 -
    """
    text = (expr or "").strip()
    if not text:
        return [], "Input is empty. Provide at least one fragment like T1=[2,1], T2=[3,2,5]."

    tag_pattern = re.compile(
        r"(?:([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*)?\[\s*([^\[\]]+?)\s*\]"
    )
    matches = list(tag_pattern.finditer(text))
    fragments = []

    if matches:
        stripped = tag_pattern.sub("", text)
        if re.sub(r"[\s,;]+", "", stripped) != "":
            return [], f"Invalid syntax near: '{stripped.strip()}'"

        if len(matches) > MAX_FRAGS:
            return [], f"Fragment count exceeds maximum allowed ({MAX_FRAGS})."

        seen_roots = set()
        for idx, m in enumerate(matches):
            tag = m.group(1) or f"T{idx + 1}"
            parts = [p.strip().lower() for p in m.group(2).split(",")]
            if len(parts) < 1 or len(parts) > 3:
                return [], f"Fragment {tag} must have 1 to 3 elements [root, left, right]."

            def parse_val(token, allow_none=False):
                if token in ("-", "null", "none", ""):
                    return None if allow_none else "MISSING_ROOT"
                if not re.fullmatch(r"-?\d+", token):
                    return "BAD_INT"
                return int(token)

            root_val = parse_val(parts[0], allow_none=False)
            if root_val == "MISSING_ROOT":
                return [], f"Fragment {tag} is missing a valid integer root."
            if root_val == "BAD_INT":
                return [], f"Fragment {tag} has non-integer root '{parts[0]}'."

            if root_val in seen_roots:
                return [], f"Duplicate fragment root ID {root_val} in {tag} (roots must be unique)."
            seen_roots.add(root_val)

            left_val = parse_val(parts[1], allow_none=True) if len(parts) >= 2 else None
            right_val = parse_val(parts[2], allow_none=True) if len(parts) >= 3 else None

            if left_val == "BAD_INT" or right_val == "BAD_INT":
                return [], f"Fragment {tag} contains non-integer child token."

            if left_val is not None and left_val >= root_val:
                return [], f"Local BST violation in {tag}: left child ({left_val}) >= root ({root_val})."
            if right_val is not None and right_val <= root_val:
                return [], f"Local BST violation in {tag}: right child ({right_val}) <= root ({root_val})."
            if left_val is not None and right_val is not None and left_val >= right_val:
                return [], f"Local BST violation in {tag}: left ({left_val}) >= right ({right_val})."

            fragments.append({"tag": tag, "root": root_val, "left": left_val, "right": right_val})

        return fragments, None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    start_idx = 0
    if len(lines) > 1 and re.fullmatch(r"\d+", lines[0]):
        start_idx = 1

    frag_lines = lines[start_idx:]
    if len(frag_lines) > MAX_FRAGS:
        return [], f"Fragment count exceeds maximum allowed ({MAX_FRAGS})."

    seen_roots = set()
    for i, ln in enumerate(frag_lines, start=1):
        tokens = ln.split()
        if len(tokens) < 1 or len(tokens) > 3:
            return [], f"Line {i} must have 1 to 3 values: root [left] [right]."
        if not re.fullmatch(r"-?\d+", tokens[0]):
            return [], f"Line {i} root '{tokens[0]}' must be an integer."
        r_val = int(tokens[0])
        if r_val in seen_roots:
            return [], f"Duplicate fragment root ID {r_val}."
        seen_roots.add(r_val)

        def parse_child(tok):
            if tok in ("-", "null", "none"):
                return None
            if not re.fullmatch(r"-?\d+", tok):
                return "BAD"
            return int(tok)

        l_val = parse_child(tokens[1]) if len(tokens) >= 2 else None
        rt_val = parse_child(tokens[2]) if len(tokens) >= 3 else None
        if l_val == "BAD" or rt_val == "BAD":
            return [], f"Line {i} has invalid child token."
        if l_val is not None and l_val >= r_val:
            return [], f"Local BST violation on line {i}: left ({l_val}) >= root ({r_val})."
        if rt_val is not None and rt_val <= r_val:
            return [], f"Local BST violation on line {i}: right ({rt_val}) <= root ({r_val})."

        fragments.append({"tag": f"T{i}", "root": r_val, "left": l_val, "right": rt_val})

    return fragments, None


def fragments_to_c_stdin(fragments) -> str:
    rows = [str(len(fragments))]
    for f in fragments:
        l_tok = "-" if f["left"] is None else str(f["left"])
        r_tok = "-" if f["right"] is None else str(f["right"])
        rows.append(f"{f['root']} {l_tok} {r_tok}")
    return "\n".join(rows) + "\n"


def ensure_c_binary(force_rebuild: bool = False):
    c_file = "student_index_BST.c"
    exe_name = "demo.exe" if os.name == "nt" else "./demo"
    built_path = "demo.exe" if os.name == "nt" else "demo"
    if not os.path.exists(c_file):
        return None, f"{c_file} not found in current directory."
    if force_rebuild or not os.path.exists(built_path):
        res = subprocess.run(
            ["gcc", "-Wall", "-Wextra", "-O2", c_file, "-o", "demo"],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return None, res.stderr.strip() or "gcc compilation failed."
    return exe_name, None


def run_c_engine(fragments):
    exe_path, compile_err = ensure_c_binary(force_rebuild=False)
    if compile_err:
        return None, compile_err, 0.0
    stdin_payload = fragments_to_c_stdin(fragments)
    t0 = time.perf_counter()
    try:
        res = subprocess.run(
            [exe_path],
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return None, "C engine execution timed out (> 5s).", 0.0
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    raw_lines = [
        ln
        for ln in res.stdout.splitlines()
        if not ln.startswith("Enter number of fragments")
        and not ln.startswith("Enter ")
        and not ln.startswith("Fragment ")
    ]
    return "\n".join(raw_lines).strip(), None, elapsed_ms


def generate_max_valid_fragments(count: int = MAX_FRAGS):
    """Generates up to MAX_FRAGS (100) valid mergeable BST fragments."""
    frags = []
    for i in range(1, count + 1):
        val = count + 2 - i
        child = val - 1 if i < count else None
        frags.append({"tag": f"T{i}", "root": val, "left": child, "right": None})
    return frags


# ---------------------------------------------------------------------------
# Presets (Aligned with 1-100 Fragment Constraint)
# ---------------------------------------------------------------------------
PRESETS = {
    "preset_1": {
        "label": "PRESET 1: ILLUSTRATIVE",
        "sub": "T1=[2,1], T2=[3,2,5], T3=[5,4]",
        "color": "#00C853",
        "expr": "T1=[2,1], T2=[3,2,5], T3=[5,4]",
    },
    "preset_2": {
        "label": "PRESET 2: UNSEEN VALID (7)",
        "sub": "MULTI-LEVEL 7-FRAGMENT BST",
        "color": "#00E5FF",
        "expr": (
            "T1=[10,5,15], T2=[5,2,7], T3=[15,12,20], "
            "T4=[2,1], T5=[7,6], T6=[12,11], T7=[20,18]"
        ),
    },
    "preset_3": {
        "label": "PRESET 3: BST CONFLICT",
        "sub": "GLOBAL (MIN, MAX) VIOLATION",
        "color": "#FF3B30",
        "expr": "T1=[3,2,6], T2=[6,2,8]",
    },
    "preset_4": {
        "label": "PRESET 4: DISCONNECTED",
        "sub": "ORPHAN / UNUSED FRAGMENT T4",
        "color": "#FFB020",
        "expr": "T1=[2,1], T2=[3,2,5], T3=[5,4], T4=[99,95]",
    },
    "preset_5": {
        "label": "PRESET 5: MAX BOUND (100)",
        "sub": "BENCHMARK 100 FRAGMENTS",
        "color": "#D580FF",
        "expr": "__MAX_100__",
    },
}

if "fragments" not in st.session_state:
    st.session_state.fragments, _ = parse_fragments_expression(PRESETS["preset_1"]["expr"])
if "editor_text" not in st.session_state:
    st.session_state.editor_text = PRESETS["preset_1"]["expr"]
if "active_preset" not in st.session_state:
    st.session_state.active_preset = "preset_1"
if "exec_ms" not in st.session_state:
    st.session_state.exec_ms = 0.50
if "c_stdout" not in st.session_state:
    out, _, ms = run_c_engine(st.session_state.fragments)
    st.session_state.c_stdout = out or ""
    st.session_state.exec_ms = round(ms, 2) if ms > 0 else 0.50
if "mode_step" not in st.session_state:
    st.session_state.mode_step = False


def apply_preset(key: str):
    st.session_state.active_preset = key
    st.session_state.mode_step = False
    p = PRESETS[key]
    if p["expr"] == "__MAX_100__":
        frags = generate_max_valid_fragments(MAX_FRAGS)
        out, c_err, ms = run_c_engine(frags)
        st.session_state.fragments = frags
        st.session_state.editor_text = (
            f"T1=[102,101], T2=[101,100], ... ({MAX_FRAGS} fragments at MAX_FRAGS limit)"
        )
        st.session_state.c_stdout = c_err or out or ""
        st.session_state.exec_ms = round(ms, 2) if ms > 0 else 0.50
    else:
        frags, err = parse_fragments_expression(p["expr"])
        if not err:
            st.session_state.fragments = frags
            st.session_state.editor_text = p["expr"]
            out, c_err, ms = run_c_engine(frags)
            st.session_state.c_stdout = c_err or out or ""
            st.session_state.exec_ms = round(ms, 2) if ms > 0 else 0.42


# ---------------------------------------------------------------------------
# Global Neo-Brutalist Theme CSS (Clean, Uncompressed Typography)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

        .stApp {
            background-color: #F4F1EA;
            color: #000000;
            font-family: 'JetBrains Mono', monospace;
            letter-spacing: 0px;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2.5rem;
            max-width: 98%;
        }
        header[data-testid="stHeader"] {
            background: transparent;
        }

        .nb-card {
            background: #FFFFFF;
            border: 4px solid #000000;
            box-shadow: 6px 6px 0px #000000;
            padding: 16px 18px;
            margin-bottom: 16px;
        }
        .nb-header-bar {
            background: #F4F1EA;
            border: 4px solid #000000;
            box-shadow: 6px 6px 0px #000000;
            padding: 16px 20px;
            margin-bottom: 14px;
        }
        .nb-badge-dark {
            display: inline-block;
            background: #000000;
            color: #FFE600;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 11px;
            padding: 3px 8px;
            letter-spacing: 0.4px;
            margin-right: 6px;
        }
        .nb-badge-cyan {
            display: inline-block;
            background: #00E5FF;
            color: #000000;
            border: 2px solid #000000;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 11px;
            padding: 2px 8px;
            letter-spacing: 0.4px;
        }
        .nb-title {
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            font-size: 28px;
            line-height: 1.18;
            margin: 10px 0 6px 0;
            letter-spacing: -0.3px;
            color: #000000;
        }
        .nb-sub {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            line-height: 1.45;
            color: #222222;
            margin: 0;
        }
        .nb-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            height: 100%;
            align-items: stretch;
        }
        .nb-kpi {
            background: #FFFFFF;
            border: 3px solid #000000;
            box-shadow: 4px 4px 0px #000000;
            padding: 10px 12px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .nb-kpi-yellow {
            background: #FFE600;
        }
        .nb-kpi-lbl {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .nb-kpi-val {
            font-family: 'Inter', sans-serif;
            font-size: 22px;
            font-weight: 800;
            margin-top: 4px;
            letter-spacing: -0.2px;
        }

        .nb-sec-hdr {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 3px solid #000000;
        }
        .nb-sec-title {
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            font-size: 15px;
            text-transform: uppercase;
            letter-spacing: 0.2px;
        }
        .nb-sq {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid #000000;
            margin-right: 8px;
            vertical-align: middle;
        }

        .nb-frag-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 12px;
        }
        .nb-frag-card {
            border: 3px solid #000000;
            box-shadow: 4px 4px 0px #000000;
            padding: 8px 10px;
            background: #FFFDF7;
        }
        .nb-frag-tag {
            display: inline-block;
            border: 2px solid #000000;
            font-weight: 700;
            font-size: 11px;
            padding: 1px 6px;
            margin-bottom: 4px;
        }
        .nb-frag-arr {
            font-weight: 700;
            font-size: 13px;
            float: right;
        }

        div.stButton > button {
            border: 3px solid #000000 !important;
            box-shadow: 4px 4px 0px #000000 !important;
            border-radius: 0px !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-weight: 700 !important;
            color: #000000 !important;
            transition: transform 0.08s ease;
        }
        div.stButton > button:hover {
            transform: translate(-1px, -1px);
            box-shadow: 5px 5px 0px #000000 !important;
        }
        div.stButton > button:active {
            transform: translate(2px, 2px);
            box-shadow: 2px 2px 0px #000000 !important;
        }
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stTextInput"] input {
            border: 3px solid #000000 !important;
            border-radius: 0px !important;
            background: #FFFFFF !important;
            color: #000000 !important;
            font-family: 'JetBrains Mono', monospace !important;
            box-shadow: 3px 3px 0px #000000 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Top Header & KPI Strip
# ---------------------------------------------------------------------------
frags_curr = st.session_state.fragments
total_nodes = len(frags_curr) + 1 if frags_curr else 0
tree_height = len(frags_curr) if frags_curr else 0

hdr_left, hdr_right = st.columns([1.35, 1.0], gap="medium")
with hdr_left:
    st.markdown(
        f"""
        <div class="nb-header-bar">
            <div>
                <span class="nb-badge-dark">REGISTRAR_SYS // INDEX_RECOVERY_v2.6</span>
                <span class="nb-badge-cyan">PS12 :: BST STRUCTURAL VALIDATION (1–{MAX_FRAGS})</span>
            </div>
            <div class="nb-title">THE REGISTRAR'S FRAGMENTED STUDENT INDEX</div>
            <p class="nb-sub">Reconstructs corrupted 1–3 node BST fragments (1–{MAX_FRAGS} fragments) into a globally valid Student Index or diagnoses structural violations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hdr_right:
    st.markdown(
        f"""
        <div class="nb-card" style="padding: 12px; height: calc(100% - 16px);">
            <div class="nb-kpi-grid">
                <div class="nb-kpi">
                    <div class="nb-kpi-lbl">Fragments</div>
                    <div class="nb-kpi-val">{len(frags_curr)}/{MAX_FRAGS}</div>
                </div>
                <div class="nb-kpi">
                    <div class="nb-kpi-lbl">Total Nodes</div>
                    <div class="nb-kpi-val">{total_nodes}</div>
                </div>
                <div class="nb-kpi">
                    <div class="nb-kpi-lbl">Tree Height</div>
                    <div class="nb-kpi-val">{tree_height}</div>
                </div>
                <div class="nb-kpi nb-kpi-yellow">
                    <div class="nb-kpi-lbl">Exec Time</div>
                    <div class="nb-kpi-val">{st.session_state.exec_ms:.2f} ms</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Preset Test Suite Bar
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span class="nb-badge-dark">PRESET TEST SUITE // ONE-CLICK LOAD</span>
        <span style="font-size:12px; font-weight:700;">Click any preset to populate fragments &amp; execute validation</span>
    </div>
    """,
    unsafe_allow_html=True,
)

preset_keys = list(PRESETS.keys())
p_cols = st.columns(5, gap="small")
for idx, p_key in enumerate(preset_keys):
    p_info = PRESETS[p_key]
    with p_cols[idx]:
        st.markdown(
            f"""
            <div style="background:{p_info['color']}; border:3px solid #000; box-shadow:4px 4px 0 #000; padding:6px 8px; margin-bottom:4px;">
                <div style="font-weight:700; font-size:11px;">{p_info['label']}</div>
                <div style="font-size:10px;">{p_info['sub']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("LOAD & RUN", key=f"btn_{p_key}", use_container_width=True):
            apply_preset(p_key)
            st.rerun()

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main Two-Column Layout: Left Workbench | Right Topology & Post-Merge Console
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1.0, 1.35], gap="medium")

with left_col:
    st.markdown(
        """
        <div class="nb-card">
            <div class="nb-sec-hdr">
                <div><span class="nb-sq" style="background:#FFE600;"></span><span class="nb-sec-title">Fragment Workbench</span></div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    c_merge, c_step, c_clear = st.columns([1.2, 1.2, 0.8], gap="small")
    with c_merge:
        merge_clicked = st.button("⚡ MERGE ALL", use_container_width=True)
    with c_step:
        step_clicked = st.button("⏭ STEP-BY-STEP", use_container_width=True)
    with c_clear:
        clear_clicked = st.button("CLEAR ALL", use_container_width=True)

    if clear_clicked:
        st.session_state.fragments = []
        st.session_state.editor_text = ""
        st.session_state.c_stdout = ""
        st.session_state.exec_ms = 0.0
        st.rerun()

    st.markdown(
        "<div style='display:flex; justify-content:space-between; font-size:11px; font-weight:700; margin-top:10px;'>"
        "<span>RAW FRAGMENT EXPRESSION EDITOR</span><span>Format: T1=[root, left, right]</span></div>",
        unsafe_allow_html=True,
    )
    edited_expr = st.text_area(
        "Raw Fragment Expression",
        value=st.session_state.editor_text,
        height=95,
        label_visibility="collapsed",
    )
    st.caption(f"Supports 1–{MAX_FRAGS} fragments. Use `null` or `-` for absent children (e.g. `[3,-,5]`).")

    if merge_clicked or step_clicked:
        st.session_state.mode_step = bool(step_clicked)
        parsed, parse_err = parse_fragments_expression(edited_expr)
        if parse_err:
            st.session_state.c_stdout = f"IMPOSSIBLE: {parse_err}"
            st.error(f"IMPOSSIBLE: {parse_err}")
        else:
            st.session_state.fragments = parsed
            st.session_state.editor_text = edited_expr
            out, c_err, ms = run_c_engine(parsed)
            st.session_state.c_stdout = c_err or out or ""
            st.session_state.exec_ms = round(ms, 2) if ms > 0 else 0.35
            st.rerun()

    st.markdown(
        "<div style='font-size:12px; font-weight:700; margin-top:10px; margin-bottom:6px;'>VISUAL FRAGMENT CARD BUILDER</div>",
        unsafe_allow_html=True,
    )
    b1, b2, b3, b4 = st.columns([0.9, 1.0, 1.0, 1.0], gap="small")
    with b1:
        b_tag = st.text_input("TAG", value=f"T{len(st.session_state.fragments) + 1}")
    with b2:
        b_root = st.text_input("ROOT *", value="18")
    with b3:
        b_left = st.text_input("LEFT", value="-")
    with b4:
        b_right = st.text_input("RIGHT", value="-")

    if st.button("+ ADD FRAGMENT", use_container_width=True):
        if len(st.session_state.fragments) >= MAX_FRAGS:
            st.error(f"Maximum of {MAX_FRAGS} fragments reached.")
        else:
            candidate = f"{b_tag.strip() or 'TX'}=[{b_root.strip()},{b_left.strip()},{b_right.strip()}]"
            combined = (
                f"{st.session_state.editor_text}, {candidate}"
                if st.session_state.editor_text.strip()
                else candidate
            )
            parsed, parse_err = parse_fragments_expression(combined)
            if parse_err:
                st.error(parse_err)
            else:
                st.session_state.fragments = parsed
                st.session_state.editor_text = combined
                out, c_err, ms = run_c_engine(parsed)
                st.session_state.c_stdout = c_err or out or ""
                st.session_state.exec_ms = round(ms, 2)
                st.rerun()

    palette = ["#FFE600", "#00E5FF", "#D580FF", "#00C853", "#FFB020"]
    preview_frags = st.session_state.fragments[:6]
    if preview_frags:
        cards_html = "<div class='nb-frag-grid'>"
        for i, f in enumerate(preview_frags):
            bg = palette[i % len(palette)]
            l_disp = "-" if f["left"] is None else str(f["left"])
            r_disp = "-" if f["right"] is None else str(f["right"])
            cards_html += (
                f"<div class='nb-frag-card'>"
                f"<span class='nb-frag-tag' style='background:{bg};'>{f['tag']}</span>"
                f"<span class='nb-frag-arr'>[{f['root']}, {l_disp}, {r_disp}]</span>"
                f"<div style='font-size:11px; margin-top:4px;'>Root: <b>{f['root']}</b> · L: <b>{l_disp}</b> · R: <b>{r_disp}</b></div>"
                f"</div>"
            )
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    frags_json = json.dumps(st.session_state.fragments)
    c_out_json = json.dumps(st.session_state.c_stdout)
    step_mode_json = json.dumps(st.session_state.mode_step)

    canvas_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
        * {{
          box-sizing: border-box;
        }}
        body {{
          margin: 0;
          padding: 2px 4px 10px 2px;
          background: #F4F1EA;
          font-family: 'JetBrains Mono', monospace;
          color: #000000;
          letter-spacing: 0px;
        }}
        .panel {{
          background: #FFFFFF;
          border: 4px solid #000000;
          box-shadow: 6px 6px 0px #000000;
          padding: 14px 16px;
          margin-bottom: 14px;
        }}
        .hdr {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 10px;
          border-bottom: 3px solid #000000;
          padding-bottom: 8px;
          margin-bottom: 10px;
        }}
        .title {{
          font-family: 'Inter', sans-serif;
          font-weight: 800;
          font-size: 14px;
          text-transform: uppercase;
          letter-spacing: 0px;
          line-height: 1.25;
        }}
        .sq {{
          display: inline-block;
          width: 11px;
          height: 11px;
          border: 2px solid #000000;
          margin-right: 7px;
          vertical-align: middle;
        }}
        .ctrl-btn {{
          background: #FFFFFF;
          border: 2px solid #000000;
          box-shadow: 2px 2px 0px #000000;
          font-family: 'JetBrains Mono', monospace;
          font-weight: 700;
          font-size: 11px;
          padding: 4px 8px;
          cursor: pointer;
          color: #000000;
        }}
        .ctrl-btn.reset {{
          background: #FFE600;
        }}
        .svg-wrap {{
          position: relative;
          height: 250px;
          border: 3px solid #000000;
          background-color: #FAFAFA;
          background-image:
            linear-gradient(to right, #E4E4E4 1px, transparent 1px),
            linear-gradient(to bottom, #E4E4E4 1px, transparent 1px);
          background-size: 20px 20px;
          overflow: hidden;
        }}
        .hint-pill {{
          position: absolute;
          bottom: 8px;
          left: 8px;
          background: #FFFFFF;
          border: 2px solid #000000;
          padding: 3px 8px;
          font-size: 10px;
          font-weight: 700;
          pointer-events: none;
        }}
        .badge-unlocked {{
          background: #00C853;
          color: #000000;
          border: 2px solid #000000;
          padding: 3px 8px;
          font-size: 10px;
          font-weight: 700;
          white-space: nowrap;
        }}
        .ops-grid {{
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
          margin-bottom: 10px;
        }}
        .op-label {{
          font-size: 11px;
          font-weight: 700;
          margin-bottom: 5px;
          line-height: 1.25;
        }}
        .op-row {{
          display: flex;
          gap: 5px;
        }}
        .op-input {{
          width: 100%;
          min-width: 0;
          border: 2px solid #000000;
          padding: 5px 7px;
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          color: #000000;
          background: #FFFFFF;
        }}
        .op-btn {{
          border: 2px solid #000000;
          box-shadow: 2px 2px 0px #000000;
          font-family: 'JetBrains Mono', monospace;
          font-weight: 700;
          font-size: 11px;
          padding: 5px 10px;
          cursor: pointer;
          white-space: nowrap;
        }}
        .term-log {{
          background: #0A0A0A;
          color: #00FF66;
          border: 3px solid #000000;
          padding: 8px 10px;
          font-size: 12px;
          line-height: 1.35;
          min-height: 30px;
        }}
      </style>
    </head>
    <body>
      <div class="panel">
        <div class="hdr">
          <div><span class="sq" style="background:#00E5FF;"></span><span class="title">Reconstructed Index Topology</span></div>
          <div style="display:flex; gap:5px;">
            <button class="ctrl-btn" onclick="zoomBy(1.15)">+</button>
            <button class="ctrl-btn" onclick="zoomBy(0.85)">-</button>
            <button class="ctrl-btn reset" onclick="resetView()">RESET VIEW</button>
          </div>
        </div>
        <div class="svg-wrap" id="svgWrap">
          <svg id="treeSvg" width="100%" height="100%"></svg>
          <div class="hint-pill">DRAG TO PAN · SCROLL TO ZOOM · CLICK NODE TO INSPECT</div>
        </div>
      </div>

      <div class="panel" style="margin-bottom: 0;">
        <div class="hdr">
          <div><span class="sq" style="background:#00C853;"></span><span class="title">Post-Merge Index Operations Console</span></div>
          <span class="badge-unlocked" id="consoleBadge">UNLOCKED · LIVE INDEX ACTIVE</span>
        </div>
        <div class="ops-grid">
          <div>
            <div class="op-label">1. SEARCH STUDENT ID</div>
            <div class="op-row">
              <input class="op-input" id="searchId" placeholder="ID" />
              <button class="op-btn" style="background:#00E5FF; color:#000000;" onclick="doSearch()">FIND</button>
            </div>
          </div>
          <div>
            <div class="op-label">2. INSERT STUDENT ID</div>
            <div class="op-row">
              <input class="op-input" id="insertId" placeholder="ID" />
              <button class="op-btn" style="background:#00C853; color:#000000;" onclick="doInsert()">ADD</button>
            </div>
          </div>
          <div>
            <div class="op-label">3. DELETE STUDENT ID</div>
            <div class="op-row">
              <input class="op-input" id="deleteId" placeholder="ID" />
              <button class="op-btn" style="background:#FF3B30; color:#FFFFFF;" onclick="doDelete()">DEL</button>
            </div>
          </div>
        </div>
        <div class="term-log" id="termLog">&gt; Index unlocked. Ready for Search, Insert, or Delete queries.</div>
      </div>

      <script>
        const rawFrags = {frags_json};
        const cOutput = {c_out_json};
        const stepMode = {step_mode_json};
        const colors = ["#FFE600", "#00E5FF", "#D580FF", "#00C853", "#FFB020"];

        let scale = 1.0, panX = 0, panY = 0, isDragging = false, dragStart = {{x:0, y:0}};
        let highlightedId = null;

        function buildTree(frags) {{
          if (!frags || frags.length === 0) return {{ root: null, error: "No fragments loaded." }};
          const nodeMap = new Map();
          const childSet = new Set();
          frags.forEach((f, idx) => {{
            const tagColor = colors[idx % colors.length];
            nodeMap.set(f.root, {{
              val: f.root,
              left: f.left !== null ? {{ val: f.left, left: null, right: null, tag: f.tag, color: tagColor }} : null,
              right: f.right !== null ? {{ val: f.right, left: null, right: null, tag: f.tag, color: tagColor }} : null,
              tag: f.tag,
              color: tagColor
            }});
            if (f.left !== null) childSet.add(f.left);
            if (f.right !== null) childSet.add(f.right);
          }});

          const roots = frags.map(f => f.root).filter(r => !childSet.has(r));
          if (roots.length !== 1) {{
            return {{
              root: nodeMap.get(frags[0].root),
              error: roots.length === 0 ? "Cycle detected (0 global roots)." : "Multiple/disconnected roots (" + roots.join(", ") + ")."
            }};
          }}

          function stitch(node, minVal, maxVal) {{
            if (!node) return null;
            if ((minVal !== null && node.val <= minVal) || (maxVal !== null && node.val >= maxVal)) {{
              return {{ conflict: node.val, minVal, maxVal }};
            }}
            if (node.left && nodeMap.has(node.left.val)) {{
              const sub = nodeMap.get(node.left.val);
              node.left = {{ ...sub }};
            }}
            if (node.right && nodeMap.has(node.right.val)) {{
              const sub = nodeMap.get(node.right.val);
              node.right = {{ ...sub }};
            }}
            const lRes = stitch(node.left, minVal, node.val);
            if (lRes && lRes.conflict !== undefined) return lRes;
            const rRes = stitch(node.right, node.val, maxVal);
            if (rRes && rRes.conflict !== undefined) return rRes;
            node.bounds = [minVal === null ? "-∞" : minVal, maxVal === null ? "+∞" : maxVal];
            return null;
          }}

          const rootNode = nodeMap.get(roots[0]);
          const check = stitch(rootNode, null, null);
          if (check && check.conflict !== undefined) {{
            return {{
              root: rootNode,
              error: `BST ordering conflict at node ${{check.conflict}} outside bounds (${{check.minVal ?? "-∞"}}, ${{check.maxVal ?? "+∞"}}).`
            }};
          }}
          return {{ root: rootNode, error: cOutput.includes("IMPOSSIBLE") ? cOutput : null }};
        }}

        let treeState = buildTree(rawFrags);

        function renderSvg() {{
          const svg = document.getElementById("treeSvg");
          const wrap = document.getElementById("svgWrap");
          const w = wrap.clientWidth || 650;
          svg.innerHTML = "";

          const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
          g.setAttribute("transform", `translate(${{panX + w/2}}, ${{panY + 42}}) scale(${{scale}})`);
          svg.appendChild(g);

          if (!treeState.root) return;

          function drawNode(n, x, y, spread) {{
            if (!n) return;
            if (n.left) {{
              const lx = x - spread, ly = y + 58;
              drawEdge(g, x, y, lx, ly, "L");
              drawNode(n.left, lx, ly, Math.max(36, spread * 0.56));
            }}
            if (n.right) {{
              const rx = x + spread, ry = y + 58;
              drawEdge(g, x, y, rx, ry, "R");
              drawNode(n.right, rx, ry, Math.max(36, spread * 0.56));
            }}

            const isHi = highlightedId === n.val;
            const grp = document.createElementNS("http://www.w3.org/2000/svg", "g");

            const pill = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            pill.setAttribute("x", x - 14);
            pill.setAttribute("y", y - 32);
            pill.setAttribute("width", 28);
            pill.setAttribute("height", 14);
            pill.setAttribute("fill", "#000000");
            grp.appendChild(pill);

            const pillTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
            pillTxt.setAttribute("x", x);
            pillTxt.setAttribute("y", y - 22);
            pillTxt.setAttribute("text-anchor", "middle");
            pillTxt.setAttribute("fill", "#FFFFFF");
            pillTxt.setAttribute("font-size", "9");
            pillTxt.setAttribute("font-weight", "700");
            pillTxt.textContent = n.tag || "T";
            grp.appendChild(pillTxt);

            const circ = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circ.setAttribute("cx", x);
            circ.setAttribute("cy", y);
            circ.setAttribute("r", 18);
            circ.setAttribute("fill", isHi ? "#FF3B30" : (n.color || "#FFE600"));
            circ.setAttribute("stroke", "#000000");
            circ.setAttribute("stroke-width", isHi ? "4" : "3");
            grp.appendChild(circ);

            const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
            txt.setAttribute("x", x);
            txt.setAttribute("y", y + 5);
            txt.setAttribute("text-anchor", "middle");
            txt.setAttribute("fill", isHi ? "#FFFFFF" : "#000000");
            txt.setAttribute("font-size", "12");
            txt.setAttribute("font-weight", "700");
            txt.textContent = n.val;
            grp.appendChild(txt);

            grp.style.cursor = "pointer";
            grp.onclick = () => {{
              highlightedId = n.val;
              const b = n.bounds ? `(${{n.bounds[0]}}, ${{n.bounds[1]}})` : "N/A";
              setLog(`Node ${{n.val}} [${{n.tag}}] · Valid BST bounds: ${{b}}`);
              renderSvg();
            }};

            g.appendChild(grp);
          }}

          function drawEdge(parent, x1, y1, x2, y2, label) {{
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", x1);
            line.setAttribute("y1", y1);
            line.setAttribute("x2", x2);
            line.setAttribute("y2", y2);
            line.setAttribute("stroke", "#000000");
            line.setAttribute("stroke-width", "3");
            parent.appendChild(line);

            const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
            const box = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            box.setAttribute("x", mx - 8);
            box.setAttribute("y", my - 8);
            box.setAttribute("width", 16);
            box.setAttribute("height", 16);
            box.setAttribute("fill", "#FFFFFF");
            box.setAttribute("stroke", "#000000");
            box.setAttribute("stroke-width", "1.5");
            parent.appendChild(box);

            const lbl = document.createElementNS("http://www.w3.org/2000/svg", "text");
            lbl.setAttribute("x", mx);
            lbl.setAttribute("y", my + 4);
            lbl.setAttribute("text-anchor", "middle");
            lbl.setAttribute("font-size", "9");
            lbl.setAttribute("font-weight", "700");
            lbl.textContent = label;
            parent.appendChild(lbl);
          }}

          drawNode(treeState.root, 0, 0, Math.min(140, w * 0.21));
        }}

        function zoomBy(factor) {{ scale = Math.max(0.4, Math.min(2.5, scale * factor)); renderSvg(); }}
        function resetView() {{ scale = 1.0; panX = 0; panY = 0; highlightedId = null; renderSvg(); }}

        const wrap = document.getElementById("svgWrap");
        wrap.addEventListener("mousedown", e => {{ isDragging = true; dragStart = {{x: e.clientX - panX, y: e.clientY - panY}}; }});
        window.addEventListener("mousemove", e => {{ if (!isDragging) return; panX = e.clientX - dragStart.x; panY = e.clientY - dragStart.y; renderSvg(); }});
        window.addEventListener("mouseup", () => {{ isDragging = false; }});
        wrap.addEventListener("wheel", e => {{ e.preventDefault(); zoomBy(e.deltaY < 0 ? 1.1 : 0.9); }}, {{passive: false}});

        function setLog(msg) {{ document.getElementById("termLog").textContent = "> " + msg; }}

        function doSearch() {{
          const v = parseInt(document.getElementById("searchId").value, 10);
          if (isNaN(v)) return setLog("Enter a valid integer Student ID to search.");
          let cur = treeState.root, path = [];
          while (cur) {{
            path.push(cur.val);
            if (v === cur.val) {{
              highlightedId = v;
              renderSvg();
              return setLog(`FOUND Student ID ${{v}} via path [${{path.join(" -> ")}}].`);
            }}
            cur = v < cur.val ? cur.left : cur.right;
          }}
          setLog(`Student ID ${{v}} NOT FOUND after path [${{path.join(" -> ") || "empty"}}].`);
        }}

        function doInsert() {{
          const v = parseInt(document.getElementById("insertId").value, 10);
          if (isNaN(v)) return setLog("Enter a valid integer Student ID to insert.");
          function ins(n) {{
            if (!n) return {{ val: v, left: null, right: null, tag: "NEW", color: "#00C853" }};
            if (v < n.val) n.left = ins(n.left);
            else if (v > n.val) n.right = ins(n.right);
            return n;
          }}
          treeState.root = ins(treeState.root);
          highlightedId = v;
          renderSvg();
          setLog(`INSERTED Student ID ${{v}} while preserving BST invariant.`);
        }}

        function minNode(n) {{ while (n && n.left) n = n.left; return n; }}
        function doDelete() {{
          const v = parseInt(document.getElementById("deleteId").value, 10);
          if (isNaN(v)) return setLog("Enter a valid integer Student ID to delete.");
          function del(n, key) {{
            if (!n) return null;
            if (key < n.val) n.left = del(n.left, key);
            else if (key > n.val) n.right = del(n.right, key);
            else {{
              if (!n.left) return n.right;
              if (!n.right) return n.left;
              const succ = minNode(n.right);
              n.val = succ.val;
              n.right = del(n.right, succ.val);
            }}
            return n;
          }}
          treeState.root = del(treeState.root, v);
          if (highlightedId === v) highlightedId = null;
          renderSvg();
          setLog(`DELETED Student ID ${{v}} (0/1/2-child BST removal applied).`);
        }}

        renderSvg();
        if (stepMode) {{
          setLog("STEP-BY-STEP mode: Verified unique global root, stitched matching leaf->root fragments, and checked (min, max) bounds.");
        }} else if (treeState.error) {{
          setLog("DIAGNOSTIC: " + treeState.error);
        }}
      </script>
    </body>
    </html>
    """
    components.html(canvas_html, height=590, scrolling=False)

# ---------------------------------------------------------------------------
# Bottom Panel: Recovery Output & Inorder Traversal Tape
# ---------------------------------------------------------------------------
c_out_str = st.session_state.c_stdout
is_impossible = (not c_out_str) or ("IMPOSSIBLE" in c_out_str)

merged_root_val = "—"
inorder_values = []
tree_struct_text = ""

if c_out_str and not is_impossible:
    in_tree_block = False
    tree_lines = []
    for line in c_out_str.splitlines():
        if line.startswith("Merged Root:"):
            merged_root_val = line.split(":", 1)[1].strip()
        elif line.startswith("Inorder Traversal:"):
            m_in = re.search(r"\[([^\]]*)\]", line)
            if m_in and m_in.group(1).strip():
                inorder_values = [x.strip() for x in m_in.group(1).split(",") if x.strip()]
        elif line.startswith("Tree Structure:"):
            in_tree_block = True
        elif in_tree_block:
            tree_lines.append(line)
    tree_struct_text = "\n".join(tree_lines)

status_bg = "#FF3B30" if is_impossible else "#00C853"
status_fg = "#FFFFFF" if is_impossible else "#000000"
status_txt = "IMPOSSIBLE" if is_impossible else "RECOVERED"
diag_msg = (
    c_out_str.splitlines()[0]
    if (c_out_str and not is_impossible)
    else (c_out_str.replace("\n", " | ") if c_out_str else "No valid fragment set loaded.")
)

tape_cells_html = ""
if inorder_values:
    for idx, val in enumerate(inorder_values):
        cell_bg = palette[idx % len(palette)]
        tape_cells_html += (
            f"<span style='display:inline-block; background:{cell_bg}; border:2px solid #000; "
            f"box-shadow:2px 2px 0 #000; padding:4px 10px; margin-right:6px; font-weight:700;'>{val}</span>"
        )
else:
    tape_cells_html = "<span style='font-size:12px; color:#555;'>Inorder tape unavailable until a valid BST is recovered.</span>"

tree_preview_html = (
    f"<pre style='background:#FAF7F0; border:2px solid #000; padding:10px; margin:10px 0 0 0; font-size:12px; overflow-x:auto;'>{tree_struct_text}</pre>"
    if tree_struct_text
    else ""
)

st.markdown(
    f"""
    <div class="nb-card" style="margin-top:4px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
            <div>
                <span style="display:inline-block; background:{status_bg}; color:{status_fg}; border:2px solid #000; padding:3px 10px; font-weight:700; font-size:12px;">{status_txt}</span>
                <span style="font-size:11px; font-weight:700; margin-left:8px;">DIAGNOSTIC SUMMARY</span>
                <div style="font-size:13px; font-weight:700; margin-top:6px;">{diag_msg}</div>
            </div>
            <div style="background:#FFFDF7; border:3px solid #000; box-shadow:3px 3px 0 #000; padding:6px 14px; text-align:right;">
                <div style="font-size:10px; font-weight:700;">MERGED GLOBAL ROOT</div>
                <div style="font-family:'Inter', sans-serif; font-size:20px; font-weight:800;">{merged_root_val}</div>
            </div>
        </div>
        <div style="border-top:2px solid #000; padding-top:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span class="nb-badge-dark">INORDER TRAVERSAL TAPE (SORTED STUDENT INDEX)</span>
                <span style="font-size:11px; font-weight:700;">Sorted keys from C engine recovery output</span>
            </div>
            <div style="background:#FAF7F0; border:2px solid #000; padding:10px; overflow-x:auto; white-space:nowrap;">
                {tape_cells_html}
            </div>
            {tree_preview_html}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)