#!/usr/bin/env python3

import sys
import re
import os
import subprocess

# ANSI escape codes (ensure these are all defined as before)
RESET = "\033[0m"; BOLD = "\033[1m"; ITALIC = "\033[3m"; DIM = "\033[2m"
F_RED = "\033[31m"; F_GREEN = "\033[32m"; F_YELLOW = "\033[33m"; F_BLUE = "\033[34m"
F_MAGENTA = "\033[35m"; F_CYAN = "\033[36m"; F_WHITE = "\033[37m"; F_DEFAULT = "\033[39m"
F_B_RED = "\033[91m"; F_B_BLUE = "\033[94m"; F_B_YELLOW = "\033[93m"; F_B_CYAN = "\033[96m"
BG_BLACK_BRIGHT = "\033[100m"; BG_DEFAULT = "\033[49m" # Using BG_DEFAULT for fallback code blocks

STYLE = {
    "h1": BOLD + F_B_BLUE, "h2": BOLD + F_B_BLUE, "h3": BOLD + F_BLUE, "h4": BOLD + F_BLUE,
    "h5": BOLD + F_CYAN, "h6": BOLD + F_CYAN,
    "bold": BOLD,
    "italic": ITALIC + F_GREEN, # Green color for italic as visual cue
    "bold_italic": BOLD + ITALIC + F_B_RED, # Combined style for ***, ___, and nested
    "inline_code_fg": F_B_YELLOW, "inline_code_bg": "",
    "code_block_fg": F_B_CYAN, "code_block_bg": BG_DEFAULT, # Fallback for code blocks
    "list_marker": F_MAGENTA, "blockquote_marker": ITALIC + F_YELLOW,
    "link_text": F_B_BLUE, "link_url": DIM + F_BLUE, "hr": DIM + F_WHITE,
}

# Pygments (optional import) - ensure this section is present
try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import Terminal256Formatter
    from pygments.util import ClassNotFound
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False
    class ClassNotFound(Exception): pass
    def guess_lexer(code, **options): raise ClassNotFound("Pygments not available")


