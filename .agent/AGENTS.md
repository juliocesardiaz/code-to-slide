# Code-to-Slide: Agent Onboarding Document

Welcome. This document is designed to bring you up to speed on the "Code-to-Slide Generator" project. It outlines the project's purpose, the architectural decisions made so far, and specific technical "gotchas" we encountered during development.

## 1. Project Context
This script was developed for a professional instructional environment to generate high-quality, side-by-side code visualizations for lecture slides (specifically Google Slides, targeting a 16:9 ratio at 1920x1080 resolution). 

The output must prioritize legibility for students viewing from a distance, while adhering to a strict, minimalist aesthetic philosophy.

## 2. Core Architecture
- **Engine**: The script reads code files and syntax highlights them using **Pygments**.
- **Rendering**: It injects the highlighted HTML into a template string and uses **Playwright** (Chromium) to render that HTML into a perfectly sized `1920x1080` PNG.
- **Dynamic Scaling**: The script features a `calculate_font_size` function that dynamically determines the largest possible font size based on the longest line length and the total number of lines, capping at 80px to prevent text from overflowing the container.

## 3. Aesthetic Constraints ("Structural Silence")
The project strictly adheres to a "Ground Mode" color palette. Future modifications MUST NOT deviate from these colors unless explicitly requested:
- **Background**: `LAMP_BLACK` (`#000000`). This must be *pure* black, not charcoal or dark grey.
- **Text/Figure**: `BONE` (`#F0EBE3`). Used for default text and line numbers.
- **Syntax Theme**: We rely on Pygments' built-in `dracula` theme, but we manually force the background of the `.code-block`, `.highlight`, and `pre` wrappers to be transparent or pure black so the Dracula background doesn't bleed into the design.
- **Watermarks**: A subtle, transparent yellow (`rgba(255, 255, 150, 0.4)`) is used for the language watermark in the bottom right corner.

## 4. Key Learnings & Gotchas
If you are modifying the CSS or the HTML template, be aware of the following history:

1.  **Template Escaping (`KeyError`)**: 
    - *The Problem*: Initially, we used an f-string for the `html_template` that included CSS definitions (e.g., `.code-block { display: flex; }`). This caused Python to try and interpolate the CSS braces as variables, resulting in `KeyError` or `NameError`.
    - *The Solution*: We switched to using `.format()` for the template. **Crucially, all raw CSS curly braces must be escaped with double braces (`{{` and `}}`)** to prevent `.format()` from parsing them.
2.  **Pygments Wrapper Backgrounds**: 
    - *The Problem*: Pygments injects a `.highlight` class that carries the background color of the chosen theme (Dracula). This caused a dark-grey box to appear behind the code, ruining the pure black design.
    - *The Solution*: We added `background-color: transparent !important;` to `.code-block .highlight, .code-block pre` in the CSS to force the pure black background to show through.
3.  **Line Number Width Calculation**: 
    - *The Problem*: When we enabled Pygments' inline line numbers (`linenos='inline'`), the lines became wider, causing long lines of code to wrap and ruin the slide layout.
    - *The Solution*: In `calculate_font_size`, we explicitly added a buffer of `+ 5` to `max_line_len` to account for the physical space taken up by the prepended line numbers (e.g., ` 10  `). If you change the line number format, you must adjust this buffer.
4.  **Word Wrapping**: 
    - We use `white-space: pre-wrap;` and `word-break: break-word;` as a fallback safety net to ensure incredibly long comments or strings don't just disappear off the edge of the slide, though the dynamic scaling usually prevents this.

---
*End of Briefing. Good luck.*