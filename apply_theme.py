#!/usr/bin/env python3
"""把统一视觉规范挂到部署包上（只动 HTML 里的样式引用和占位标记，可重复执行）。

用法：
    python3 apply_theme.py /path/to/部署目录            # 挂上
    python3 apply_theme.py /path/to/部署目录 --revert   # 撤掉，HTML 恢复原样

做的事只有四件，全部带 gn-theme 标记，--revert 能原样撤回：
  1. 把 gn-theme.css / gn-screen.css 复制进部署目录；
  2. index.html：在 </head> 前加一行 <link>（排在内联 <style> 之后才压得住）；
  3. index.html：在 <div class="content"> 里最前面插入 AI 预留区（gn-ai-slot.html）；
  4. dash.html / shuju.html：加一行 <link>、在 <div id="app"></div> 后面插入同一段 AI 预留区，
     并把 CONFIG.colors 那 9 个配色值换成品牌色板
     （那段注释写明「配色均在下方 CONFIG 中修改」，只换颜色值，不碰任何取数逻辑）。

不会改 app.js、api.php、任何 .php，也不改 style.css。
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "gn-theme"

# 大屏配色：原霓虹色 → 品牌色板。必须跟 gn-screen.css 开头那组变量逐个对应。
SCREEN_COLORS = {
    "bg": "#ffffff",
    "cyan": "#1f2329",
    "purple": "#1d5fb8",
    "orange": "#4e5969",
    "magenta": "#e00012",
    "green": "#1a7f45",
    "red": "#e00012",
    "yellow": "#86909c",
    "blue": "#5b8fd6",
}


def read(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    return text, ("\r\n" if "\r\n" in text else "\n")


def write(path, text):
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def version_of(text):
    m = re.search(r'style\.css\?v=(\d+)', text) or re.search(r'app\.js\?v=(\d+)', text)
    return m.group(1) if m else "1"


def strip_marked(text):
    """撤掉所有带标记的插入块，并把换过的配色值还原。"""
    text = re.sub(r'[ \t]*<!-- %s:start -->.*?<!-- %s:end -->\r?\n?' % (MARK, MARK), "", text, flags=re.S)
    text = re.sub(r"'(#[0-9a-fA-F]{6})',?( *)/\* %s:was (#[0-9a-fA-F]{6}) \*/" % MARK,
                  lambda m: "'%s'," % m.group(3), text)
    return text


def block(body, nl):
    return "<!-- %s:start -->%s%s%s<!-- %s:end -->%s" % (MARK, nl, body.rstrip("\r\n"), nl, MARK, nl)


def add_link(text, nl, css, ver):
    link = '<link rel="stylesheet" href="%s?v=%s" />' % (css, ver)
    if "</head>" not in text:
        raise SystemExit("找不到 </head>，没法挂样式")
    return text.replace("</head>", block(link, nl) + "</head>", 1)


def add_ai_slot(text, nl, anchor='<div class="content">'):
    if anchor not in text:
        raise SystemExit('找不到 %s，AI 预留区没插进去' % anchor)
    with open(os.path.join(HERE, "gn-ai-slot.html"), encoding="utf-8") as f:
        slot = f.read().replace("\r\n", "\n").rstrip("\n").replace("\n", nl)
    at = text.index(anchor) + len(anchor)
    # 插在锚点所在行的下一行，这样 --revert 之后文件跟原来逐字节一致
    if text.startswith(nl, at):
        at += len(nl)
        return text[:at] + block(slot, nl) + text[at:]
    return text[:at] + nl + block(slot, nl) + text[at:]


def recolor_screen(text):
    m = re.search(r"colors:\s*\{(.*?)\}", text, flags=re.S)
    if not m:
        return text
    body = m.group(1)

    def swap(mm):
        key, old = mm.group(1), mm.group(2)
        new = SCREEN_COLORS.get(key)
        if not new or new.lower() == old.lower():
            return mm.group(0)
        return "%s: '%s', /* %s:was %s */" % (key, new, MARK, old)

    new_body = re.sub(r"(\w+):\s*'(#[0-9a-fA-F]{6})',", swap, body)
    return text[:m.start(1)] + new_body + text[m.end(1):]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    revert = "--revert" in sys.argv
    site = os.path.abspath(args[0] if args else ".")
    index = os.path.join(site, "index.html")
    if not os.path.isfile(index):
        raise SystemExit("这个目录里没有 index.html：" + site)

    for css in ("gn-theme.css", "gn-screen.css"):
        src, dst = os.path.join(HERE, css), os.path.join(site, css)
        if revert:
            if os.path.isfile(dst) and os.path.abspath(src) != dst:
                os.remove(dst)
        elif os.path.isfile(src) and os.path.abspath(src) != dst:
            shutil.copyfile(src, dst)

    text, nl = read(index)
    ver = version_of(text)
    text = strip_marked(text)
    if not revert:
        text = add_link(text, nl, "gn-theme.css", ver)
        text = add_ai_slot(text, nl)
    write(index, text)
    print(("已撤掉：" if revert else "已挂上：") + "index.html")

    for name in ("dash.html", "shuju.html"):
        path = os.path.join(site, name)
        if not os.path.isfile(path):
            continue
        text, nl = read(path)
        text = strip_marked(text)
        if not revert:
            text = add_link(text, nl, "gn-screen.css", ver)
            text = add_ai_slot(text, nl, '<div id="app"></div>')
            text = recolor_screen(text)
        write(path, text)
        print(("已撤掉：" if revert else "已挂上：") + name)


if __name__ == "__main__":
    main()
