#!/usr/bin/env python3

import sys
import re
import os
import subprocess

# ANSI escape codes
RESET = "\033[0m"; BOLD = "\033[1m"; ITALIC = "\033[3m"; DIM = "\033[2m"
F_RED = "\033[31m"; F_GREEN = "\033[32m"; F_YELLOW = "\033[33m"; F_BLUE = "\033[34m"
F_MAGENTA = "\033[35m"; F_CYAN = "\033[36m"; F_WHITE = "\033[37m"; F_DEFAULT = "\033[39m"
F_B_RED = "\033[91m"; F_B_BLUE = "\033[94m"; F_B_YELLOW = "\033[93m"; F_B_CYAN = "\033[96m"
BG_BLACK_BRIGHT = "\033[100m"; BG_DEFAULT = "\033[49m"
NORMAL_INTENSITY = "\033[22m"

# Unicode box drawing characters
H_LINE = "─"
V_LINE = "│"
TAG_OPEN_JUNC = "┤"
TAG_CLOSE_JUNC = "├"
CORNER_TL = "┌"
CORNER_BL = "└"

STYLE = {
    "h1": BOLD + F_B_BLUE, "h2": BOLD + F_B_BLUE, "h3": BOLD + F_BLUE, "h4": BOLD + F_BLUE,
    "h5": BOLD + F_CYAN, "h6": BOLD + F_CYAN,
    "bold": BOLD,
    "italic": ITALIC + F_GREEN,
    "bold_italic": BOLD + ITALIC + F_B_RED,
    "inline_code_fg": F_B_YELLOW, "inline_code_bg": "",
    "code_block_fg": F_B_CYAN, "code_block_bg": BG_DEFAULT,
    "list_marker": F_MAGENTA, "blockquote_marker": ITALIC + F_YELLOW,
    "link_text": F_B_BLUE, "link_url": DIM + F_BLUE, "hr": DIM + F_WHITE,
    "fence_bar": NORMAL_INTENSITY + DIM + F_WHITE,
    "fence_lang_tag": BOLD + F_B_YELLOW,
    "table_border": DIM + F_WHITE,
    "table_header": BOLD + F_B_BLUE,
    "table_cell": "",
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

def format_code_block_top_bar_partial(language_name, terminal_columns):
    """Formats the top bar for a partial box."""
    bar_style = STYLE.get("fence_bar", RESET)
    lang_style = STYLE.get("fence_lang_tag", RESET)
    effective_cols = terminal_columns if terminal_columns is not None else 80

    if effective_cols < 10: # Fallback
        return f"{bar_style}```{language_name or ''}{RESET}"

    if language_name:
        pre_junc_bar_text = CORNER_TL+H_LINE * 1
        styled_pre_junc_bar = f"{bar_style}{pre_junc_bar_text}"
        styled_junc = f"{bar_style}{TAG_OPEN_JUNC}" # "---┤"

        tag_text_raw = f"{language_name}"
        styled_tag_content_and_vline = f"{lang_style}{tag_text_raw}{bar_style}"

        fixed_prefix_len = len(pre_junc_bar_text) + 1 + len(tag_text_raw) + 1

        remaining_cols = effective_cols - fixed_prefix_len

        if remaining_cols < 0:
            available_for_tag_text = effective_cols - (len(pre_junc_bar_text) + 1 + 1 + 2) # "---┤" + "│" + "  " spaces
            if available_for_tag_text < 1: available_for_tag_text = 1

            truncated_lang = language_name.upper()[:available_for_tag_text]
            if len(language_name.upper()) > available_for_tag_text and available_for_tag_text > 2:
                truncated_lang = language_name.upper()[:available_for_tag_text-2] + ".."
            tag_text_raw = f" {truncated_lang} "
            styled_tag_content_and_vline = f"{lang_style}{tag_text_raw}{bar_style}"
            remaining_cols = 0 # No further H_LINEs

        #trailing_bar = H_LINE * max(0, remaining_cols)
        trailing_bar = ""
        return f"{styled_pre_junc_bar}{styled_junc}{styled_tag_content_and_vline}{bar_style}{trailing_bar}{RESET}"
    else: # No language name, simple open top bar
        return f"{bar_style}{CORNER_TL}{H_LINE +TAG_OPEN_JUNC}{RESET}"


def format_code_block_bottom_bar_partial(terminal_columns):
    """Formats the bottom bar for a partial box."""
    bar_style = STYLE.get("fence_bar", RESET)
    effective_cols = terminal_columns if terminal_columns is not None else 80
    if effective_cols < 1: return f"{bar_style}{RESET}"
    return f"{bar_style}{CORNER_BL}{H_LINE +TAG_OPEN_JUNC}{RESET}"

def format_code_block_content_line_partial(content_line, _terminal_columns, _max_content_width_ignored):
    """Formats a single line of code content with a left vertical bar."""
    bar_style = STYLE.get("fence_bar", RESET)

    return f"{bar_style}{V_LINE}{RESET} {content_line}"

def apply_styles(line):
    """Applies inline Markdown styles to a line of text. Order is important."""
    # --- PRE-PROCESSING FOR SPECIFIC NESTED CASES ---
    # Case 1: **_content_** (Bold asterisks, italic underscore)
    line = re.sub(r'\*\*(?P<ud>_)(?!_)(?!\s)(.+?)(?<!\s)(?P=ud)(?!_)\*\*', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)
    # Case 2: *__content__* (Italic asterisk, bold underscores)
    line = re.sub(r'\*(?P<ud>__)(?!_)(?!\s)(.+?)(?<!\s)(?P=ud)(?!_)\*', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)
    # Case 3: __*content*__ (Bold underscores, italic asterisk)
    line = re.sub(r'__(?P<ast>\*)(?!\*)(?!\s)(.+?)(?<!\s)(?P=ast)(?!\*)__', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)
    # Case 4: _**content**_ (Italic underscore, bold asterisks)
    line = re.sub(r'_(?P<ast>\*\*)(?!\*)(?!\s)(.+?)(?<!\s)(?P=ast)(?!\*)_', 
                  rf'{STYLE["bold_italic"]}\2{RESET}', line)

    # --- STANDARD BOLD ITALIC (*** and ___) ---
    line = re.sub(r'\*\*\*(?!\s)(.+?)(?<!\s)\*\*\*', rf'{STYLE["bold_italic"]}\1{RESET}', line)
    line = re.sub(r'___(?!\s)(.+?)(?<!\s)___', rf'{STYLE["bold_italic"]}\1{RESET}', line)

    # --- STANDARD BOLD (** and __) ---
    line = re.sub(r'\*\*(?!\s)(.+?)(?<!\s)\*\*', rf'{STYLE["bold"]}\1{RESET}', line)
    line = re.sub(r'__(?!\s)(.+?)(?<!\s)__', rf'{STYLE["bold"]}\1{RESET}', line)

    # --- STANDARD ITALIC (* and _) ---
    line = re.sub(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', rf'{STYLE["italic"]}\1{RESET}', line) 
    line = re.sub(r'(?<![a-zA-Z0-9_])_(?!_)(?!\s)(.+?)(?<!\s)_(?!_)(?![a-zA-Z0-9_])', rf'{STYLE["italic"]}\1{RESET}', line)
    
    # --- INLINE CODE & LINKS ---
    line = re.sub(r'`(.*?)`', rf'{STYLE["inline_code_bg"]}{STYLE["inline_code_fg"]}\1{RESET}', line)
    line = re.sub(r'\[(.*?)\]\((.*?)\)', rf'{STYLE["link_text"]}[\1]{RESET}({STYLE["link_url"]}\2{RESET})', line)
    return line

def print_plain_code_block(lines, style_dict, output_func):
    for l in lines:
        output_func(f"{style_dict['code_block_bg']}{style_dict['code_block_fg']}{l}{RESET}")

def format_fence_line(language_name, terminal_columns, is_opening=True):
    """Formats a fence line with a horizontal bar and language tag."""
    bar_style = STYLE.get("fence_bar", RESET)
    lang_style = STYLE.get("fence_lang_tag", RESET)

    # Default to terminal_columns if None, but ensure it's reasonable
    effective_cols = terminal_columns if terminal_columns is not None else 80 # Default if no tty

    if effective_cols < 20: # Fallback for very narrow
        raw_fence = "```"
        if is_opening and language_name:
            raw_fence += language_name
        return f"{bar_style}{raw_fence}{RESET}"

    if is_opening and language_name:
        tag_text = f" {language_name.upper()} "
        # Calculate visual length of styled tag (approximation, as styles add non-printing chars)
        # For simplicity, we use text length + 2 for bars. Real visual length is harder.
        styled_tag_inner = f"{lang_style}{tag_text}{bar_style}"
        styled_tag_full = f"{V_LINE}{styled_tag_inner}{V_LINE}"
        # Visual length of the tag part for layout calculation
        tag_visual_len = len(tag_text) + 2 # for V_LINEs

        bar_len_total = effective_cols - tag_visual_len

        if bar_len_total < 2:
            # Not enough space for bars around tag, make tag itself the focus
            # This might look a bit cramped, but it's better than overflowing or erroring.
            # Ensure the styled tag itself doesn't exceed terminal width
            if tag_visual_len > effective_cols:
                 # Truncate tag_text if too long, though this is an edge case
                max_tag_text_len = effective_cols - 4 # for | | and spaces
                if max_tag_text_len < 1: max_tag_text_len = 1
                tag_text = f" {language_name.upper()[:max_tag_text_len-2]}.. " # -2 for spaces
                styled_tag_inner = f"{lang_style}{tag_text}{bar_style}"
                styled_tag_full = f"{V_LINE}{styled_tag_inner}{V_LINE}"

            return f"{bar_style}{styled_tag_full}{RESET}".center(effective_cols, H_LINE)


        left_bar_len = bar_len_total // 2
        right_bar_len = bar_len_total - left_bar_len

        left_bar = H_LINE * left_bar_len
        right_bar = H_LINE * right_bar_len

        return f"{bar_style}{left_bar}{styled_tag_full}{right_bar}{RESET}"
    else: # Closing fence or no language
        return f"{bar_style}{H_LINE * effective_cols}{RESET}"

ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def visual_len(s):
    """Length of string excluding ANSI escape sequences."""
    return len(ANSI_RE.sub('', s))

def parse_table_row(line):
    """Parse a markdown table row into a list of cell texts. Returns None if not a table row."""
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        return None
    # Split on |, discard empty first/last from leading/trailing |
    cells = stripped.split('|')
    cells = [c.strip() for c in cells[1:-1]]
    return cells

def is_separator_row(line):
    """Check if a line is a markdown table separator like |---|:---:|---|."""
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        return False
    cells = stripped.split('|')
    cells = [c.strip() for c in cells[1:-1]]
    return all(re.fullmatch(r':?-{1,}:?', c) for c in cells) and len(cells) > 0

def parse_alignment(separator_line):
    """Parse column alignments from a separator row like |:---|:---:|---:|."""
    stripped = separator_line.strip()
    cells = stripped.split('|')
    cells = [c.strip() for c in cells[1:-1]]
    aligns = []
    for c in cells:
        if c.startswith(':') and c.endswith(':'):
            aligns.append('center')
        elif c.endswith(':'):
            aligns.append('right')
        else:
            aligns.append('left')
    return aligns

def pad_cell(text, width, align):
    """Pad cell text to given visual width with specified alignment."""
    vlen = visual_len(text)
    pad = max(0, width - vlen)
    if align == 'center':
        left = pad // 2
        right = pad - left
        return ' ' * left + text + ' ' * right
    elif align == 'right':
        return ' ' * pad + text
    else:
        return text + ' ' * pad

def wrap_ansi_text(text, width):
    """Wraps text into a list of strings of max `width`, preserving ANSI codes."""
    if width < 1: return [""]
    lines = []; curr_line = ""; curr_len = 0; active_ansi = []

    # Split text separating ANSI codes and whitespace, keeping all tokens
    tokens = re.split(r'(\033\[[0-9;]*m|\s+)', text)

    for token in tokens:
        if not token: continue

        # Track and apply ANSI sequences
        if token.startswith('\033['):
            if token == '\033[0m': active_ansi.clear()
            elif token not in active_ansi: active_ansi.append(token)
            curr_line += token
            continue

        # Handle whitespace safely
        if token.isspace():
            if curr_len + len(token) <= width and curr_len > 0:
                curr_line += token
                curr_len += len(token)
            continue

        vlen = visual_len(token)

        # Hard-wrap: If a single word is longer than the column width
        if vlen > width:
            if curr_len > 0: # Flush current line first
                lines.append(curr_line + "\033[0m")
                curr_line = "".join(active_ansi); curr_len = 0

            while len(token) > width:
                lines.append(curr_line + token[:width] + "\033[0m")
                token = token[width:]
                curr_line = "".join(active_ansi)

            curr_line += token
            curr_len = len(token)

        # Standard wrap: If adding this word exceeds width
        elif curr_len + vlen > width and curr_len > 0:
            lines.append(curr_line + "\033[0m")
            curr_line = "".join(active_ansi) + token
            curr_len = vlen
        else: # Fits perfectly
            curr_line += token
            curr_len += vlen

    if curr_line: lines.append(curr_line + "\033[0m")
    return lines if lines else [""]

def calculate_column_widths(styled_cells, num_cols, terminal_columns):
    """Calculates optimal column widths minimizing height without exceeding screen width."""
    term_width = terminal_columns if terminal_columns else 80
    max_widths = [0] * num_cols
    min_widths = [0] * num_cols

    for row in styled_cells:
        for j, cell in enumerate(row):
            max_widths[j] = max(max_widths[j], visual_len(cell))
            # Min width is the longest single word
            clean_text = ANSI_RE.sub('', cell)
            max_word = max((len(w) for w in clean_text.split()), default=0)
            min_widths[j] = max(min_widths[j], max_word)

    # Calculate overhead: borders (|) and padding spaces (2 per cell)
    overhead = (3 * num_cols) + 1 + (2 * num_cols)
    avail_width = max(10, term_width - overhead)

    # If natural content fits, return it as-is
    if sum(max_widths) <= avail_width:
        return max_widths

    # Content doesn't fit — distribute available space between min and max
    col_widths = list(min_widths)
    extra = avail_width - sum(col_widths)

    if extra < 0: # Extreme case: terminal is too small even for single words
        total_min = sum(min_widths) or 1
        return [max(1, int((w / total_min) * avail_width)) for w in min_widths]

    # Distribute remaining space based on "flex" (how much more space a column wants)
    flex = [max_widths[i] - min_widths[i] for i in range(num_cols)]
    total_flex = sum(flex)

    if total_flex > 0:
        for i in range(num_cols):
            col_widths[i] += int((flex[i] / total_flex) * extra)

        # Distribute any rounding remainder to the columns that wanted the most space
        remainder = avail_width - sum(col_widths)
        if remainder > 0:
            sorted_idx = sorted(range(num_cols), key=lambda x: flex[x], reverse=True)
            for i in range(remainder):
                col_widths[sorted_idx[i % num_cols]] += 1

    return col_widths

def render_table(rows, separator_idx, output_func, terminal_columns=None, wrap_tables=True):
    """Render a buffered markdown table with optimal column wrapping."""
    border_style = STYLE.get("table_border", RESET)
    header_style = STYLE.get("table_header", RESET)
    cell_style = STYLE.get("table_cell", RESET)

    data_rows = [r for i, r in enumerate(rows) if i != separator_idx]
    parsed = [parse_table_row(r) for r in data_rows]
    num_cols = max(len(r) for r in parsed) if parsed else 0

    if num_cols == 0:
        for r in rows: output_func(apply_styles(r))
        return

    # Normalize rows
    for i in range(len(parsed)):
        while len(parsed[i]) < num_cols: parsed[i].append('')

    aligns = parse_alignment(rows[separator_idx]) if 0 <= separator_idx < len(rows) else ['left'] * num_cols
    while len(aligns) < num_cols: aligns.append('left')

    has_header = separator_idx == 1 and len(data_rows) > 0

    # Apply styles to all cells first
    styled_cells = []
    for row in parsed:
        styled_cells.append([apply_styles(cell) for cell in row])

    # Calculate column widths
    if wrap_tables:
        col_widths = calculate_column_widths(styled_cells, num_cols, terminal_columns)
    else:
        col_widths = [0] * num_cols
        for row in styled_cells:
            for j, cell in enumerate(row):
                col_widths[j] = max(col_widths[j], visual_len(cell))

    # Build separator line
    sep_parts = []
    for j in range(num_cols):
        w = max(3, col_widths[j] + 2)
        a = aligns[j]
        if a == 'center': sep_parts.append(':' + '-' * max(1, w - 2) + ':')
        elif a == 'right': sep_parts.append('-' * max(1, w - 1) + ':')
        else: sep_parts.append('-' * w)
    sep_line = DIM + '|' + ('|'.join(sep_parts)) + '|' + RESET

    # Render rows
    for i, styled_row in enumerate(styled_cells):
        is_header_row = has_header and i == 0
        row_style = header_style if is_header_row else cell_style
        pipe_style = row_style if is_header_row else DIM

        if wrap_tables:
            # Wrap text in each cell of this row
            wrapped_cols = [wrap_ansi_text(cell, col_widths[j]) for j, cell in enumerate(styled_row)]
            max_lines = max((len(c) for c in wrapped_cols), default=1)

            for line_idx in range(max_lines):
                line = pipe_style + '|'
                for j in range(num_cols):
                    cell_text = wrapped_cols[j][line_idx] if line_idx < len(wrapped_cols[j]) else ""
                    padded = pad_cell(cell_text, col_widths[j], aligns[j])
                    line += row_style + ' ' + padded + ' ' + pipe_style + '|'
                line += RESET
                output_func(line)
        else:
            padded = [pad_cell(cell, col_widths[j], aligns[j]) for j, cell in enumerate(styled_row)]
            line = pipe_style + '|'
            line += (pipe_style + '|').join(
                (row_style + ' ' + padded[j] + ' ') for j in range(num_cols)
            )
            line += pipe_style + '|' + RESET
            output_func(line)

        if is_header_row:
            output_func(sep_line)

def process_stream(input_stream, output_func, wrap_tables=True, terminal_columns=None):
    in_code_block = False
    code_block_lines_buffer = []
    in_table = False
    table_row_buffer = []
    table_has_header = False

    for line_raw in input_stream:
        line = line_raw.rstrip('\n')
        stripped_line = line.strip()
        
        is_closing_fence = in_code_block and stripped_line == "```"
        opening_fence_match = None
        if not in_code_block:
            opening_fence_match = re.match(r'^```([^`\s]*)\s*$', stripped_line)

        if is_closing_fence or opening_fence_match:
            if in_code_block: # Closing a block
                in_code_block = False

                actual_opening_fence_line_raw = code_block_lines_buffer[0]
                content_lines_raw = code_block_lines_buffer[1:]

                lang_match = re.match(r'^```([^`\s]*)\s*$', actual_opening_fence_line_raw.strip())
                lang_for_highlighting = lang_match.group(1).lower() if lang_match and lang_match.group(1) else None

                if content_lines_raw:
                    code_to_highlight = "\n".join(content_lines_raw)
                    lexer = None
                    highlighted_lines_iter = None

                    if PYGMENTS_AVAILABLE:
                        if lang_for_highlighting:
                            try: lexer = get_lexer_by_name(lang_for_highlighting, stripall=True)
                            except ClassNotFound: pass
                        if not lexer:
                            try: lexer = guess_lexer(code_to_highlight, stripall=True)
                            except ClassNotFound: lexer = None
                    
                    if lexer:
                        try:
                            formatter = Terminal256Formatter(style='dracula')
                            highlighted_code_full = highlight(code_to_highlight, lexer, formatter)
                            highlighted_lines_iter = highlighted_code_full.rstrip('\n').split('\n')
                        except Exception:
                            highlighted_lines_iter = None
                    
                    if not highlighted_lines_iter:
                        fallback_style = STYLE.get("code_block_fg", "") + STYLE.get("code_block_bg", "")
                        highlighted_lines_iter = [f"{fallback_style}{cl}{RESET}" for cl in content_lines_raw]

                    for hl_line in highlighted_lines_iter:
                        output_func(format_code_block_content_line_partial(hl_line, terminal_columns, 0))
                
                #output_func(format_code_block_bottom_bar_partial(terminal_columns))
                code_block_lines_buffer = []
            else: # Opening a new block
                in_code_block = True
                lang_specifier = opening_fence_match.group(1)
                current_block_language_name = lang_specifier.lower() if lang_specifier else None

                output_func(format_code_block_top_bar_partial(current_block_language_name, terminal_columns))
                code_block_lines_buffer.append(line)
            continue

        if in_code_block:
            code_block_lines_buffer.append(line)
            continue

        # --- Table detection ---
        is_tbl_sep = is_separator_row(stripped_line)
        is_tbl_row = parse_table_row(stripped_line) is not None

        if is_tbl_sep or is_tbl_row:
            if not in_table:
                # Starting a new table
                in_table = True
                table_row_buffer = [line]
                table_has_header = is_tbl_row  # first row is header if it's data
            else:
                table_row_buffer.append(line)
            continue
        else:
            # Not a table line — flush any buffered table first
            if in_table:
                # Find separator row index
                sep_idx = -1
                for ti, tr in enumerate(table_row_buffer):
                    if is_separator_row(tr):
                        sep_idx = ti
                        break
                if sep_idx >= 0:
                    render_table(table_row_buffer, sep_idx, output_func, terminal_columns, wrap_tables)
                else:
                    # No separator found — not a valid table, render raw
                    for tr in table_row_buffer:
                        output_func(apply_styles(tr))
                in_table = False
                table_row_buffer = []

        # --- Standard Markdown processing ---

        # --- Standard Markdown processing ---
        processed_line = line # Use the original `line` for non-code-block processing
        if re.fullmatch(r'^\s*(\---|___|\*\*\*)\s*$', processed_line.strip()):
            if terminal_columns:
                bar_char = H_LINE
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
        
        # Default case: apply inline styles to the whole line
        output_func(apply_styles(processed_line))


    # After the loop, handle any pending code block (for streaming)
    if in_code_block and code_block_lines_buffer:
        actual_opening_fence_line_raw = code_block_lines_buffer[0]
        content_lines_raw = code_block_lines_buffer[1:]
        lang_match = re.match(r'^```([^`\s]*)\s*$', actual_opening_fence_line_raw.strip())
        lang_for_highlighting = lang_match.group(1).lower() if lang_match and lang_match.group(1) else None

        if content_lines_raw:
            code_to_highlight = "\n".join(content_lines_raw)
            lexer = None; highlighted_lines_iter = None
            if PYGMENTS_AVAILABLE:
                if lang_for_highlighting:
                    try: lexer = get_lexer_by_name(lang_for_highlighting, stripall=True)
                    except ClassNotFound: pass
                if not lexer:
                    try: lexer = guess_lexer(code_to_highlight, stripall=True)
                    except ClassNotFound: lexer = None
            if lexer:
                try:
                    formatter = Terminal256Formatter(style='dracula')
                    highlighted_code_full = highlight(code_to_highlight, lexer, formatter)
                    highlighted_lines_iter = highlighted_code_full.rstrip('\n').split('\n')
                except Exception: pass
            if not highlighted_lines_iter:
                fallback_style = STYLE.get("code_block_fg", "") + STYLE.get("code_block_bg", "")
                highlighted_lines_iter = [f"{fallback_style}{cl}{RESET}" for cl in content_lines_raw]
            for hl_line in highlighted_lines_iter:
                output_func(format_code_block_content_line_partial(hl_line, terminal_columns, 0))

        output_func(format_code_block_bottom_bar_partial(terminal_columns))

    # Handle any pending table at end of stream
    if in_table and table_row_buffer:
        sep_idx = -1
        for ti, tr in enumerate(table_row_buffer):
            if is_separator_row(tr):
                sep_idx = ti
                break
        if sep_idx >= 0:
            render_table(table_row_buffer, sep_idx, output_func, terminal_columns)
        else:
            for tr in table_row_buffer:
                output_func(apply_styles(tr))

def main():
    wrap_tables = True
    filename_arg = None

    args = sys.argv[1:]
    filtered_args = []
    for arg in args:
        if arg == '--no-wrap' or arg == '-w':
            wrap_tables = False
        elif arg == '--help' or arg == '-h':
            print(f"Usage: {sys.argv[0]} [--no-wrap|-w] [markdown_file]")
            print("Processes Markdown from file or stdin and outputs colorized text.")
            print("If a file is given and output is to a TTY, 'less -R' is used for paging.")
            print("  --no-wrap, -w  Disable table column wrapping")
            sys.exit(0)
        else:
            filtered_args.append(arg)

    if filtered_args:
        filename_arg = filtered_args[0]
        if filename_arg == '-':
            filename_arg = None

    input_source = None; close_source_after = False; should_page = False

    # Detect terminal width before stdout might be redirected to a pager
    terminal_columns = None
    try:
        terminal_columns = os.get_terminal_size().columns
    except OSError:
        terminal_columns = None

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

    if not sys.stdin.isatty() and filename_arg is None: # Piped input
        if not PYGMENTS_AVAILABLE:
            print(f"{RESET}Notice: Pygments library not found. Syntax highlighting for specific code block languages is disabled. Install with 'pip install Pygments'. Code blocks will use basic coloring.{RESET}", file=sys.stderr)

    if should_page:
        less_process = None
        try:
            less_process = subprocess.Popen(["less", "-R"], stdin=subprocess.PIPE, text=True, encoding='utf-8')
            def paged_output_func(s):
                try:
                    if less_process and less_process.stdin and not less_process.stdin.closed:
                        less_process.stdin.write(s + '\n')
                except BrokenPipeError: 
                    if less_process and less_process.stdin and not less_process.stdin.closed:
                         less_process.stdin.close()
                    sys.exit(130)
                except Exception: # Catch other write errors, less might have exited.
                    if less_process and less_process.stdin and not less_process.stdin.closed:
                         less_process.stdin.close()
                    # It's hard to know if less exited normally or due to an error on its side.
                    # We can't easily get its return code here if stdin write fails.
                    sys.exit(1) # Generic error
            process_stream(input_source, paged_output_func, wrap_tables, terminal_columns)
        except KeyboardInterrupt: # Ctrl+C during mdcolor processing before less takes over fully
            print(f"{RESET}\nExiting.", file=sys.stderr)
            if less_process and less_process.stdin and not less_process.stdin.closed:
                less_process.stdin.close()
            if less_process:
                less_process.terminate(); less_process.wait()
            sys.exit(130)
        finally:
            if less_process and less_process.stdin and not less_process.stdin.closed:
                try:
                    less_process.stdin.flush()
                    less_process.stdin.close()
                except BrokenPipeError: pass # less already exited
                except Exception: pass # Other errors on close
            if less_process:
                return_code = less_process.wait()
                # Exit with less's return code if it's non-zero (e.g. if less itself was Ctrl-C'd)
                # or if we exited due to BrokenPipeError (user quit less by pressing 'q')
                # SIGPIPE (13) often translates to exit code 141. Ctrl-C in less is often 130.
                if return_code != 0 and return_code != 130: # 130 for our own Ctrl+C handling
                     sys.exit(return_code)
    else: 
        def direct_output_func(s): print(s)
        process_stream(input_source, direct_output_func, wrap_tables, terminal_columns)

    if close_source_after and input_source: input_source.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt: # Handles Ctrl+C if it happens early in main or if not paging
        print(f"{RESET}\nExiting.", file=sys.stderr); sys.exit(130)
    except SystemExit: # Allow sys.exit() to propagate cleanly
        raise
    except Exception as e: # Catch-all for truly unexpected errors in main
        print(f"{RESET}An unexpected error occurred in main: {e}", file=sys.stderr); sys.exit(1)
    finally:
        # Final reset if outputting to a non-TTY and we weren't paging.
        # (Paging should handle its own terminal state on exit).
        # (If outputting to TTY and not paging, RESET is applied per line by output_func).
        is_paging_active = False
        if len(sys.argv) > 1 and sys.argv[1] != '-':
            # Check if filename_arg was valid and output is TTY
            # This check is a bit indirect; should_page from main would be better if accessible
            # For simplicity, assume if args and stdout is tty, paging might have been attempted
            if os.path.exists(sys.argv[1]) and sys.stdout.isatty():
                 is_paging_active = True

        if not is_paging_active and not sys.stdout.isatty():
             sys.stdout.write(RESET) # Ensure reset for piped non-paged output
        sys.stdout.flush()
