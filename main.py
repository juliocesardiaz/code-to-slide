import argparse
import sys
import os
import math
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
    code1 = process_code(file1, lines1)
    lexer1 = get_lexer(file1, code1)
    lang1_name = lexer1.name if lexer1 else "Text"
    
    is_sbs = file2 is not None
    font_size1 = calculate_font_size(code1, is_sbs)
    
    formatter = HtmlFormatter(style='dracula', nowrap=False, linenos='inline')
    pygments_css = formatter.get_style_defs('.code-block')
    
    highlighted1 = highlight(code1, lexer1, formatter)
    
    highlighted2 = ""
    font_size2 = 32
    lang2_name = ""
    if file2:
        code2 = process_code(file2, lines2)
        lexer2 = get_lexer(file2, code2)
        lang2_name = lexer2.name if lexer2 else "Text"
        font_size2 = calculate_font_size(code2, is_sbs)
        highlighted2 = highlight(code2, lexer2, formatter)

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
            .watermark {{
                position: absolute;
                bottom: 20px;
                right: 30px;
                font-size: 28px;
                font-weight: 600;
                color: rgba(255, 255, 150, 0.4); /* Light transparent yellow */
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
            
            .code1 pre {{ font-size: {fs1}px; }}
            .code2 pre {{ font-size: {fs2}px; }}
            
            pre {{
                margin: 0;
                line-height: 1.45;
                white-space: pre-wrap;
                word-wrap: break-word;
                word-break: break-word;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="code-block code1">
                {h1}
                <div class="watermark">{lang1}</div>
            </div>
            {sbs_html}
        </div>
    </body>
    </html>
    """
    
    sbs_html = f'<div class="code-block code2">{highlighted2}<div class="watermark">{lang2_name}</div></div>' if file2 else ""
    
    html_content = html_template.format(
        width=SLIDE_WIDTH,
        height=SLIDE_HEIGHT,
        bg=LAMP_BLACK,
        fg=BONE,
        border=WET_CONCRETE,
        pygments_css=pygments_css,
        fs1=font_size1,
        fs2=font_size2,
        h1=highlighted1,
        lang1=lang1_name,
        sbs_html=sbs_html
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': SLIDE_WIDTH, 'height': SLIDE_HEIGHT}, device_scale_factor=2)
        page.set_content(html_content)
        page.wait_for_timeout(1000) 
        page.screenshot(path=output, full_page=True)
        browser.close()
        
        info = f"(Fonts: {font_size1}px"
        if is_sbs:
            info += f", {font_size2}px"
        info += ")"
        print(f"Slide generated: {os.path.abspath(output)} {info}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code-to-Slide with Dynamic Font Scaling.")
    parser.add_argument("file1", help="Primary code file")
    parser.add_argument("--file2", help="Secondary file for side-by-side", default=None)
    parser.add_argument("--lines1", help="Line range (e.g., '10-25')", default=None)
    parser.add_argument("--lines2", help="Line range for file2", default=None)
    parser.add_argument("--output", "-o", help="Output file", default="slide.png")
    
    args = parser.parse_args()
    generate_image(args.file1, args.file2, args.lines1, args.lines2, args.output)
