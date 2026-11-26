```markdown
# 🌳 Registrar's Fragmented Student Index (Flash Hack V3.0 - PS12)

A C-backed recovery system and interactive Streamlit dashboard that reconstructs a single, valid Binary Search Tree (BST) from `1` to `100` fragmented `1`-to-`3`-node subtrees—or detects structural and ordering conflicts and reports `IMPOSSIBLE` with the exact failure reason.

---

## 👥 Team Members
1. 🧑‍💻 **Sunil Maruti Kadam** – 1DS25CS282 / [GitHub](https://github.com/sunilkadam2781-maker)
2. 🧑‍💻 **Udith V Kumar** – 1DS25CS300 / [GitHub](https://github.com/thekumar-85-mark)
3. 🧑‍💻 **Viraj Guranna Yalawar** – 1DS25CS310 / [GitHub](https://github.com/virajgurannayalawar)
4. 🧑‍💻 **Yashwantha Kumara** – 1DS25CS314 / [GitHub](https://github.com/Yash2008may)

---

## 🏗️ Project Architecture

```text
student-idx-recovery/
├── student_index_BST.c   # C recovery engine (parsing, stitching, global BST check)
├── app.py                # Neo-Brutalist Streamlit dashboard, presets, SVG tree & console
└── README.md             # Project documentation, architecture & progress

```

* **Backend C Engine (`student_index_BST.c`):** Compiled with `-Wall -Wextra -O2` to enforce `1–100` fragment limits (`MAX_FRAGS = 100`), local BST validity, unique root/cycle detection, recursive leaf-to-root stitching, full fragment consumption, `(LLONG_MIN, LLONG_MAX)` global BST bound checking, and clean heap memory deallocation.
* **Frontend Dashboard (`app.py`):** Built in Streamlit with a Neo-Brutalist theme, providing one-click preset scenarios, a raw expression editor + visual fragment card builder, live execution of the compiled C binary, an interactive pan/zoom SVG topology view, a sorted inorder traversal tape, and a post-merge Search/Insert/Delete operations console.

---

## 🚀 Step-by-Step Introduction

1. 📄 **Understand the Fragment Format:** Each input fragment represents a local root node with up to two immediate children (`root [left] [right]`, using `-` when a child is absent).
2. ⌨️ **Enter Fragment Count & Data:** At runtime, specify the total number of fragments (`1–100`) and enter each fragment line—either directly into `stdin` for the C binary or through the Streamlit workbench.
3. 🔗 **Validate & Merge:** The engine parses each fragment, identifies the unique global root, stitches matching leaf nodes to corresponding fragment roots, and verifies global BST invariants.
4. 📊 **Inspect Output:**
* ✅ **Valid Tree:** Prints `SUCCESS`, the merged global root, the sorted inorder traversal, and an indented visual tree layout (plus interactive tree & inorder views in the dashboard).
* ❌ **Invalid Input:** Prints `IMPOSSIBLE` alongside a diagnostic message explaining which rule was violated.



---

## ⚙️ Methodology

The recovery pipeline runs in four deterministic stages (`O(N^2)` worst-case time, `O(N)` space for `N <= 100`):

1. 🔍 **Parsing & Local Fragment Validation (`build_fragments`)**
* Reads up to three tokens per line and rejects malformed inputs or duplicate fragment root IDs.
* Enforces immediate parent-child BST rules on every fragment (`left < root` and `right > root`) before any merging occurs.


2. 🎯 **Unique Global Root Identification (`appears_as_child`)**
* Scans all fragments to find roots that never appear as a left or right child in any other fragment.
* Rejects inputs with `0` root candidates (cycles) or more than `1` root candidate (disconnected forest).


3. 🧵 **Recursive Subtree Stitching (`stitch`)**
* Starting from the unique global root, traverses down to leaf nodes and replaces any leaf whose value matches an unused fragment root with that fragment's subtree.
* Tracks used fragments via `used_roots[]` to ensure every fragment is consumed exactly once and no unreachable components remain.


4. 🛡️ **Global BST Range Verification (`is_valid_bst`)**
* Performs a top-down recursive traversal passing strict `(min, max)` bounds (`LLONG_MIN` to `LLONG_MAX`) down every branch.
* Catches deep subtree violations where a node satisfies its local parent rule but violates an ancestor's boundary (e.g., a node in a right subtree smaller than the global root).



---

## 🛠️ Build & Run

### 🔨 Compile C Engine

```bash
gcc -Wall -Wextra -O2 student_index_BST.c -o demo

```

### ▶️ Run C Binary Directly (Interactive Demo)

```bash
./demo

```

*(On Windows PowerShell, run `.\demo.exe` after compiling with `-o demo.exe`.)*

### 🖥️ Run Streamlit Dashboard

```bash
streamlit run app.py

```

---

## 🧪 Demo Test Cases

### 1. ✅ Valid Merge (`SUCCESS`)

**Input:**

```text
3
2 1 -
3 2 5
5 4 -

```

**Expected Result:** `SUCCESS`, Merged Root: `3`, Inorder Traversal: `[1, 2, 3, 4, 5]`.

### 2. ❌ Global BST Ordering Conflict (`IMPOSSIBLE`)

**Input:**

```text
2
3 2 6
6 2 8

```

**Expected Result:** `IMPOSSIBLE: Global BST ordering violation in merged tree.`

### 3. ❌ Disconnected / Unused Fragment (`IMPOSSIBLE`)

**Input:**

```text
4
2 1 -
3 2 5
5 4 -
99 95 -

```

**Expected Result:** `IMPOSSIBLE: Unused/unreachable fragment with root 99.`

---

## 📌 Work Progress So Far

* [x] **Core C Recovery Engine (`student_index_BST.c`):** Implemented fragment parsing, duplicate root checks, cycle and disconnected-root detection, recursive leaf-to-root stitching, unused-fragment rejection, `(min, max)` global BST validation, and full memory cleanup.
* [x] **Constraint Alignment (`1–100` Fragments):** Standardized `MAX_FRAGS = 100` across both `student_index_BST.c` and `app.py` to match project scope.
* [x] **Neo-Brutalist Streamlit Dashboard (`app.py`):** Built preset test cases (illustrative, unseen valid, BST conflict, disconnected fragment, and 100-fragment bound), raw expression editor, visual fragment card builder, KPI bar, and recovery/inorder output panel.
* [x] **Interactive Topology & Post-Merge Console:** Added pan/zoom/node-inspection SVG rendering and live post-merge Search, Insert, and Delete operations.
* [x] **UI Polish & Verification:** Resolved typography compression and post-merge console clipping, and verified valid merges, duplicate roots, ordering conflicts, and orphan fragments against the C engine.

```

```
