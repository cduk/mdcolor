#!/usr/bin/env python3

import sys
import re
import os
import subprocess # For running 'less'

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
ITALIC = "\033[3m"
DIM = "\033[2m"

# Colors ... (rest of the color definitions remain the same)
F_RED = "\033[31m"; F_GREEN = "\033[32m"; F_YELLOW = "\033[33m"; F_BLUE = "\033[34m"
F_MAGENTA = "\033[35m"; F_CYAN = "\033[36m"; F_WHITE = "\033[37m"; F_DEFAULT = "\033[39m"
F_B_RED = "\033[91m"; F_B_BLUE = "\033[94m"; F_B_YELLOW = "\033[93m"; F_B_CYAN = "\033[96m"
BG_BLACK_BRIGHT = "\033[100m"; BG_DEFAULT = "\033[49m"

STYLE = {
    "h1": BOLD + F_B_BLUE, "h2": BOLD + F_B_BLUE, "h3": BOLD + F_BLUE, "h4": BOLD + F_BLUE,
    "h5": BOLD + F_CYAN, "h6": BOLD + F_CYAN, "bold": BOLD, "italic": ITALIC + F_GREEN,
    "bold_italic": BOLD + ITALIC + F_B_RED, "inline_code_fg": F_B_YELLOW, "inline_code_bg": "",
    "code_block_fg": F_B_CYAN, "code_block_bg": BG_DEFAULT, "list_marker": F_MAGENTA,
    "blockquote_marker": ITALIC + F_YELLOW, "link_text": F_B_BLUE, "link_url": DIM + F_BLUE,
    "hr": DIM + F_WHITE,
}

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
    # ... (apply_styles function remains the same)
    line = re.sub(r'\*\*\*(.*?)\*\*\*', rf'{STYLE["bold_italic"]}\1{RESET}', line)
    line = re.sub(r'___(.*?)___', rf'{STYLE["bold_italic"]}\1{RESET}', line)
    line = re.sub(r'\*\*(.*?)\*\*', rf'{STYLE["bold"]}\1{RESET}', line)
    line = re.sub(r'__(.*?)__', rf'{STYLE["bold"]}\1{RESET}', line)
    line = re.sub(r'(?<!\*)\*(?!\*)(?!\s)(.+?)(?<!\s)\*(?!\*)', rf'{STYLE["italic"]}\1{RESET}', line)
    line = re.sub(r'(?<![a-zA-Z0-9_])_(?!_)(?!\s)(.+?)(?<!\s)_(?!_)(?![a-zA-Z0-9_])', rf'{STYLE["italic"]}\1{RESET}', line)
    line = re.sub(r'`(.*?)`', rf'{STYLE["inline_code_bg"]}{STYLE["inline_code_fg"]}\1{RESET}', line)
    line = re.sub(r'\[(.*?)\]\((.*?)\)', rf'{STYLE["link_text"]}[\1]{RESET}({STYLE["link_url"]}\2{RESET})', line)
    return line

def print_plain_code_block(lines, style_dict, output_func):
    for l in lines:
        output_func(f"{style_dict['code_block_bg']}{style_dict['code_block_fg']}{l}{RESET}")

def process_stream(input_stream, output_func):
    """
    Processes the markdown from input_stream and sends styled output to output_func.
    """
    in_code_block = False
    current_block_language = None
    code_block_lines = []

    terminal_columns = None
    # We get terminal size based on our script's stdout, even if it's piped to less.
    # This allows HR to be drawn correctly before sending to less.
    if sys.stdout.isatty():
        try:
            terminal_columns = os.get_terminal_size().columns
        except OSError: # In case of failure (e.g. some CI environments)
            terminal_columns = None


    for line_raw in input_stream:
        line = line_raw.rstrip('\n')
        fence_match = re.match(r'^```([^`\s]*)\s*$', line.strip())

        if fence_match:
            if in_code_block:
                in_code_block = False
                if code_block_lines:
                    code_to_highlight = "\n".join(code_block_lines)
                    lexer = None
                    if PYGMENTS_AVAILABLE:
                        if current_block_language:
                            try: lexer = get_lexer_by_name(current_block_language, stripall=True)
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
                            output_func(highlighted_code.rstrip('\n') + RESET) # No extra \n, let output_func handle
                        except Exception:
                            print_plain_code_block(code_block_lines, STYLE, output_func)
                    else:
                        print_plain_code_block(code_block_lines, STYLE, output_func)
                code_block_lines = []
                current_block_language = None
                output_func(line)
            else:
                in_code_block = True
                lang_specifier = fence_match.group(1)
                current_block_language = lang_specifier.lower() if lang_specifier else None
                output_func(line)
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        processed_line = line

        if re.fullmatch(r'^\s*(\---|___|\*\*\*)\s*$', processed_line.strip()):
            if terminal_columns:
                bar_char = "─"
                full_width_bar = bar_char * terminal_columns
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

