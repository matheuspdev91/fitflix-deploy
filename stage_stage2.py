import subprocess, os

repo = "C:/Users/Matheus/Desktop/fitflix-deploy"
out = subprocess.run(
    ["git", "-C", repo, "diff", "--no-color", "core/tests.py"],
    capture_output=True, text=True, check=True
).stdout
lines = out.splitlines(keepends=True)

target_offsets = {"-310", "-608", "-692", "-707"}
hunks = []
cur = []
in_hunk = False

for ln in lines:
    if ln.startswith("@@"):
        if in_hunk:
            if any(off in cur[0] for off in target_offsets):
                hunks.append("".join(cur))
        cur = [ln]
        in_hunk = True
    else:
        if in_hunk:
            cur.append(ln)

if in_hunk:
    if any(off in cur[0] for off in target_offsets):
        hunks.append("".join(cur))

filtered = "".join(hunks)

# Adiciona os headers de arquivo no topo do patch
patch = (
    "diff --git a/core/tests.py b/core/tests.py\n"
    "--- a/core/tests.py\n"
    "+++ b/core/tests.py\n"
    + filtered
)
patch_path = os.path.join(repo, "stage_patch_4hunks.diff")
with open(patch_path, "w", encoding="utf-8") as f:
    f.write(patch)

res = subprocess.run(
    ["git", "-C", repo, "apply", "--cached", patch_path],
    capture_output=True, text=True
)
print("git apply --cached rc:", res.returncode)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)

print("\n=== git diff --cached --stat ===")
print(subprocess.run(
    ["git", "-C", repo, "diff", "--cached", "--stat"],
    capture_output=True, text=True, check=True
).stdout)

print("\n=== git diff --cached -- core/tests.py (resumo das 4 alterações) ===")
print(subprocess.run(
    ["git", "-C", repo, "diff", "--cached", "--", "core/tests.py"],
    capture_output=True, text=True, check=True
).stdout)

os.remove(patch_path)
