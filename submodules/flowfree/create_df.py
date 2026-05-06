# %%


# %%
import re
import sys
from pathlib import Path
import pandas as pd

# --- Config ---
ROOT = Path("/notebooks/multimodal_cot/FlowFree/generated/")  # folder containing your files
OUTPUT_CSV = ROOT / "problems_solutions.csv"

# Regex for any triple-quoted grid
TRIPLE_BLOCK_RE = re.compile(r'"""\s*([\s\S]*?)\s*"""', re.M)

# Regex for the specific "Human-readable solution" section
HR_SOLUTION_RE = re.compile(
    r'##\s*Human-readable solution:\s*"""\s*([\s\S]*?)\s*"""',
    re.M,
)

def extract_problem_and_solution(text: str):
    """
    Returns (problem_grid, solution_grid) as strings (without quotes),
    or (None, None) if not found.
    - Problem grid: first triple-quoted block in the file.
    - Solution grid: triple-quoted block following the 'Human-readable solution' header.
    """
    # Find the solution block (authoritative when present)
    sol_match = HR_SOLUTION_RE.search(text)
    solution = sol_match.group(1) if sol_match else None

    # Problem: take the first triple-quoted block in the file
    triples = TRIPLE_BLOCK_RE.findall(text)
    problem = triples[0] if triples else None

    # Safety: If we only found one block, try to infer which it is.
    # Prefer treating the explicitly labeled "Human-readable solution" as solution.
    if problem == solution and problem is not None:
        # If they’re the same (rare), keep as-is; otherwise leave as found.
        pass

    return problem, solution

def scan_folder(root: Path):
    rows = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            # Skip unreadable files
            continue

        problem, solution = extract_problem_and_solution(text)
        if problem is None and solution is None:
            continue

        rows.append({
            "path": str(p.relative_to(root)),
            "problem": problem,
            "solution": solution,
        })
    return rows

# %%
rows = scan_folder(ROOT)
df = pd.DataFrame(rows)

df.head()

# %%
df.shape

# %%
df.to_csv('/notebooks/multimodal_cot/FlowFree/flowfree_problems_solutions.csv', index=False)

# %%
#path like 9x9_8c_5_2af3ded9.txt	
# find histogram of grid sizes and number of colors
df['grid_size'] = df['path'].apply(lambda x: x.split('_')[0])
df['num_colors'] = df['path'].apply(lambda x: int(x.split('_')[1][:-1]))
df['num_colors'].value_counts().sort_index().plot(kind='bar', title='Number of colors distribution')


# %%
df['grid_size'].value_counts().sort_index().plot(kind='bar', title='Grid size distribution')

# %%
df

# %%
# add a column with 5*5, 6*6 as easy, 7*7, 8*8 as medium, 9*9, 10*10 as hard
df['difficulty'] = df['grid_size'].apply(lambda x: 'easy' if x in ['5x5', '6x6'] else ('medium' if x in ['7x7', '8x8'] else 'hard'))
df['difficulty'].value_counts().sort_index().plot(kind='bar', title='Difficulty distribution')




# %%
# now sample a test set with 50 easy samples, 50 medium samples and 50 hard samples
# add column as test or train
seed = 42
df['set'] = 'train'
df_copy = df.copy()
df_copy = df_copy.sample(frac=1, random_state=seed).reset_index(drop=True)  # shuffle the dataframe
df_copy.shape

for difficulty in ['easy', 'medium', 'hard']:
    mask = (df_copy['difficulty'] == difficulty) & (df_copy['set'] == 'train')
    test_samples = df_copy[mask].head(50).index
    print(f"Selected {len(test_samples)} samples for difficulty {difficulty}")
    # asd
    df_copy.loc[test_samples, 'set'] = 'test'

# %%
len(test_samples)

# %%
df_copy.shape


# %%
df_copy['set'].value_counts().sort_index().plot(kind='bar', title='Train/Test distribution')

# %%
df_copy[df_copy['set'] == 'test']['difficulty'].value_counts().sort_index().plot(kind='bar', title='Test set difficulty distribution')

# %%


# %%
df_copy.to_csv('/notebooks/multimodal_cot/csvs/flowfree_problems_solutions.csv', index=False)