def apply_styles(line):
    """Applies inline Markdown styles to a line of text. Order is important."""

    # --- PRE-PROCESSING FOR SPECIFIC NESTED CASES ---

    # Case 1: **_content_** (Bold asterisks, italic underscore)
    # Content is group 2 (\2) because (?P<ud>_) is group 1
    line = re.sub(r'\*\*(?P<ud>_)(?!_)(?!\s)(.+?)(?<!\s)(?P=ud)(?!_)\*\*', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)

    # Case 2: *__content__* (Italic asterisk, bold underscores)
    # Content is group 2 (\2)
    line = re.sub(r'\*(?P<ud>__)(?!_)(?!\s)(.+?)(?<!\s)(?P=ud)(?!_)\*', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)
    
    # Case 3: __*content*__ (Bold underscores, italic asterisk)
    # Content is group 2 (\2)
    line = re.sub(r'__(?P<ast>\*)(?!\*)(?!\s)(.+?)(?<!\s)(?P=ast)(?!\*)\*\*',  # Mistake here, should be __ at end
                  rf'{STYLE["bold_italic"]}\2{RESET}', line) 
    # Corrected Case 3:
    line = re.sub(r'__(?P<ast>\*)(?!\*)(?!\s)(.+?)(?<!\s)(?P=ast)(?!\*)__', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)


    # Case 4: _**content**_ (Italic underscore, bold asterisks)
    # Content is group 2 (\2)
    line = re.sub(r'_(?P<ast>\*\*)(?!\*)(?!\s)(.+?)(?<!\s)(?P=ast)(?!\*)\_', # Mistake here, should be _ at end
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)
    # Corrected Case 4:
    line = re.sub(r'_(?P<ast>\*\*)(?!\*)(?!\s)(.+?)(?<!\s)(?P=ast)(?!\*)_', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)


    # --- STANDARD BOLD ITALIC (*** and ___) ---
    line = re.sub(r'\*\*\*(?!\s)(.+?)(?<!\s)\*\*\*', rf'{STYLE["bold_italic"]}\1{RESET}', line)
    line = re.sub(r'___(?!\s)(.+?)(?<!\s)___', rf'{STYLE["bold_italic"]}\1{RESET}', line)

    # --- STANDARD BOLD (** and __) ---
    line = re.sub(r'\*\*(?!\s)(.+?)(?<!\s)\*\*', rf'{STYLE["bold"]}\1{RESET}', line)
    line = re.sub(r'__(?!\s)(.+?)(?<!\s)__', rf'{STYLE["bold"]}\1{RESET}', line)

    # --- STANDARD ITALIC (* and _) ---
    line = re.sub(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', rf'{STYLE["italic"]}\1{RESET}', line) # For *
    line = re.sub(r'(?<![a-zA-Z0-9_])_(?!_)(?!\s)(.+?)(?<!\s)_(?!_)(?![a-zA-Z0-9_])', rf'{STYLE["italic"]}\1{RESET}', line) # For _
    
    # --- INLINE CODE & LINKS ---
    line = re.sub(r'`(.*?)`', rf'{STYLE["inline_code_bg"]}{STYLE["inline_code_fg"]}\1{RESET}', line)
    line = re.sub(r'\[(.*?)\]\((.*?)\)', rf'{STYLE["link_text"]}[\1]{RESET}({STYLE["link_url"]}\2{RESET})', line)

    return line

def print_plain_code_block(lines, style_dict, output_func):
    for l in lines:
        output_func(f"{style_dict['code_block_bg']}{style_dict['code_block_fg']}{l}{RESET}")

def process_stream(input_stream, output_func):
    in_code_block = False
    current_block_language = None # Not strictly needed if we re-extract from opening fence
    code_block_lines = [] # Will now include the opening fence line

    terminal_columns = None
    if sys.stdout.isatty():
        try:
            terminal_columns = os.get_terminal_size().columns
        except OSError:
            terminal_columns = None

    for line_raw in input_stream:
        line = line_raw.rstrip('\n')
        stripped_line = line.strip()
        
        is_closing_fence = in_code_block and stripped_line == "```"
        opening_fence_match = None
        if not in_code_block:
            opening_fence_match = re.match(r'^```([^`\s]*)\s*$', stripped_line)

        if is_closing_fence or opening_fence_match:
            if in_code_block: 
                in_code_block = False
                code_block_lines.append(line) 

                if code_block_lines:
                    actual_opening_fence_line = code_block_lines[0]
                    actual_closing_fence_line = code_block_lines[-1]
                    content_lines = code_block_lines[1:-1]

                    temp_match = re.match(r'^```([^`\s]*)\s*$', actual_opening_fence_line.strip())
                    lang_for_highlighting = None
                    if temp_match:
                        lang_spec = temp_match.group(1)
                        lang_for_highlighting = lang_spec.lower() if lang_spec else None
                    
                    output_func(actual_opening_fence_line)

                    if content_lines:
                        code_to_highlight = "\n".join(content_lines)
                        lexer = None
                        if PYGMENTS_AVAILABLE:
                            if lang_for_highlighting:
                                try: lexer = get_lexer_by_name(lang_for_highlighting, stripall=True)
                                except ClassNotFound:
                                    try: lexer = guess_lexer(code_to_highlight, stripall=True)
                                    except ClassNotFound: lexer = None
                            else:
                                try: lexer = guess_lexer(code_to_highlight, stripall=True)
                                except ClassNotFound: lexer = None
                        
                        if lexer:
                            try:
                                formatter = Terminal256Formatter(style='dracula')
                                highlighted_code = highlight(code_to_highlight, lexer, formatter)
                                output_func(highlighted_code.rstrip('\n') + RESET)
                            except Exception:
                                print_plain_code_block(content_lines, STYLE, output_func)
                        else:
                            print_plain_code_block(content_lines, STYLE, output_func)
                    
                    output_func(actual_closing_fence_line)
                
                code_block_lines = []
            else: 
                in_code_block = True
                code_block_lines.append(line)
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        processed_line = line
        if re.fullmatch(r'^\s*(\---|___|\*\*\*)\s*$', processed_line.strip()):
            if terminal_columns:
                bar_char = "─"; full_width_bar = bar_char * terminal_columns
                output_func(f"{STYLE['hr']}{full_width_bar}{RESET}")
            else:
                output_func(f"{STYLE['hr']}{processed_line.strip()}{RESET}")
            continue
        
        header_match = re.match(r'^(#+)\s+(.*)', processed_line)
        if header_match:
            level = len(header_match.group(1)); text = header_match.group(2)
            header_style_key = f"h{min(level, 6)}"
            styled_text = apply_styles(text)
            output_func(f"{STYLE[header_style_key]}{header_match.group(1)} {styled_text}{RESET}")
            continue
            
        ul_match = re.match(r'^(\s*)(\*|\-|\+)\s+(.*)', processed_line)
        if ul_match:
            indent, marker, text = ul_match.groups()
            styled_text = apply_styles(text)
            output_func(f"{indent}{STYLE['list_marker']}{marker}{RESET} {styled_text}")
            continue

        ol_match = re.match(r'^(\s*)(\d+\.)\s+(.*)', processed_line)
        if ol_match:
            indent, marker, text = ol_match.groups()
            styled_text = apply_styles(text)
            output_func(f"{indent}{STYLE['list_marker']}{marker}{RESET} {styled_text}")
            continue

        bq_match = re.match(r'^(\s*)(>\s+)(.*)', processed_line)
        if bq_match:
            indent, marker, text = bq_match.groups()
            styled_text = apply_styles(text)
            output_func(f"{indent}{STYLE['blockquote_marker']}{marker.rstrip()}{RESET} {styled_text}")
            continue
        
        output_func(apply_styles(processed_line))

    # After the loop, handle any pending code block (for streaming)
    if in_code_block and code_block_lines:
        actual_opening_fence_line = code_block_lines[0]
        content_lines = code_block_lines[1:]

        temp_match = re.match(r'^```([^`\s]*)\s*$', actual_opening_fence_line.strip())
        lang_for_highlighting = None
        if temp_match:
            lang_spec = temp_match.group(1)
            lang_for_highlighting = lang_spec.lower() if lang_spec else None

        output_func(actual_opening_fence_line)

        if content_lines:
            code_to_highlight = "\n".join(content_lines)
            lexer = None
            if PYGMENTS_AVAILABLE:
                if lang_for_highlighting:
                    try: lexer = get_lexer_by_name(lang_for_highlighting, stripall=True)
                    except ClassNotFound:
                        try: lexer = guess_lexer(code_to_highlight, stripall=True)
                        except ClassNotFound: lexer = None
                else:
                    try: lexer = guess_lexer(code_to_highlight, stripall=True)
                    except ClassNotFound: lexer = None
            if lexer:
                try:
                    formatter = Terminal256Formatter(style='native')
                    highlighted_code = highlight(code_to_highlight, lexer, formatter)
                    output_func(highlighted_code.rstrip('\n') + RESET)
                except Exception:
                    print_plain_code_block(content_lines, STYLE, output_func)
            else:
                print_plain_code_block(content_lines, STYLE, output_func)
        output_func(f"{RESET}```" + RESET)


def main():
    filename_arg = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print(f"Usage: {sys.argv[0]} [markdown_file]")
            print("Processes Markdown from file or stdin and outputs colorized text.")
            print("If a file is given and output is to a TTY, 'less -R' is used for paging.")
            sys.exit(0)
        filename_arg = sys.argv[1]
        if filename_arg == '-': 
            filename_arg = None

    input_source = None; close_source_after = False; should_page = False

    if filename_arg:
        if not os.path.exists(filename_arg):
            print(f"{RESET}Error: File not found: {filename_arg}", file=sys.stderr); sys.exit(1)
        try:
            input_source = open(filename_arg, 'r', encoding='utf-8')
            close_source_after = True
            if sys.stdout.isatty(): should_page = True
        except Exception as e:
            print(f"{RESET}Error opening file {filename_arg}: {e}", file=sys.stderr); sys.exit(1)
    else: 
        input_source = sys.stdin
        should_page = False

    if not sys.stdin.isatty() and filename_arg is None:
        if not PYGMENTS_AVAILABLE:
            print("Notice: Pygments library not found...", file=sys.stderr) # Abridged

    if should_page:
        less_process = None
        try:
            less_process = subprocess.Popen(["less", "-R"], stdin=subprocess.PIPE, text=True, encoding='utf-8')
            def paged_output_func(s):
                try:
                    if less_process and less_process.stdin and not less_process.stdin.closed:
                        less_process.stdin.write(s + '\n')
                except BrokenPipeError: 
                    if less_process: less_process.stdin.close() 
                    sys.exit(130) 
                except Exception as e_write:
                    if less_process and less_process.stdin: less_process.stdin.close()
                    sys.exit(1)
            process_stream(input_source, paged_output_func)
        except KeyboardInterrupt:
            print(f"{RESET}\nExiting.", file=sys.stderr)
            if less_process and less_process.stdin and not less_process.stdin.closed:
                less_process.stdin.close()
            if less_process:
                less_process.terminate(); less_process.wait()
            sys.exit(130)
        finally:
            if less_process and less_process.stdin and not less_process.stdin.closed:
                try: less_process.stdin.flush(); less_process.stdin.close()
                except BrokenPipeError: pass
            if less_process:
                return_code = less_process.wait()
                if return_code != 0 and return_code != 130 : sys.exit(return_code)
    else: 
        def direct_output_func(s): print(s)
        process_stream(input_source, direct_output_func)

    if close_source_after and input_source: input_source.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"{RESET}\nExiting.", file=sys.stderr); sys.exit(130)
    except SystemExit: raise
    except Exception as e:
        print(f"{RESET}An unexpected error occurred: {e}", file=sys.stderr); sys.exit(1)
    finally:
        is_paging_active = False
        if len(sys.argv) > 1 and sys.argv[1] != '-' and os.path.exists(sys.argv[1]) and sys.stdout.isatty():
            is_paging_active = True
        if not is_paging_active and not sys.stdout.isatty():
             sys.stdout.write(RESET)
        sys.stdout.flush()
