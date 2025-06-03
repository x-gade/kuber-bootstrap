import os

total_lines = 0
file_count = 0
extensions = [".py"]
excluded_dirs = {'.venv', '__pycache__', '.git', 'venv', '.idea'}

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in excluded_dirs]

    for file in files:
        if any(file.endswith(ext) for ext in extensions):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    line_count = sum(1 for _ in f)
                    total_lines += line_count
                    file_count += 1
                    print(f"{file_path} — {line_count} строк")
            except Exception as e:
                print(f"Ошибка при чтении {file_path}: {e}")

print(f"\nФайлов всего: {file_count}")
print(f"Total lines of code: {total_lines}")
