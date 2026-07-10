import os
import json
from pathlib import Path

IGNORE = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".cache",
}

KEYWORDS = [
    "OPENAI_API_KEY",
    "OpenAI(",
    "AsyncOpenAI",
    "chat.completions",
    "responses.create",
    "gpt-",
    "session_id",
    "@router.get",
    "@router.post",
    "dispatch(",
    "fetch(",
    "sqlite3",
    ".db",
]

report = {"project_tree": [], "keywords": {}}


def should_scan(filename):
    extensions = (
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".env",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
    )

    return filename.endswith(extensions)


for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in IGNORE]

    level = root.count(os.sep)

    report["project_tree"].append(f"{'    ' * level}{Path(root).name}/")

    for file in files:
        path = os.path.join(root, file)

        report["project_tree"].append(f"{'    ' * (level + 1)}{file}")

        if not should_scan(file):
            continue

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for keyword in KEYWORDS:
                if keyword in content:
                    report["keywords"].setdefault(keyword, []).append(path)

        except Exception:
            pass


with open("aurora_context.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("Arquivo gerado:")
print("aurora_context.json")
