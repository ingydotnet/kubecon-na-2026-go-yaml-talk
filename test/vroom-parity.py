"""Compare native and interpreted YS output with the talk's Perl compiler."""

import os
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PERL = os.environ["VROOM_WATCH_PERL"]
YS = os.environ["VROOM_WATCH_YS"]
VROOM = ROOT / "repos/vroom"
CONFIG = (
    "---- config\ntitle: Parity\nheight: 24\nwidth: 80\nbefore: 1\n"
)
CASES = {
    "talk": (ROOT / "slides.vroom").read_text(),
    "notes-and-scripts": (
        CONFIG + "script: '@'\n"
        "----\n% Notes title\n== Notes\n* First\n@echo first\n"
        "+* Next\n@echo second\n====\nOpening\n+Closing\n"
        "---- python\nvalue = 1 + 2\n"
        "---- include extra.vroom\n"
    ),
    "format-and-replace": (
        CONFIG + "---- center\n^Ingy döt Net^ ``code``\n+next\n"
        "---- i3\n== Heading\n* One\n+  continuation\n+* Two\n"
        "---- replace\n* Old\n+* Replacement\n  wrapped\n+Last\n"
        "---- i-3\n      undented\n!footer\n"
        "---- cdpython\nvalue = 1\n"
        "---- .txt\ntext\n"
    ),
    "configuration": (
        "---- config\nheight: 12\nwidth: 60\ntop: 1\nskip: 1\n"
        "----\nOmitted\n---- skip\nAlso omitted\n"
        "----\n== Header\n* Body\n+* More\n"
        "---- config\ncenter: 1\nheight: 18\n"
        "----\ncentered\n+another\n"
    ),
    "many-reveals": CONFIG + "----\nFirst\n" + "+Next\n" * 28,
}


def generated(directory):
    files = {
        str(path.relative_to(directory)): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file() and re.fullmatch(
            r"(?:bin/)?\d+[a-z]*(?:\.[\w-]+)*|notes.txt",
            str(path.relative_to(directory)),
        )
    }
    return files


temporary = tempfile.TemporaryDirectory(
    prefix="vroom-parity-", dir=ROOT / ".cache"
)
with temporary as temp:
    for name, source in CASES.items():
        results = []
        commands = [
            [PERL, str(ROOT / "util/vroom-watch-compile")],
            [YS, str(VROOM / "vroom.ys"), "compile"],
            [str(VROOM / "bin/vroom"), "compile"],
        ]
        for index, command in enumerate(commands):
            directory = Path(temp) / name / str(index)
            directory.mkdir(parents=True)
            (directory / "slides.vroom").write_text(source)
            (directory / "extra.vroom").write_text("---- shell\necho included\n")
            result = subprocess.run(
                command, cwd=directory, capture_output=True,
                text=True, timeout=30,
            )
            if result.returncode:
                raise AssertionError(
                    f"{name} {command}: {result.stderr}"
                )
            results.append(generated(directory))
        for label, actual in zip(("interpreted", "native"), results[1:]):
            expected = results[0]
            different = sorted(
                key for key in expected.keys() | actual.keys()
                if expected.get(key) != actual.get(key)
            )
            if different:
                raise AssertionError(
                    f"{name} {label}: differing files {different}"
                )
        print(f"ok - {name}: Perl, interpreted YS, and native YS match")
