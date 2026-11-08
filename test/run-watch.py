"""Exercise the real Vroom compiler and Vim in disposable decks."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PERL = os.environ["VROOM_WATCH_PERL"]
COMPILER = ROOT / "util/vroom-watch-compile"
YS_BACKEND = os.environ.get("VROOM_TEST_BACKEND") == "ys"
VROOM_YS = ROOT / "repos/vroom/bin/vroom"
COMPILE = [str(VROOM_YS), "compile"] if YS_BACKEND else [PERL, str(COMPILER)]
START = [str(VROOM_YS)] if YS_BACKEND else [PERL, str(COMPILER), "--run"]


def line_runner(file, number):
    if YS_BACKEND:
        return [str(VROOM_YS), "line", file, number]
    return ["bash", str(ROOT / "vroom-slide-runner"), file, number]


def deck(second="Second\n+More\n+Last", third="Third"):
    config = (
        "---- config\n"
        "title: Watch fixture\nwidth: 80\nheight: 24\nbefore: 1\n"
        "vimrc: |\n  source ./vimrc\n"
    )
    # Vroom chooses filename width from the number of raw slide blocks.
    return (
        config + "---- skip\nPadding\n" * 8
        + "----\nFirst https://example.com\n"
        + f"----\n{second}\n"
        + (f"----\n{third}\n" if third is not None else "")
    )


BULLET_STEPS = (
    '== Title ^mint^ *bold title* tail\n\n* First ^mint^ tail\n  first wrap\n\n'
    '+* Second `code` tail\n  * Sub %peach% tail\n'
    '    sub wrap #gray# tail\n\n'
    '+* Third\n  * Final ^mint^ ^^bold^^ `code` ``bold code`` '
    '%peach% %%bold peach%% #gray# *strong* tail\n'
    '    final wrap https://example.com\n'
)


class RunWatchTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="run-watch-test-", dir=ROOT / ".cache"
        )
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        (self.directory / "vimrc").symlink_to(ROOT / "vimrc")
        (self.directory / "util").mkdir()
        for name in ("vroom-watch.vim", "vroom-watch-compile"):
            (self.directory / "util" / name).symlink_to(ROOT / "util" / name)
        self.source = self.directory / "slides.vroom"
        self.source.write_text(deck())
        self.compile()

    def compile(self, success=True):
        result = subprocess.run(
            COMPILE, cwd=self.directory,
            capture_output=True, text=True, timeout=15,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def manifest(self):
        return json.loads(
            (self.directory / ".cache/vroom-watch/manifest.json").read_text()
        )

    def vim(self, body, start="", watch=False, success=True):
        script = self.directory / "check.vim"
        script.write_text(
            "function! WaitFor(expression)\n"
            "  let started = reltime()\n"
            "  while !eval(a:expression)\n"
            "    if reltimefloat(reltime(started)) > 12\n"
            "      call assert_report('Timeout: ' . a:expression)\n"
            "      return\n"
            "    endif\n"
            "    sleep 100m\n"
            "  endwhile\n"
            "endfunction\n"
            "function! SaveDeck(lines)\n"
            "  call writefile(a:lines, 'slides.vroom')\n"
            "endfunction\n"
            "function! Generation()\n"
            "  return json_decode(join(readfile(\n"
            "        \\ '.cache/vroom-watch/manifest.json'), '\\n')).generation\n"
            "endfunction\n"
            "function! CheckPresentation()\n"
            "  try\n"
            + body
            + "\n  catch\n"
            "    call assert_report(v:exception . ' at ' . v:throwpoint)\n"
            "  endtry\n"
            "  call writefile(v:errors, 'errors.txt')\n"
            "  if !empty(v:errors)\n    cquit\n  endif\n  qa!\n"
            "endfunction\n"
            "autocmd VimEnter * ++nested call CheckPresentation()\n"
        )
        environment = dict(
            os.environ, VROOM_START_SLIDE=start,
            VROOM_WATCH="1" if watch else "",
        )
        result = subprocess.run(
            ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es",
             *self.manifest()["slides"], "-c", "source .vimrc", "-S", str(script)],
            cwd=self.directory, env=environment,
            capture_output=True, text=True, timeout=65,
        )
        errors = self.directory / "errors.txt"
        details = errors.read_text() if errors.exists() else result.stderr
        log = self.directory / ".cache/vroom-watch/build.log"
        if log.exists():
            details += "\nCompiler log:\n" + log.read_text()
        if success:
            self.assertEqual(result.returncode, 0, details)
        else:
            self.assertNotEqual(result.returncode, 0)

    def test_start_selection_and_bidirectional_navigation(self):
        for start in ("2", "002"):
            with self.subTest(start=start):
                self.vim("""
    call assert_equal('002', expand('%:t'))
    call assert_false(&l:wrap)
    call assert_equal('001', fnamemodify(argv(0), ':t'))
    previous
    call assert_equal('001', expand('%:t'))
    let row = search('https:', 'w')
    let column = match(getline(row), 'https:') + 1
    call assert_equal('https_url', synIDattr(synID(row, column, 1), 'name'))
    next
    normal ,
    call assert_equal('002z', expand('%:t'))
    previous
    call assert_equal('002b', expand('%:t'))
    normal ,
    call assert_equal('002z', expand('%:t'))
    normal ,
    call assert_equal('003', expand('%:t'))
    normal ,
    call assert_equal('003', expand('%:t'))
    call assert_false(&l:wrap)
    call assert_equal([], timer_info())
""", start=start)

    def test_comma_jumps_to_final_reveal_with_extension(self):
        self.source.write_text(deck().replace('----\nSecond',
                                             '---- python\nSecond'))
        self.compile()
        self.vim("""
    normal ,
    call assert_equal('002.py', expand('%:t'))
    normal ,
    call assert_equal('002z.py', expand('%:t'))
    previous
    call assert_equal('002b.py', expand('%:t'))
    normal ,
    call assert_equal('002z.py', expand('%:t'))
    normal ,
    call assert_equal('003', expand('%:t'))
""")

    def test_default_and_invalid_start(self):
        for start in ("", "0", "000"):
            self.vim("call assert_equal('001', expand('%:t'))", start=start)
        for start in ("bogus", "-1", "99"):
            self.vim("", start=start, success=False)

    def test_slide_twelve_is_not_argument_twelve(self):
        self.source.write_text(
            deck() + "".join(f"----\nSlide {number}\n" for number in range(4, 14))
        )
        self.compile()
        self.vim("""
    call assert_equal('012', expand('%:t'))
    previous
    call assert_equal('011', expand('%:t'))
    next
    call assert_equal('012', expand('%:t'))
    normal ,
    call assert_equal('013', expand('%:t'))
