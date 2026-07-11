import os
import zipfile

OUTPUT = "aurora_export.zip"

IGNORE = {
    "__pycache__",
    ".git",
    ".next",
    "node_modules",
    "dist",
    ".venv",
    ".upm",
    ".cache"
}

EXTENSIONS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".yml",
    ".yaml"
)

with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zipf:

    for root, dirs, files in os.walk("."):

        dirs[:] = [d for d in dirs if d not in IGNORE]

        for file in files:

            if file.endswith(EXTENSIONS):

                path = os.path.join(root, file)

                try:
                    zipf.write(path)
                except:
                    pass

print(f"Exportado para: {OUTPUT}")