def main():
    filename_arg = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print(f"Usage: {sys.argv[0]} [markdown_file]")
            print("Processes Markdown from file or stdin and outputs colorized text.")
            print("If a file is given and output is to a TTY, 'less -R -F' is used for paging.")
            print("Example: cat README.md | mdcolor")
            print("         mdcolor README.md")
            sys.exit(0)
        filename_arg = sys.argv[1]
        if filename_arg == '-': # Explicitly request stdin
            filename_arg = None


    input_source = None
    close_source_after = False
    should_page = False

    if filename_arg:
        if not os.path.exists(filename_arg):
            print(f"{RESET}Error: File not found: {filename_arg}", file=sys.stderr)
            sys.exit(1)
        try:
            input_source = open(filename_arg, 'r', encoding='utf-8')
            close_source_after = True
            if sys.stdout.isatty(): # Only page if output is to an interactive terminal
                should_page = True
        except Exception as e:
            print(f"{RESET}Error opening file {filename_arg}: {e}", file=sys.stderr)
            sys.exit(1)
    else: # No filename argument or filename was '-'
        input_source = sys.stdin
        # Don't automatically page if reading from stdin, user can pipe to less if they want
        should_page = False


    # Pygments availability notice (only if not reading from TTY, for piped input)
    if not sys.stdin.isatty() and filename_arg is None: # i.e. piped input
        if not PYGMENTS_AVAILABLE:
            print("Notice: Pygments library not found. Syntax highlighting for specific code block languages is disabled. Install with 'pip install pygments'. Code blocks will use basic coloring.", file=sys.stderr)

    if should_page:
        less_process = None
        try:
            # Start less process
            less_process = subprocess.Popen(["less", "-R", "-F"], stdin=subprocess.PIPE, text=True, encoding='utf-8')
            
            def paged_output_func(s):
                try:
                    if less_process and less_process.stdin and not less_process.stdin.closed:
                        less_process.stdin.write(s + '\n')
                except BrokenPipeError: # User quit less (e.g., pressed 'q')
                    # This exception means less has exited, so we should too.
                    # Closing stdin again might raise another error.
                    if less_process: less_process.stdin.close() # Attempt to close
                    sys.exit(130) # Standard exit code for SIGPIPE
                except Exception as e_write: # Other write errors
                    print(f"{RESET}Error writing to less: {e_write}", file=sys.stderr)
                    if less_process and less_process.stdin: less_process.stdin.close()
                    sys.exit(1)

            process_stream(input_source, paged_output_func)

        except KeyboardInterrupt: # Ctrl+C during processing before less is fully handling
            print(f"{RESET}\nExiting.", file=sys.stderr)
            if less_process and less_process.stdin and not less_process.stdin.closed:
                less_process.stdin.close()
            if less_process:
                less_process.terminate() # Ask less to terminate
                less_process.wait()      # Wait for it
            sys.exit(130)
        finally:
            if less_process and less_process.stdin and not less_process.stdin.closed:
                try:
                    less_process.stdin.flush()
                    less_process.stdin.close()
                except BrokenPipeError:
                    pass # less already exited
            if less_process:
                return_code = less_process.wait()
                # Exit with less's return code if it's non-zero (e.g. if less itself was Ctrl-C'd)
                # or if we exited due to BrokenPipeError (user quit less)
                if return_code != 0 and return_code != 130 :
                     sys.exit(return_code)

    else: # Not paging, print directly
        def direct_output_func(s):
            print(s)
        process_stream(input_source, direct_output_func)

    if close_source_after and input_source:
        input_source.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # This handles Ctrl+C if it happens very early in main() or if not paging
        print(f"{RESET}\nExiting.", file=sys.stderr)
        sys.exit(130) # Standard for SIGINT
    except SystemExit: # Allow sys.exit() to propagate
        raise
    except Exception as e: # Catch-all for unexpected errors
        print(f"{RESET}An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Final reset if outputting to a non-TTY and not paging
        # (Paging handles its own terminal state)
        # (If outputting to TTY and not paging, RESET is applied per line)
        is_paging = (len(sys.argv) > 1 and sys.argv[1] != '-' and os.path.exists(sys.argv[1]) and sys.stdout.isatty())
        if not is_paging and not sys.stdout.isatty():
             sys.stdout.write(RESET)
        sys.stdout.flush()