""", start="12")

    def test_demo_vim_does_not_inherit_presentation_settings(self):
        bindir = self.directory / "bin"
        bindir.mkdir()
        real_vim = shutil.which("vim")
        wrapper = bindir / "vim"
        wrapper.write_text(
            f"#!{sys.executable}\n"
            "import os, sys\n"
            f"vim = {real_vim!r}\n"
            "os.execv(vim, [vim, '-Nu', 'NONE', '-i', 'NONE', '-n', '-es',\n"
            "    '-c', 'source .vimrc', *sys.argv[1:],\n"
            "    '-S', 'demo-check.vim'])\n"
        )
        wrapper.chmod(0o755)
        (self.directory / "vimrc2").symlink_to(ROOT / "vimrc2")
        (self.directory / "demo.py").write_text("value = 1\n")
        (self.directory / "demo-check.vim").write_text(
            "function! CheckDemo()\n"
            "  call assert_equal('demo.py', argv(0))\n"
            "  call assert_true(&l:wrap)\n"
            "  call assert_equal('', $VROOM_START_SLIDE)\n"
            "  call assert_equal('', $VROOM_WATCH)\n"
            "  call assert_equal('', $VROOM_WATCH_PERL)\n"
            "  call assert_equal([], timer_info())\n"
            "  call writefile(v:errors, 'demo-errors.txt')\n"
            "  if !empty(v:errors)\n    cquit\n  endif\n  qa!\n"
            "endfunction\n"
            "autocmd VimEnter * ++nested call CheckDemo()\n"
        )
        environment = dict(
            os.environ, VROOM_START_SLIDE="12", VROOM_WATCH="1",
            VROOM_WATCH_PERL=PERL, TERM="xterm",
            PATH=str(bindir) + os.pathsep + os.environ["PATH"],
        )
        (self.directory / "demo-slide").write_text(
            "\x1b[22;38;5;121m$ vim\x1b[0m \x1b[22;38;5;153mdemo.py\x1b[0m\n"
        )
        result = subprocess.run(
            line_runner("demo-slide", "1"),
            cwd=self.directory, env=environment,
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.directory / "demo-errors.txt").read_text(), "")

    def test_compilation_failure_preserves_deck(self):
        old = self.manifest()
        original = (self.directory / "002").read_bytes()
        self.source.write_text("---- config\ntitle: [broken\n----\nBad\n")
        self.compile(success=False)
        self.assertEqual(old, self.manifest())
        self.assertEqual(original, (self.directory / "002").read_bytes())
        self.source.write_text(deck("Recovered"))
        self.compile()
        self.assertFalse((self.directory / "002b").exists())
        self.assertFalse((self.directory / "002z").exists())

    def test_direct_includes(self):
        self.source.write_text(deck() + "---- include extra.vroom\n")
        (self.directory / "extra.vroom").write_text("----\nIncluded\n")
        self.compile()
        self.assertIn("004", self.manifest()["slides"])

    def test_multiple_emphasis_spans_and_vim_colors(self):
        self.source.write_text(deck(
            "one ^two three^ four five ^six^ seven\n"
            "$ echo ^hello^ ^world^\n^$ echo all^\n"
            "^^ literal ^\n^cross\nline^"
        ))
        self.compile()
        content = (self.directory / "002").read_text()
        self.assertIn(
            "one \x1b[22;38;5;121mtwo three\x1b[0m four five "
            "\x1b[22;38;5;121msix\x1b[0m seven", content,
        )
        self.assertIn("^^ literal ^\n", content)
        self.assertIn("^cross\n", content)
        self.assertIn("line^\n", content)
        self.vim("""
    let row = search('two three', 'nw')
    let text = getline(row)
    for word in ['two three', 'six']
      let column = match(text, word) + 1
      call assert_equal('vroom_emphasis', synIDattr(synID(row, column, 1), 'name'))
    endfor
    let column = match(text, 'four five') + 1
    call assert_notequal('vroom_emphasis', synIDattr(synID(row, column, 1), 'name'))
    let column = match(text, nr2char(27)) + 1
    call assert_equal(1, synconcealed(row, column)[0])
    call assert_equal('121', synIDattr(hlID('vroom_emphasis'), 'fg', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_emphasis'), 'bold', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_emphasis'), 'bold', 'gui'))
    let row = search('hello', 'nw')
    let column = match(getline(row), 'hello') + 1
    call assert_equal('vroom_emphasis', synIDattr(synID(row, column, 1), 'name'))
    normal gg
    normal j
    call assert_true(getline('.') =~# 'hello')
    normal j
    call assert_true(getline('.') =~# 'echo all')
    normal k
    call assert_true(getline('.') =~# 'hello')
""", start="2")

    def test_emphasis_in_website(self):
        self.source.write_text(deck(
            "one ^two three^ four five ^six^ seven\n"
            "^<b>&text</b>^\n^https://example.com^\n^^ unmatched ^"
        ))
        result = subprocess.run(
            [os.environ["VROOM_WATCH_YS"], str(ROOT / "util/vroom-to-html.ys"),
             "slides.vroom", "site/index.html"],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / "site/index.html").read_text()
        self.assertIn(
            'one <strong class="emphasis">two three</strong> four five '
            '<strong class="emphasis">six</strong> seven', html,
        )
        self.assertIn(
            '<strong class="emphasis">&lt;b&gt;&amp;text&lt;/b&gt;</strong>',
            html,
        )
        self.assertIn(
            '<strong class="emphasis"><a href="https://example.com"', html
        )
        self.assertIn('^^ unmatched ^', html)
        self.assertNotIn('\x1b', html)

    def test_code_spans_and_vim_colors(self):
        self.source.write_text(deck(
            'one `two three` four ^five^ `^six^` seven\n'
            '`https://example.com ^literal^`\n'
            '^outer `inner` tail^\n'
            '$ echo `hello` and ^world^\n'
            'empty `` and ^^\nASCII ` glyph\n`cross\nline`'
        ))
        self.compile()
        content = (self.directory / '002').read_text()
        self.assertIn(
            'one \x1b[22;38;5;153mtwo three\x1b[0m four '
            '\x1b[22;38;5;121mfive\x1b[0m \x1b[22;38;5;153m^six^\x1b[0m seven',
            content,
        )
        self.assertIn(
            '\x1b[22;38;5;153mhttps://example.com ^literal^\x1b[0m', content
        )
        self.assertIn('\x1b[22;38;5;121mouter `inner` tail\x1b[0m', content)
        self.assertIn('empty `` and ^^\n', content)
        self.assertIn('ASCII ` glyph\n', content)
        self.assertIn('`cross\n', content)
        self.assertIn('line`\n', content)
        self.vim("""
    let row = search('two three', 'nw')
    let text = getline(row)
    for word in ['two three', 'six']
      let column = match(text, word) + 1
      call assert_equal('vroom_code', synIDattr(synID(row, column, 1), 'name'))
    endfor
    let column = match(text, 'five') + 1
    call assert_equal('vroom_emphasis', synIDattr(synID(row, column, 1), 'name'))
    let column = match(text, 'four') + 1
    call assert_notequal('vroom_code', synIDattr(synID(row, column, 1), 'name'))
    let column = match(text, nr2char(27)) + 1
    call assert_equal(1, synconcealed(row, column)[0])
    call assert_equal('153', synIDattr(hlID('vroom_code'), 'fg', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_code'), 'bold', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_code'), 'bold', 'gui'))
    for word in ['https:', 'hello']
      let row = search(word, 'nw')
      let column = match(getline(row), word) + 1
      call assert_equal('vroom_code', synIDattr(synID(row, column, 1), 'name'))
    endfor
""", start='2')

    def test_code_spans_in_website(self):
        self.source.write_text(deck(
            'one `two three` four ^five^ `^six^` seven\n'
            '`https://code.example.com <b>&text</b> ^literal^`\n'
            '^outer `inner` tail^\nempty `` and ^^\nASCII ` glyph'
        ))
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        self.assertIn(
            'one <code class="code-span">two three</code> four '
            '<strong class="emphasis">five</strong> '
            '<code class="code-span">^six^</code> seven', html,
        )
        self.assertIn(
            '<code class="code-span">https://code.example.com '
            '&lt;b&gt;&amp;text&lt;/b&gt; ^literal^</code>', html,
        )
        self.assertNotIn('<a href="https://code.example.com"', html)
        self.assertIn('<strong class="emphasis">outer `inner` tail</strong>', html)
        self.assertIn('empty `` and ^^', html)
        self.assertIn('ASCII ` glyph', html)
        self.assertIn(
            '.code-span { color: #afd7ff; font: inherit; font-weight: normal; }',
            html,
        )

    def test_gray_spans_and_slide_wrapping(self):
        marked = 'one #two three# four ^five^ `#six#` #seven# end'
        self.source.write_text(
            deck(marked + '\n#outer ^literal^ `code`#\n'
                 'empty ## unmatched #\n#cross\nline#\ncomment # stays')
            + '---- center\n' + marked + '\n'
        )
        self.compile()
        content = (self.directory / '002').read_text()
        self.assertIn('\x1b[22;38;5;250mtwo three\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;250mseven\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;153m#six#\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;250mouter ^literal^ `code`\x1b[0m', content)
        for literal in ('empty ## unmatched #', '#cross', 'line#', 'comment # stays'):
            self.assertIn(literal, content)
        centered = (self.directory / '004').read_text()
        for sequence in ('\x1b[22;38;5;250m', '\x1b[22;38;5;153m',
                         '\x1b[22;38;5;121m', '\x1b[0m'):
            centered = centered.replace(sequence, '')
        visible = 'one two three four five #six# seven end'
        self.assertIn(' ' * ((80 - len(visible)) // 2) + visible, centered.splitlines())
        self.vim("""
    call assert_false(&l:wrap)
    let row = search('two three', 'nw')
    let text = getline(row)
    for word in ['two three', 'seven']
      let column = match(text, word) + 1
      call assert_equal('vroom_comment', synIDattr(synID(row, column, 1), 'name'))
    endfor
    let column = match(text, 'six') + 1
    call assert_equal('vroom_code', synIDattr(synID(row, column, 1), 'name'))
    let column = match(text, nr2char(27)) + 1
    call assert_equal(1, synconcealed(row, column)[0])
    call assert_equal('250', synIDattr(hlID('vroom_comment'), 'fg', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_comment'), 'bold', 'cterm'))
    edit slides.vroom
    call assert_true(&l:wrap)
""", start='2')

    def test_gray_spans_in_website(self):
        self.source.write_text(deck(
            'one #two three# four ^five^ `#six#` #seven# end\n'
            '#outer ^literal^ `code`#\n'
            '#https://gray.example.com#\n#<b>&text</b>#\n'
            'empty ## unmatched #\ncomment # stays\n'
            'https://docs.example.com/#anchor'
        ))
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        self.assertIn(
            'one <span class="comment-span">two three</span> four '
            '<strong class="emphasis">five</strong> '
            '<code class="code-span">#six#</code> '
            '<span class="comment-span">seven</span> end', html,
        )
        self.assertIn('<span class="comment-span">outer ^literal^ `code`</span>', html)
        self.assertIn('<span class="comment-span">&lt;b&gt;&amp;text&lt;/b&gt;</span>', html)
        self.assertIn('<span class="comment-span"><a href="https://gray.example.com"', html)
        self.assertIn('empty ## unmatched #', html)
        self.assertIn('comment # stays', html)
        self.assertIn('<a href="https://docs.example.com/#anchor"', html)

    def test_yellow_spans_and_vim_colors(self):
        self.source.write_text(
            deck('@first@ and @second@ with `@literal@`\n'
                 '^outer @literal@ tail^\nempty @@ unmatched @')
            + '---- center\n@one@ and @two words@\n'
            + '----\n* Earlier\n+* Last @yellow@ tail\n'
        )
        self.compile()
        content = (self.directory / '002').read_text()
        self.assertIn('\x1b[22;38;5;229mfirst\x1b[0m and '
                      '\x1b[22;38;5;229msecond\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;153m@literal@\x1b[0m', content)
        self.assertIn('outer @literal@ tail', content)
        self.assertIn('empty @@ unmatched @', content)
        centered = re.sub(r'\x1b\[[0-9;]*m', '',
                          (self.directory / '004').read_text())
        visible = 'one and two words'
        self.assertIn(' ' * ((80 - len(visible)) // 2) + visible,
                      centered.splitlines())
        self.vim("""
    let row = search('first', 'nw')
    for word in ['first', 'second']
      let column = match(getline(row), word) + 1
      call assert_equal('vroom_yellow',
            \\ synIDattr(synID(row, column, 1), 'name'))
    endfor
    call assert_equal('229', synIDattr(hlID('vroom_yellow'), 'fg', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_yellow'), 'bold', 'cterm'))
""", start='2')
        self.vim("""
    normal ,
    let row = search('yellow', 'nw')
    let column = match(getline(row), 'yellow') + 1
    call assert_equal('vroom_yellow_underlined',
          \\ synIDattr(synID(row, column, 1), 'name'))
""", start='5')

    def test_yellow_spans_in_website(self):
        self.source.write_text(deck(
            '@first@ and @second@ with `@literal@`\n'
            '^outer @literal@ tail^\nempty @@ unmatched @\n'
            '@https://example.com@\n@<b>&text</b>@'
        ))
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        self.assertIn('<span class="yellow-span">first</span> and '
                      '<span class="yellow-span">second</span>', html)
        self.assertIn('<code class="code-span">@literal@</code>', html)
        self.assertIn('outer @literal@ tail', html)
        self.assertIn('empty @@ unmatched @', html)
        self.assertIn('<span class="yellow-span"><a href="https://example.com"',
                      html)
        self.assertIn('<span class="yellow-span">&lt;b&gt;&amp;text&lt;/b&gt;</span>',
                      html)
        self.assertIn('color: #ffffaf; font-weight: normal;', html)

    def test_peach_spans_and_note_titles(self):
        self.source.write_text(
            deck('%first% and %second% with ^green^ and `100% %literal%`\n'
                 '% Legacy note title\n100% literal\nempty %% unmatched %\n'
                 '====\nNotes\n%notes span%')
            + '---- center\n%first% and %second%\n'
        )
        self.compile()
        content = (self.directory / '002').read_text()
        self.assertIn('\x1b[22;38;5;216mfirst\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;216msecond\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;121mgreen\x1b[0m', content)
        self.assertIn('\x1b[22;38;5;153m100% %literal%\x1b[0m', content)
        self.assertIn('100% literal', content)
        self.assertIn('empty %% unmatched %', content)
        self.assertNotIn('Legacy note title', content)
        self.assertNotIn('\x00', content)
        notes = (self.directory / 'notes.txt').read_text()
        self.assertIn('Legacy note title', notes)
        self.assertIn('%notes span%', notes)
        self.assertNotIn('\x00', notes)
        centered = (self.directory / '004').read_text()
        centered = centered.replace('\x1b[22;38;5;216m', '').replace('\x1b[0m', '')
        visible = 'first and second'
        self.assertIn(' ' * ((80 - len(visible)) // 2) + visible, centered.splitlines())
        self.vim("""
    let row = search('first', 'nw')
    let text = getline(row)
    for word in ['first', 'second']
      let column = match(text, word) + 1
      call assert_equal('vroom_accent', synIDattr(synID(row, column, 1), 'name'))
    endfor
    call assert_equal('216', synIDattr(hlID('vroom_accent'), 'fg', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_accent'), 'bold', 'cterm'))
    let column = match(text, nr2char(27)) + 1
    call assert_equal(1, synconcealed(row, column)[0])
""", start='2')

    def test_peach_spans_in_website(self):
        self.source.write_text(deck(
            '%first% and %second% with ^green^ and `100% %literal%`\n'
            '% Legacy note title\n100% literal\nempty %% unmatched %\n'
            '%https://peach.example.com%\n%<b>&text</b>%'
        ))
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        self.assertIn(
            '<span class="accent-span">first</span> and '
            '<span class="accent-span">second</span> with '
            '<strong class="emphasis">green</strong> and '
            '<code class="code-span">100% %literal%</code>', html,
        )
        self.assertNotIn('Legacy note title', html)
        self.assertIn('100% literal', html)
        self.assertIn('empty %% unmatched %', html)
        self.assertIn('<span class="accent-span">&lt;b&gt;&amp;text&lt;/b&gt;</span>', html)
        self.assertIn('<span class="accent-span"><a href="https://peach.example.com"', html)
        for color in ('#87ffaf', '#afd7ff', '#ffaf87'):
            self.assertIn(color, html)

    def test_peach_spans_refresh_in_watch_mode(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    let original = readfile('slides.vroom')
    let updated = map(copy(original),
          \\ 'substitute(v:val, "Second", "%first% and %second%", "")')
    call SaveDeck(updated)
    call WaitFor('search("first", "nw") > 0')
    let row = search('second', 'nw')
    let column = match(getline(row), 'second') + 1
    call assert_equal('vroom_accent', synIDattr(synID(row, column, 1), 'name'))
    call assert_equal(2, count(getline(row), nr2char(27) . '[22;38;5;216m'))
""", start='2', watch=True)

    def test_current_bullet_blocks_and_final_underline(self):
        self.source.write_text(deck(BULLET_STEPS, '* Single bullet'))
        self.compile()
        frames = [(self.directory / name).read_text()
                  for name in ('002', '002b', '002z')]
        white = '\x1b[1;38;5;231m'
        underlined = '\x1b[1;4;38;5;231m'
        self.assertEqual(
            [len(frame.splitlines()) for frame in frames], [25, 25, 24]
        )
        self.assertIn(white + '* First ', frames[0])
        self.assertIn('  ' + white + 'first wrap', frames[0])
        self.assertNotIn(underlined, frames[0])
        self.assertNotIn(white + '* First ', frames[1])
        for text in ('* Second ', '* Sub ', 'sub wrap '):
            self.assertIn(white + text, frames[1])
        self.assertNotIn(underlined, frames[1])
        self.assertNotIn(white + '* Second ', frames[2])
        self.assertIn(white + '* Third', frames[2])
        self.assertIn(underlined + '* Final ', frames[2])
        self.assertIn(underlined + 'final wrap ', frames[2])
        self.assertIn('\x1b[0m' + underlined
                      + ' \x1b[1mstrong\x1b[1m tail', frames[2])
        for color in (121, 153, 216, 250):
            self.assertIn(f'\x1b[22;4;38;5;{color}m', frames[2])
        for color in (121, 153, 216):
            self.assertIn(f'\x1b[1;4;38;5;{color}m', frames[2])
        self.assertNotIn(white, (self.directory / '003').read_text())
        self.assertNotIn(underlined, (self.directory / '003').read_text())
        self.vim("""
    let row = search('Title', 'nw')
    let text = getline(row)
    for word in ['Title', 'tail']
      let column = match(text, word) + 1
      let group = synIDattr(synID(row, column, 1), 'name')
      call assert_equal('vroom_heading', group)
    endfor
    let column = match(text, 'mint') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_emphasis', group)
    let column = match(text, 'bold title') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_bold_heading', group)
    call assert_equal('225', synIDattr(hlID(group), 'fg', 'cterm'))
    call assert_equal('225', synIDattr(hlID('vroom_heading'), 'fg', 'cterm'))
    call assert_equal('', synIDattr(hlID('vroom_heading'), 'bold', 'cterm'))
    let row = search('First', 'nw')
    let column = match(getline(row), 'First') + 1
    call assert_equal('vroom_current', synIDattr(synID(row, column, 1), 'name'))
    let column = match(getline(row), 'mint') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_emphasis', group)
    let column = match(getline(row), 'tail') + 1
    call assert_equal('vroom_current', synIDattr(synID(row, column, 1), 'name'))
    call assert_equal('231', synIDattr(hlID('vroom_current'), 'fg', 'cterm'))
    call assert_equal('1', synIDattr(hlID('vroom_current'), 'bold', 'cterm'))
    next
    next
    let row = search('Final', 'nw')
    let text = getline(row)
    syntax match vroom_final /^\\s*\\e\\[1;4;38;5;231m.*$/
    call VroomHighlight()
    for column in range(1, match(text, nr2char(27)))
      let group = synIDtrans(synID(row, column, 1))
      call assert_notequal('1', synIDattr(group, 'underline', 'cterm'))
    endfor
    for [word, group] in [
          \\ ['Final', 'vroom_final'], ['tail', 'vroom_final'],
          \\ ['mint', 'vroom_emphasis_underlined'],
          \\ ['bold', 'vroom_emphasis_bold_underlined'],
          \\ ['code', 'vroom_code_underlined'],
          \\ ['bold code', 'vroom_code_bold_underlined'],
          \\ ['peach', 'vroom_accent_underlined'],
          \\ ['bold peach', 'vroom_accent_bold_underlined'],
          \\ ['gray', 'vroom_comment_underlined']]
      let column = match(text, word) + 1
      call assert_equal(group, synIDattr(synID(row, column, 1), 'name'), word)
      call assert_equal('1', synIDattr(hlID(group), 'underline', 'cterm'), word)
    endfor
    let column = match(text, 'strong') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_bold_final', group)
    call assert_equal('1', synIDattr(hlID(group), 'underline', 'cterm'))
    let column = 1
    while column <= len(text)
      if text[column - 1] ==# nr2char(27)
        call assert_equal(1, synconcealed(row, column)[0])
      endif
      let column += 1
    endwhile
    let row = search('final wrap', 'nw')
    let group = synIDtrans(synID(row, 1, 1))
    call assert_notequal('1', synIDattr(group, 'underline', 'cterm'))
    let column = match(getline(row), 'https:') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_final_url', group)
    previous
    let row = search('Second', 'nw')
    let column = match(getline(row), 'Second') + 1
    call assert_equal('vroom_current', synIDattr(synID(row, column, 1), 'name'))
""", start='2')

    def test_bullet_cues_match_website(self):
        self.source.write_text(
            deck(BULLET_STEPS, '* Single bullet')
            + '----\n* Continue\n+  continued\n+$ echo OK\n'
            + '---- replace\n* Old\n+* Old\n* New\n  wrapped\n+No bullets\n'
        )
        self.compile()
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        sections = [
            ET.fromstring(section.replace(' hidden>', ' hidden="hidden">'))
            for section in re.findall(r'<section\b.*?</section>', html, re.S)
        ]
        frames = [section for section in sections
                  if section.attrib['data-slide'] == '2']
        filenames = self.manifest()['slides']
        self.assertEqual(len(sections), len(filenames))
        for section, filename in zip(sections, filenames):
            rows = list(section.find('pre'))
            terminal = (self.directory / filename).read_text().splitlines()
            styles = (('current-bullet', r'\x1b\[1;(?:4;)?38;5;231m'),
                      ('last-bullet', r'\x1b\[1;4;38;5;231m'))
            for style, marker in styles:
                expected = [re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
                            for line in terminal if re.search(marker, line)]
                actual = [''.join(row.itertext()).strip() for row in rows
                          if style in row.attrib['class'].split()]
                self.assertEqual(actual, expected, (filename, style))
        final = frames[-1]
        marked = [row for row in final.find('pre')
                  if 'last-bullet' in row.attrib['class']]
        self.assertEqual(len(marked), 2)
        self.assertTrue(''.join(marked[0].itertext()).startswith('* Final '))
        self.assertIn('<code class="code-span">code</code>', html)
        self.assertIn('<strong class="emphasis bold">bold</strong>', html)
        self.assertIn('.current-bullet { color: #ffffff; font-weight: bold; }', html)
        self.assertIn('.last-bullet { text-decoration: underline; }', html)
        self.assertIn('.heading { color: #ffafff; }', html)
        heading = frames[0].find('pre').find("span[@class='line heading']")
        self.assertEqual(''.join(heading.itertext()), 'Title mint bold title tail')
        single = next(section for section in sections
                      if section.attrib['data-slide'] == '3')
        self.assertNotIn('current-bullet', ET.tostring(single).decode())

    def test_continuation_and_nonbullet_reveals(self):
        self.source.write_text(deck('* First\n+  continuation\n+$ echo OK'))
        self.compile()
        final = (self.directory / '002z').read_text()
        self.assertIn('\x1b[1;4;38;5;231m* First\x1b[0m', final)
        self.assertIn('  \x1b[1;4;38;5;231mcontinuation\x1b[0m', final)
        self.assertIn('          $ echo OK\n', final)
        self.assertNotIn(';4;', (self.directory / '002b').read_text())

    def test_replace_reveals_restart_bullet_cues(self):
        self.source.write_text(
            deck('* Old\n+* Old\n* New\n  wrapped\n+No bullets').replace(
                '----\n* Old', '---- replace\n* Old'
            )
        )
        self.compile()
        middle = (self.directory / '002b').read_text()
        self.assertEqual(middle.count('Old'), 1)
        self.assertIn('\x1b[1;38;5;231m* Old', middle)
        self.assertIn('\x1b[1;38;5;231m* New', middle)
        self.assertIn('\x1b[1;38;5;231mwrapped', middle)
        self.assertNotIn('\x1b', (self.directory / '002z').read_text())

    def test_bullet_cues_refresh_when_reveals_change(self):
        self.source.write_text(deck('* One\n+* Two ^mint^'))
        self.compile()
        self.vim("""
    next
    let row = search('Two', 'nw')
    call assert_match(';4;', getline(row))
    let g:generation = Generation()
    let source = readfile('slides.vroom')
    let index = index(source, '+* Two ^mint^')
    call insert(source, '+* Three `code`', index + 1)
    call SaveDeck(source)
    call WaitFor('Generation() !=# g:generation')
    call WaitFor("expand('%:t') ==# '002b'")
    let row = search('Two', 'nw')
    call assert_notmatch(';4;', getline(row))
    let column = match(getline(row), 'Two') + 1
    call assert_equal('vroom_current', synIDattr(synID(row, column, 1), 'name'))
    next
    let row = search('Three', 'nw')
    let column = match(getline(row), 'Three') + 1
    call assert_equal('vroom_final', synIDattr(synID(row, column, 1), 'name'))
    let g:generation = Generation()
    let source = filter(source, 'v:val !=# "+* Two ^mint^"')
    let source = filter(source, 'v:val !=# "+* Three `code`"')
    call SaveDeck(source)
    call WaitFor('Generation() !=# g:generation')
    call WaitFor("expand('%:t') ==# '002'")
    call assert_notmatch(nr2char(27), join(getline(1, '$'), "\\n"))
""", start='2', watch=True)

    def test_asterisk_bold_spans(self):
        self.source.write_text(
            deck('* Bullet *first* and *second* tail\n'
                 'plain *bold words* after\n'
                 '$ echo *argument* after\n'
                 'https://example.com/*path*\n'
                 '`*literal*` ^*also literal*^\n'
                 'empty ** unmatched * and spaced * word* 2 * 3 * 4')
            + '---- center\none *two three* four\n'
        )
        self.compile()
        content = (self.directory / '002').read_text()
        self.assertIn('* Bullet \x1b[1mfirst\x1b[22m and '
                      '\x1b[1msecond\x1b[22m tail', content)
        self.assertIn('plain \x1b[1mbold words\x1b[22m after', content)
        self.assertIn('*literal*', content)
        self.assertIn('*also literal*', content)
        self.assertIn('empty ** unmatched * and spaced * word* 2 * 3 * 4', content)
        centered = re.sub(r'\x1b\[[0-9;]*m', '',
                          (self.directory / '004').read_text())
        visible = 'one two three four'
        self.assertIn(' ' * ((80 - len(visible)) // 2) + visible,
                      centered.splitlines())
        self.vim("""
    let row = search('Bullet', 'nw')
    for word in ['first', 'second']
      let column = match(getline(row), word) + 1
      let group = synIDattr(synID(row, column, 1), 'name')
      call assert_equal('vroom_bold', group)
      call assert_equal('1', synIDattr(hlID(group), 'bold', 'cterm'))
    endfor
    let column = match(getline(row), 'tail') + 1
    let group = synIDtrans(synID(row, column, 1))
    call assert_notequal('1', synIDattr(group, 'bold', 'cterm'))
    let row = search('argument', 'nw')
    let column = match(getline(row), 'argument') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_bold_command', group)
    let row = search('https:', 'nw')
    let column = match(getline(row), 'path') + 1
    let group = synIDattr(synID(row, column, 1), 'name')
    call assert_equal('vroom_bold_url', group)
""", start='2')
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        self.assertIn('* Bullet <strong class="bold">first</strong> and '
                      '<strong class="bold">second</strong> tail', html)
        self.assertIn('<code class="code-span">*literal*</code>', html)
        self.assertIn('empty ** unmatched * and spaced * word* 2 * 3 * 4', html)

    def test_bold_spans_and_vim_weights(self):
        marked = ('^regular green^ ^^bold green^^ `regular code` ``bold code`` '
                  '%regular peach% %%bold peach%%')
        self.source.write_text(
            deck('== ' + marked + '\n'
                 '^^outer ^inner^ tail^^\n``outer `inner` #literal#``\n'
                 '%%outer %inner% tail%%\n'
                 '$ echo ^^command^^ ``argument`` %%option%%\n'
                 'empty ```` ^^^^ %%%% ##\n^^cross\nline^^')
            + '---- center\n' + marked + '\n'
        )
        self.compile()
        content = (self.directory / '002').read_text()
        for color, name in ((121, 'green'), (153, 'code'), (216, 'peach')):
            self.assertIn(f'\x1b[1;38;5;{color}mbold {name}\x1b[0m', content)
            self.assertIn(f'\x1b[22;38;5;{color}mregular {name}\x1b[0m', content)
        self.assertIn('\x1b[1;38;5;121mouter ^inner^ tail\x1b[0m', content)
        self.assertIn('\x1b[1;38;5;153mouter `inner` #literal#\x1b[0m', content)
        self.assertIn('\x1b[1;38;5;216mouter %inner% tail\x1b[0m', content)
        self.assertIn('empty ```` ^^^^ %%%% ##', content)
        self.assertIn('^^cross\n', content)
        self.assertIn('line^^\n', content)
        centered = (self.directory / '004').read_text()
        for color in (121, 153, 216):
            for weight in (1, 22):
                centered = centered.replace(f'\x1b[{weight};38;5;{color}m', '')
        centered = centered.replace('\x1b[0m', '')
        visible = ('regular green bold green regular code bold code '
                   'regular peach bold peach')
        self.assertIn(' ' * ((80 - len(visible)) // 2) + visible, centered.splitlines())
        self.vim("""
    let row = search('bold green', 'nw')
    let text = getline(row)
    for [word, group, color] in [
          \\ ['green', 'vroom_emphasis', '121'],
          \\ ['code', 'vroom_code', '153'],
          \\ ['peach', 'vroom_accent', '216']]
      for prefix in ['regular ', 'bold ']
        let column = match(text, prefix . word) + 1
        let expected = group . (prefix ==# 'bold ' ? '_bold' : '')
        call assert_equal(expected, synIDattr(synID(row, column, 1), 'name'))
      endfor
      call assert_equal(color, synIDattr(hlID(group . '_bold'), 'fg', 'cterm'))
      call assert_equal('1', synIDattr(hlID(group . '_bold'), 'bold', 'cterm'))
      call assert_equal('1', synIDattr(hlID(group . '_bold'), 'bold', 'gui'))
      call assert_equal('', synIDattr(hlID(group), 'bold', 'cterm'))
    endfor
    let column = match(text, nr2char(27)) + 1
    call assert_equal(1, synconcealed(row, column)[0])
    let row = search('command', 'nw')
    for [word, group] in [
          \\ ['command', 'vroom_emphasis_bold'],
          \\ ['argument', 'vroom_code_bold'],
          \\ ['option', 'vroom_accent_bold']]
      let column = match(getline(row), word) + 1
      call assert_equal(group, synIDattr(synID(row, column, 1), 'name'))
    endfor
""", start='2')

    def test_bold_spans_in_website(self):
        self.source.write_text(deck(
            '%%peach%% and %regular peach%\n% Legacy note title\n'
            '^^mint^^ ^regular mint^ ``code`` `regular code`\n'
            '^^outer ^inner^ tail^^ ``outer `inner` <b>&text</b>``\n'
            '%%outer %inner% tail%%\nempty ```` ^^^^ %%%% ##'
        ))
        result = subprocess.run(
            [os.environ['VROOM_WATCH_YS'], str(ROOT / 'util/vroom-to-html.ys'),
             'slides.vroom', 'site/index.html'],
            cwd=self.directory, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.directory / 'site/index.html').read_text()
        for element, kind, text in (
            ('strong', 'emphasis', 'mint'),
            ('code', 'code-span', 'code'),
            ('span', 'accent-span', 'peach'),
        ):
            self.assertIn(f'<{element} class="{kind} bold">{text}</{element}>', html)
            self.assertIn(f'<{element} class="{kind}">regular {text}</{element}>', html)
        self.assertIn('<strong class="emphasis bold">outer ^inner^ tail</strong>', html)
        self.assertIn(
            '<code class="code-span bold">outer `inner` &lt;b&gt;&amp;text&lt;/b&gt;</code>',
            html,
        )
        self.assertIn('<span class="accent-span bold">outer %inner% tail</span>', html)
        self.assertNotIn('Legacy note title', html)
        self.assertIn('empty ```` ^^^^ %%%% ##', html)
        self.assertIn('.bold, .bold a { font-weight: bold; }', html)

    def test_bold_spans_refresh_in_watch_mode(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    let original = readfile('slides.vroom')
    let updated = map(copy(original),
          \\ 'substitute(v:val, "Second", "^^green^^ ``blue`` %%peach%%", "")')
    call SaveDeck(updated)
    call WaitFor('search("green", "nw") > 0')
    let row = search('green', 'nw')
    for [word, group] in [
          \\ ['green', 'vroom_emphasis_bold'],
          \\ ['blue', 'vroom_code_bold'],
          \\ ['peach', 'vroom_accent_bold']]
      let column = match(getline(row), word) + 1
      call assert_equal(group, synIDattr(synID(row, column, 1), 'name'))
    endfor
""", start='2', watch=True)

    def test_gray_spans_refresh_in_watch_mode(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    let original = readfile('slides.vroom')
    let updated = map(copy(original),
          \\ 'substitute(v:val, "Second", "one #two three# four #six# seven", "")')
    call SaveDeck(updated)
    call WaitFor('search("two three", "nw") > 0')
    let row = search('six', 'nw')
    let column = match(getline(row), 'six') + 1
    call assert_equal('vroom_comment', synIDattr(synID(row, column, 1), 'name'))
    call assert_false(&l:wrap)
""", start='2', watch=True)

    def test_code_spans_do_not_change_centering(self):
        marked = 'one `two three` four ^five^ `^six^` seven'
        self.source.write_text(deck('== ' + marked) + '---- center\n' + marked + '\n')
        self.compile()
        visible = 'one two three four five ^six^ seven'
        expected = ' ' * ((80 - len(visible)) // 2) + visible
        for slide in ('002', '004'):
            content = (self.directory / slide).read_text()
            content = re.sub(r'\x1b\[[0-9;]*m', '', content)
            self.assertIn(expected, content.splitlines())

    def test_code_spans_refresh_in_watch_mode(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    let original = readfile('slides.vroom')
    let updated = map(copy(original),
          \\ 'substitute(v:val, "Second", "one `two three` four ^five^ `^six^` seven", "")')
    call SaveDeck(updated)
    call WaitFor('search("two three", "nw") > 0')
    let row = search('six', 'nw')
    let column = match(getline(row), 'six') + 1
    call assert_equal('vroom_code', synIDattr(synID(row, column, 1), 'name'))
    call assert_equal(2, count(getline(row), nr2char(27) . '[22;38;5;153m'))
""", start='2', watch=True)

    def test_emphasis_does_not_change_centering(self):
        self.source.write_text(
            deck('== one ^two three^ four five ^six^ seven')
            + '---- center\none ^two three^ four five ^six^ seven\n'
        )
        self.compile()
        visible = 'one two three four five six seven'
        expected = ' ' * ((80 - len(visible)) // 2) + visible
        for slide in ('002', '004'):
            content = (self.directory / slide).read_text()
            plain = re.sub(r'\x1b\[[0-9;]*m', '', content)
            self.assertIn(expected, plain.splitlines())

    def test_emphasis_refreshes_in_watch_mode(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    let original = readfile('slides.vroom')
    let updated = map(copy(original),
          \\ 'substitute(v:val, "Second", "one ^two three^ four five ^six^ seven", "")')
    call SaveDeck(updated)
    call WaitFor('search("two three", "nw") > 0')
    let row = search('six', 'nw')
    let column = match(getline(row), 'six') + 1
    call assert_equal('vroom_emphasis', synIDattr(synID(row, column, 1), 'name'))
    call assert_equal(2, count(getline(row), nr2char(27) . '[22;38;5;121m'))
""", start="2", watch=True)

    def test_run_compiles_and_opens_colored_slides(self):
        launcher = self.directory / "start-vim"
        launcher.write_text(
            f"#!{sys.executable}\n"
            "import os, sys\n"
            f"vim = {shutil.which('vim')!r}\n"
            "os.execv(vim, [vim, '-i', 'NONE', '-n', '-es',\n"
            "    *sys.argv[1:], '-S', 'start-check.vim'])\n"
        )
        launcher.chmod(0o755)
        self.source.write_text(
            deck('one ^two three^ four five ^six^ seven `code`').replace(
                'vimrc: |', f'vim: {launcher}\nvimrc: |'
            )
        )
        (self.directory / 'start-check.vim').write_text(
            "function! CheckStart()\n"
            "  call assert_equal('002', expand('%:t'))\n"
            "  let row = search('two three', 'nw')\n"
            "  let column = match(getline(row), 'two three') + 1\n"
            "  call assert_equal('vroom_emphasis',\n"
            "        \\ synIDattr(synID(row, column, 1), 'name'))\n"
            "  let column = match(getline(row), 'code') + 1\n"
            "  call assert_equal('vroom_code',\n"
            "        \\ synIDattr(synID(row, column, 1), 'name'))\n"
            "  call writefile(v:errors, 'start-errors.txt')\n"
            "  if !empty(v:errors)\n    cquit\n  endif\n  qa!\n"
            "endfunction\n"
            "autocmd VimEnter * ++nested call CheckStart()\n"
        )
        result = subprocess.run(
            START, cwd=self.directory,
            env=dict(os.environ, VROOM_START_SLIDE='2', VROOM_WATCH=''),
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.directory / 'start-errors.txt').read_text(), '')
        self.assertEqual(list((self.directory / '.cache/vroom-watch').glob('build-*')), [])

    def test_highlighted_url_opens_without_ansi_codes(self):
        bindir = self.directory / 'bin'
        bindir.mkdir()
        browser = bindir / 'chromium'
        browser.write_text(
            f'#!{sys.executable}\n'
            'import json, sys\n'
            'from pathlib import Path\n'
            'Path("browser.json").write_text(json.dumps(sys.argv[1:]))\n'
        )
        browser.chmod(0o755)
        (self.directory / 'url-slide').write_text(
            '    \x1b[22;38;5;121mhttps://example.com/path\x1b[0m\n'
        )
        result = subprocess.run(
            line_runner('url-slide', '1'),
            cwd=self.directory,
            env=dict(os.environ, TERM='xterm',
                     PATH=str(bindir) + os.pathsep + os.environ['PATH']),
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.directory / 'browser.json'
        deadline = time.monotonic() + 3
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(json.loads(output.read_text())[-1], 'https://example.com/path')

    def test_live_reload_structure_and_error_recovery(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    call WaitFor('fnamemodify(argv(0), ":p") ==# getcwd() . "/001"')
    call assert_equal('002', expand('%:t'))
    let original = readfile('slides.vroom')
    call SaveDeck(map(copy(original), 'substitute(v:val, "Second", "Updated", "")'))
    call WaitFor('search("Updated", "nw") > 0')
    execute 'argument ' . (index(map(copy(argv()), 'fnamemodify(v:val, ":t")'), '002z') + 1)
    let longer = insert(copy(original), '+Extra', index(original, '+Last'))
    call SaveDeck(longer)
    call WaitFor('expand("%:t") ==# "002c"')
    call assert_true(filereadable('002c'))
    call SaveDeck(filter(copy(original), 'v:val !=# "+More" && v:val !=# "+Last"'))
    call WaitFor('expand("%:t") ==# "002" && !filereadable("002z")')
    normal ,
    call assert_equal('003', expand('%:t'))
    let g:baseline = Generation()
    call SaveDeck(['---- config', 'title: [broken', '----', 'Bad'])
    call WaitFor('filereadable(".cache/vroom-watch/build.log") && getfsize(".cache/vroom-watch/build.log") > 0')
    call assert_equal(g:baseline, Generation())
    call assert_true(search('Third', 'nw') > 0)
    call SaveDeck(map(copy(original), 'substitute(v:val, "Third", "Recovered", "")'))
    call WaitFor('search("Recovered", "nw") > 0')
    let shortened = original[0 : index(original, 'Third') - 2]
    call SaveDeck(shortened)
    call WaitFor('expand("%:t") =~# "^002" && !filereadable("003")')
    call assert_equal('002', expand('%:t'))
""", start="2", watch=True)

    def test_modified_and_demo_buffers_are_protected(self):
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    let original = readfile('slides.vroom')
    call setline(2, 'Unsaved edit')
    let g:baseline = Generation()
    call SaveDeck(map(copy(original), 'substitute(v:val, "Second", "Saved update", "")'))
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    call assert_true(&modified)
    call assert_equal('Unsaved edit', getline(2))
    setlocal nomodified
    call WaitFor('search("Saved update", "nw") > 0')
    edit demo.py
    let g:baseline = Generation()
    call SaveDeck(original)
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    call assert_equal('demo.py', expand('%:t'))
    execute 'argument ' . (index(map(copy(argv()), 'fnamemodify(v:val, ":t")'), '002') + 1)
    call WaitFor('search("Second", "nw") > 0')
""", start="2", watch=True)

    def test_included_file_changes_refresh_the_visible_slide(self):
        self.source.write_text(deck() + "---- include extra.vroom\n")
        (self.directory / "extra.vroom").write_text("----\nIncluded\n")
        self.compile()
        self.vim("""
    let g:baseline = Generation()
    call WaitFor('Generation() !=# g:baseline')
    sleep 1100m
    call writefile(['----', 'Updated include'], 'extra.vroom')
    call WaitFor('search("Updated include", "nw") > 0')
    call assert_equal('004', expand('%:t'))
""", start="4", watch=True)

    def test_saves_during_build_and_exit_cleanup(self):
        wrapper = self.directory / "util/vroom-watch-compile"
        wrapper.unlink()
        wrapper.write_text(
            'open my $fh, ">>", "compiler.pids" or die $!;\n'
            'print {$fh} "$$\\n"; close $fh;\n'
            'select undef, undef, undef, 1.3;\n'
            f'exec $^X, q{{{COMPILER}}};\n'
        )
        if YS_BACKEND:
            wrapper.write_text(
                f"#!{sys.executable}\n"
                "import os, time\n"
                "with open('compiler.pids', 'a') as output:\n"
                "    output.write(str(os.getpid()) + '\\n')\n"
                "time.sleep(1.3)\n"
                f"os.execv({str(VROOM_YS)!r}, {COMPILE!r})\n"
            )
            wrapper.chmod(0o755)
            with self.source.open('a') as source:
                source.write(
                    "---- config\nvimrc: |\n"
                    "  source ./vimrc\n"
                    "  let g:vroom_compile_command = "
                    "[getcwd() . '/util/vroom-watch-compile']\n"
                )
            self.compile()
        self.vim("""
    call WaitFor('filereadable("compiler.pids")')
    let original = readfile('slides.vroom')
    call SaveDeck(map(copy(original), 'substitute(v:val, "Second", "Latest", "")'))
    call WaitFor('len(readfile("compiler.pids")) >= 2')
    call WaitFor('search("Latest", "nw") > 0')
    sleep 2000m
    call SaveDeck(original)
    call WaitFor('len(readfile("compiler.pids")) >= 3')
""", start="2", watch=True)
        pid = int((self.directory / "compiler.pids").read_text().splitlines()[-1])
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail(f"Compiler {pid} survived presentation exit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
