import argparse
import sys
import os
import math
import re
import html
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, guess_lexer, get_lexer_by_name
from pygments.lexers.special import TextLexer
from pygments.formatters import HtmlFormatter
from playwright.sync_api import sync_playwright

# Google Slides Standard 16:9 dimensions
SLIDE_WIDTH = 1920
SLIDE_HEIGHT = 1080

# Design Doc Colors (Ground Mode)
LAMP_BLACK = "#000000"
BONE = "#F0EBE3"
WET_CONCRETE = "#2A2826"

# LaTeX packages that require TikZJax (instead of KaTeX)
TIKZ_PACKAGES = {'tikzcd', 'tikz', 'pgf', 'pgfplots', 'circuitikz', 'pgfplotstable'}


def is_math_file(path):
    return path is not None and path.endswith('.math')


def is_mermaid_file(path):
    return path is not None and path.endswith('.mmd')


def parse_mermaid_file(file_path):
    """Parse a .mmd file, stripping ```mermaid ... ``` fences if present."""
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if content.startswith('```mermaid'):
        content = content[len('```mermaid'):].strip()
        if content.endswith('```'):
            content = content[:-3].strip()

    return content


def parse_math_file(file_path):
    """Parse a .math file, returning (packages, equation).

    Extracts \\usepackage declarations from the top of the file and returns
    the equation body with surrounding $$ delimiters stripped.
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    lines = content.splitlines()
    packages = []
    eq_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(r'\usepackage'):
            match = re.search(r'\{(.+?)\}', stripped)
            if match:
                packages.append(match.group(1))
        else:
            eq_lines.append(line)

    equation = '\n'.join(eq_lines).strip()
    if equation.startswith('$$') and equation.endswith('$$'):
        equation = equation[2:-2].strip()

    return packages, equation


def get_lexer(filename, code):
    try:
        if filename.endswith('.py'):
            return get_lexer_by_name('python')
        if filename.endswith('.c') or filename.endswith('.h'):
            return get_lexer_by_name('c')
        if filename:
            return get_lexer_for_filename(filename)
        return guess_lexer(code)
    except Exception:
        return TextLexer()


def process_code(file_path, lines=None):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        code_lines = f.readlines()

    if lines:
        try:
            parts = lines.split('-')
            start = int(parts[0])
            end = int(parts[1])
            code_lines = code_lines[start-1:end]
        except (ValueError, IndexError):
            print(f"Warning: Invalid line range '{lines}'.")

    return "".join(code_lines)


def calculate_font_size(code, is_side_by_side=False):
    lines = code.splitlines()
    if not lines:
        return 32

    # Add 5 to max_line_len to account for the line number prefix (e.g. " 10  ")
    max_line_len = max(len(line) for line in lines) + 5
    line_count = len(lines)

    avail_width = (SLIDE_WIDTH / 2 - 160) if is_side_by_side else (SLIDE_WIDTH - 200)
    avail_height = SLIDE_HEIGHT - 200

    size_from_width = avail_width / (max_line_len * 0.62)
    size_from_height = avail_height / (line_count * 1.45)

    optimal_size = min(size_from_width, size_from_height)
    return max(18, min(80, math.floor(optimal_size)))


def generate_image(file1, file2=None, lines1=None, lines2=None, output="slide.png"):
    is_sbs = file2 is not None

    formatter = HtmlFormatter(style='dracula', nowrap=False, linenos='inline')
    pygments_css = formatter.get_style_defs('.code-block')

    uses_katex = False
    uses_tikzjax = False
    uses_mermaid = False
    katex_scripts = []
    fs_css_parts = []

    def build_code_panel(filepath, lines, slot):
        code = process_code(filepath, lines)
        lexer = get_lexer(filepath, code)
        lang_name = lexer.name if lexer else "Text"
        fs = calculate_font_size(code, is_sbs)
        fs_css_parts.append(f".{slot} pre {{ font-size: {fs}px; }}")
        highlighted = highlight(code, lexer, formatter)
        return highlighted, lang_name, fs

    def build_mermaid_panel(filepath):
        nonlocal uses_mermaid
        uses_mermaid = True
        diagram = parse_mermaid_file(filepath)
        # HTML-escape so browser doesn't interpret < > & inside the pre element
        escaped = html.escape(diagram)
        return (
            f'<div class="mermaid-block">'
            f'<pre class="mermaid">{escaped}</pre>'
            f'<div class="watermark">Mermaid</div>'
            f'</div>'
        )

    def build_math_panel(filepath, slot):
        nonlocal uses_katex, uses_tikzjax
        packages, equation = parse_math_file(filepath)
        tikz_pkgs = [p for p in packages if p in TIKZ_PACKAGES]

        if tikz_pkgs:
            uses_tikzjax = True
            pkg_declarations = '\n'.join(f'\\usepackage{{{p}}}' for p in packages)
            return (
                f'<div class="math-block">\n'
                f'                <script type="text/tikz">\n'
                f'{pkg_declarations}\n'
                f'{equation}\n'
                f'                </script>\n'
                f'                <div class="watermark">Math</div>\n'
                f'            </div>'
            ), None
        else:
            uses_katex = True
            # Escape characters that would break a JS template literal
            eq_escaped = equation.replace('`', '\\`').replace('${', '\\${')
            script = (
                f'katex.render(String.raw`{eq_escaped}`, '
                f'document.getElementById("math-{slot}"), '
                f'{{displayMode: true, throwOnError: false}});'
            )
            katex_scripts.append(script)
            return (
                f'<div class="math-block">'
                f'<div id="math-{slot}"></div>'
                f'<div class="watermark">Math</div>'
                f'</div>'
            ), None

    # Build panel 1
    if is_mermaid_file(file1):
        panel1_html = build_mermaid_panel(file1)
    elif is_math_file(file1):
        panel1_html, _ = build_math_panel(file1, "1")
    else:
        highlighted1, lang1_name, fs1 = build_code_panel(file1, lines1, "code1")
        panel1_html = (
            f'<div class="code-block code1">'
            f'{highlighted1}'
            f'<div class="watermark">{lang1_name}</div>'
            f'</div>'
        )

    # Build panel 2
    panel2_html = ""
    if file2:
        if is_mermaid_file(file2):
            panel2_html = build_mermaid_panel(file2)
        elif is_math_file(file2):
            panel2_html, _ = build_math_panel(file2, "2")
        else:
            highlighted2, lang2_name, fs2 = build_code_panel(file2, lines2, "code2")
            panel2_html = (
                f'<div class="code-block code2">'
                f'{highlighted2}'
                f'<div class="watermark">{lang2_name}</div>'
                f'</div>'
            )

    # Build conditional <head> assets
    extra_head_parts = []
    if uses_katex:
        extra_head_parts.append(
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">\n'
            '    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>'
        )
    if uses_tikzjax:
        extra_head_parts.append(
            '<link rel="stylesheet" href="https://tikzjax.com/v1/fonts.css">\n'
            '    <script src="https://tikzjax.com/v1/tikzjax.js"></script>'
        )
    if uses_mermaid:
        extra_head_parts.append(
            '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
        )
    extra_head = '\n    '.join(extra_head_parts)

    # Build KaTeX render script block
    katex_render_block = ""
    if katex_scripts:
        inner = '\n        '.join(katex_scripts)
        katex_render_block = f'<script>\n        {inner}\n    </script>'

    # Build Mermaid init block (Ground Mode palette)
    mermaid_init_block = ""
    if uses_mermaid:
        mermaid_init_block = (
            "<script>\n"
            "        mermaid.initialize({\n"
            "            startOnLoad: false,\n"
            "            theme: 'base',\n"
            "            themeVariables: {\n"
            f"                background: '{LAMP_BLACK}',\n"
            f"                primaryColor: '{WET_CONCRETE}',\n"
            f"                primaryTextColor: '{BONE}',\n"
            f"                primaryBorderColor: '{BONE}',\n"
            f"                lineColor: '{BONE}',\n"
            "                secondaryColor: '#1A1816',\n"
            f"                tertiaryColor: '{LAMP_BLACK}',\n"
            f"                edgeLabelBackground: '{LAMP_BLACK}',\n"
            f"                nodeTextColor: '{BONE}'\n"
            "            }\n"
            "        });\n"
            "        mermaid.run();\n"
            "    </script>"
        )

    fs_css = '\n            '.join(fs_css_parts)

    # Use .format() instead of f-string to avoid complex brace escaping issues
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

            body, html {{
                margin: 0;
                padding: 0;
                width: {width}px;
                height: {height}px;
                background-color: {bg};
                display: flex;
                align-items: center;
                justify-content: center;
                box-sizing: border-box;
                overflow: hidden;
                color: {fg};
                font-family: 'JetBrains Mono', monospace;
            }}
            .container {{
                display: flex;
                flex-direction: row;
                gap: 60px;
                width: 100%;
                height: 100%;
                padding: 80px;
                box-sizing: border-box;
            }}
            .code-block {{
                flex: 1;
                background-color: {bg} !important;
                border: 1px solid {border};
                padding: 40px;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: center;
                position: relative;
            }}
            .code-block .highlight, .code-block pre {{
                background-color: transparent !important;
            }}
            .math-block {{
                flex: 1;
                background-color: {bg} !important;
                border: 1px solid {border};
                padding: 40px;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                position: relative;
            }}
            .math-block .katex, .math-block .katex * {{
                color: {fg} !important;
            }}
            .math-block svg {{
                fill: {fg};
                stroke: {fg};
                max-width: 100%;
                max-height: 80%;
            }}
            .mermaid-block {{
                flex: 1;
                background-color: {bg} !important;
                border: 1px solid {border};
                padding: 40px;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                position: relative;
            }}
            .mermaid-block svg {{
                max-width: 100%;
                max-height: 80%;
            }}
            .mermaid-block pre {{
                margin: 0;
                white-space: pre;
            }}
            .watermark {{
                position: absolute;
                bottom: 20px;
                right: 30px;
                font-size: 28px;
                font-weight: 600;
                color: rgba(255, 255, 150, 0.4);
                text-transform: uppercase;
                letter-spacing: 3px;
                pointer-events: none;
            }}
            .linenos {{
                color: {border};
                opacity: 0.7;
                padding-right: 20px;
                user-select: none;
                text-align: right;
                display: inline-block;
            }}

            {pygments_css}

            {fs_css}

            pre {{
                margin: 0;
                line-height: 1.45;
                white-space: pre-wrap;
                word-wrap: break-word;
                word-break: break-word;
            }}
        </style>
        {extra_head}
    </head>
    <body>
        <div class="container">
            {panel1}
            {panel2}
        </div>
        {katex_render_block}
        {mermaid_init_block}
    </body>
    </html>
    """

    html_content = html_template.format(
        width=SLIDE_WIDTH,
        height=SLIDE_HEIGHT,
        bg=LAMP_BLACK,
        fg=BONE,
        border=WET_CONCRETE,
        pygments_css=pygments_css,
        fs_css=fs_css,
        extra_head=extra_head,
        panel1=panel1_html,
        panel2=panel2_html,
        katex_render_block=katex_render_block,
        mermaid_init_block=mermaid_init_block,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': SLIDE_WIDTH, 'height': SLIDE_HEIGHT}, device_scale_factor=2)
        page.set_content(html_content)

        if uses_tikzjax or uses_mermaid:
            page.wait_for_selector('svg', timeout=30000)
        else:
            page.wait_for_timeout(2000)

        page.screenshot(path=output, full_page=True)
        browser.close()

        print(f"Slide generated: {os.path.abspath(output)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code-to-Slide with Dynamic Font Scaling.")
    parser.add_argument("file1", help="Primary file: source code, .math, or .mmd")
    parser.add_argument("--file2", help="Secondary file for side-by-side: source code, .math, or .mmd", default=None)
    parser.add_argument("--lines1", help="Line range (e.g., '10-25')", default=None)
    parser.add_argument("--lines2", help="Line range for file2", default=None)
    parser.add_argument("--output", "-o", help="Output file", default="slide.png")

    args = parser.parse_args()
    generate_image(args.file1, args.file2, args.lines1, args.lines2, args.output)
