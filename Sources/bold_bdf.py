#!/usr/bin/env python3
# bold_bdf.py

import os
import sys


def pick_files():
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()

        in_path = filedialog.askopenfilename(
            title="选择要加粗的 BDF 文件",
            filetypes=[("BDF 字体", "*.bdf *.txt"), ("所有文件", "*.*")]
        )
        if not in_path:
            return None, None

        default_out = os.path.splitext(in_path)[0] + "-bold.bdf"
        out_path = filedialog.asksaveasfilename(
            title="保存加粗后的字体",
            defaultextension=".bdf",
            initialfile=os.path.basename(default_out),
            initialdir=os.path.dirname(in_path) or ".",
            filetypes=[("BDF 字体", "*.bdf"), ("所有文件", "*.*")]
        )
        if not out_path:
            return None, None

        return in_path, out_path

    except Exception as e:
        print(f"[提示] 无法使用图形对话框（{e}），切换到命令行输入。")
        in_path = input("请输入 BDF 文件路径: ").strip().strip('"\'')
        if not in_path:
            return None, None
        default_out = os.path.splitext(in_path)[0] + "-bold.bdf"
        out_path = input(f"输出路径（回车使用 {default_out}）: ").strip().strip('"\'')
        if not out_path:
            out_path = default_out
        return in_path, out_path


def show_success(msg):
    print(msg)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("完成", msg)
        root.destroy()
    except Exception:
        pass


def show_error(msg):
    print(f"[错误] {msg}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("出错了", msg)
        root.destroy()
    except Exception:
        pass


# ---------- 核心算法（已支持任意位宽） ----------

def decode_row(hexstr, w):
    hexstr = hexstr.strip()
    nbytes = max(1, len(hexstr) // 2)
    total_bits = nbytes * 8
    val = int(hexstr, 16) if hexstr else 0
    return [(val >> (total_bits - 1 - i)) & 1 for i in range(w)]


def encode_row(bits, w):
    nbytes = (w + 7) // 8
    total_bits = nbytes * 8
    val = 0
    for i in range(min(w, len(bits))):
        if bits[i]:
            val |= 1 << (total_bits - 1 - i)
    return f"{val:0{nbytes * 2}X}"


def bold_bits(bits):
    w = len(bits)
    out = [0] * (w + 1)
    prev_end = None
    max_col = -1
    i = 0
    while i < w:
        if bits[i] == 0:
            i += 1
            continue
        s = i
        while i < w and bits[i] == 1:
            i += 1
        e = i - 1
        cs = s
        ce = e + 1
        if prev_end is not None:
            cs = max(cs, prev_end + 2)
        if cs <= ce:
            for j in range(cs, ce + 1):
                if j >= len(out):
                    out.extend([0] * (j - len(out) + 1))
                out[j] = 1
            prev_end = ce
            max_col = max(max_col, ce)
    return out, max_col


def process_char_block(lines):
    bbx_idx = bitmap_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("BBX "):
            bbx_idx = idx
        if line.strip() == "BITMAP":
            bitmap_idx = idx
            break
    assert bbx_idx is not None and bitmap_idx is not None
    parts = lines[bbx_idx].split()
    w, h, xoff, yoff = map(int, parts[1:5])
    bitmap = [lines[bitmap_idx + 1 + k].strip() for k in range(h)]
    rows = [decode_row(s, w) for s in bitmap]
    bold_rows = []
    max_end = -1
    for row in rows:
        out_bits, me = bold_bits(row)
        bold_rows.append(out_bits)
        max_end = max(max_end, me)
    wnew = max(w, max_end + 1)
    hexrows = []
    for out_bits in bold_rows:
        if len(out_bits) < wnew:
            out_bits = out_bits + [0] * (wnew - len(out_bits))
        else:
            out_bits = out_bits[:wnew]
        hexrows.append(encode_row(out_bits, wnew))
    lines[bbx_idx] = f"BBX {wnew} {h} {xoff} {yoff}"
    for k in range(h):
        lines[bitmap_idx + 1 + k] = hexrows[k]
    return lines, wnew


def convert(inp, outp):
    with open(inp, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    new_lines = []
    max_char_w = 0
    char_count = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("STARTCHAR"):
            j = i
            while j < len(lines) and not lines[j].startswith("ENDCHAR"):
                j += 1
            block = lines[i:j + 1]
            block, cw = process_char_block(block)
            max_char_w = max(max_char_w, cw)
            new_lines.extend(block)
            char_count += 1
            i = j + 1
        else:
            if line.startswith("FONT "):
                line = line.replace("Regular", "Bold")
            if line.startswith("WEIGHT_NAME"):
                line = 'WEIGHT_NAME "Bold"'
            new_lines.append(line)
            i += 1

    for idx, line in enumerate(new_lines):
        if line.startswith("FONTBOUNDINGBOX"):
            p = line.split()
            old_w, old_h, old_x, old_y = map(int, p[1:5])
            new_lines[idx] = f"FONTBOUNDINGBOX {max_char_w} {old_h} {old_x} {old_y}"
            break

    with open(outp, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")

    return char_count


def main():
    if len(sys.argv) == 3:
        in_path, out_path = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        in_path = sys.argv[1]
        out_path = os.path.splitext(in_path)[0] + "-bold.bdf"
    else:
        in_path, out_path = pick_files()

    if not in_path or not out_path:
        print("已取消。")
        return

    try:
        n = convert(in_path, out_path)
    except Exception as e:
        show_error(f"处理失败：\n{e}")
        sys.exit(1)

    show_success(
        f"加粗成功！\n"
        f"共处理 {n} 个字符\n"
        f"输出文件：\n{os.path.abspath(out_path)}"
    )


if __name__ == "__main__":
    main()