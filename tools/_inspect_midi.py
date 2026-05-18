"""Final cleanup: remove remaining grid refs from midi-learn.js by line range"""
path = "frontend/js/midi-learn.js"
lines = open(path, encoding="utf-8").readlines()

# Find and print context around line 171 and 294
print("=== Lines 169-222 ===")
for i in range(168, 222):
    print(f"{i+1}: {repr(lines[i])}")

print("\n=== Lines 290-300 ===")
for i in range(289, 300):
    print(f"{i+1}: {repr(lines[i])}")
