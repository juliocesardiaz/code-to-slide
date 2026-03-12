# Code-to-Slide Generator

I developed this script to enhance technical instruction by generating high-quality code visualizations for lecture slides. It is designed specifically for Google Slides (16:9) to provide students with clear, legible code comparisons.

## 🚀 Features
- **16:9 Aspect Ratio:** Optimized at 1920x1080 for seamless slide integration.
- **Side-by-Side Comparison:** Compare two snippets (e.g., C and Python) in a single frame.
- **Dynamic Font Scaling:** Automatically calculates the optimal font size to maximize legibility.
- **Inline Line Numbers:** Facilitates direct referencing during lectures.
- **Language Watermarks:** Subtle identification of syntax highlighting.

## 🛠 Dependencies
- `pygments`
- `playwright` (Requires: `playwright install chromium`)

## 💻 Usage
```bash
python main.py source.py --file2 comparison.c -o slide.png
```

---
*Note: I plan on adding further features to support more complex lecture requirements.*
