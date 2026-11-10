# Evolving the YAML Family

This repository contains the complete working draft of Ingy döt Net's talk
for Open Source Summit Europe 2026.

The deck is presented in Vim with Vroom.
Commands and URLs on the slides are interactive: move to one and press Enter.

[View the slideshow website](https://ingydotnet.github.io/kubecon-na-2026-go-yaml-talk/).

## Run the talk

```sh
make preflight
make run
```

Start on a numbered slide, with earlier slides still available, using:

```sh
make run s=12
```

This starts on slide `012`, at its first reveal.
Omit `s`, or use `s=0`, to start at the first slide.
Press Space or Backspace to move through reveals.
Press `,` to jump to the final (`z`) reveal of the current multipart slide.
On the final reveal or a single-part slide, `,` advances to the next numbered
slide.

To rebuild and refresh the Vim presentation automatically after saves:

```sh
make run-watch
make run-watch s=12
```

These targets use Perl Vroom.
To try the native YAMLScript implementation in `repos/vroom`, use:

```sh
make vroom
make vroom-watch s=12
```

Both implementations support the same starting-slide and navigation keys.
`make -C repos/vroom build` builds the native `repos/vroom/bin/vroom` using
Makes-managed YAMLScript and Gloat dependencies.
Run `make vroom-check` to check the native CLI and the shared presentation
tests against it.

The watcher checks `slides.vroom` and its directly included files once per
second.
It preserves the current numbered slide and reveal position when possible,
and updates navigation when reveals or slides are added or removed.
Refreshes wait while you are editing a buffer or viewing a demo file.
Failed builds leave the previous deck available; diagnostics are saved in
`.cache/vroom-watch/build.log`.
Exiting the presentation stops the watcher.
Run only one presentation per worktree.

Slide titles starting with `== ` are pale magenta.

Wrap text in asterisks for bold without changing its color:

```text
This is *important* and *so is this*.
```

Ordinary `* ` bullet markers stay literal.
Bold spans must start and end with a non-whitespace character.

Wrap text in double tildes for strikethrough, keeping its surrounding color:

```text
Use ~~the old setting~~ the new setting.
```

Wrap text in carets to make it regular-weight mint green:

```text
one ^two three^ four five ^six^ seven
```

Wrap code in single backticks for pale-blue text at regular weight:

```text
Use `kubectl apply` to deploy ^your application^, then run `kubectl get pods`.
```

Wrap comment-like text in hash marks for light gray at regular weight:

```text
Use `kubectl apply` #with your chosen namespace# for ^your application^.
```

Wrap text in percent signs for warm peach at regular weight:

```text
YAML implementations exist in over %50 languages%.
```

Wrap text in at signs for soft yellow at regular weight:

```text
one @two three@ four five @six@ seven
```

Use double carets, backticks, or percent signs for bold versions:

```text
^^mint green^^ and ``pale blue code`` and %%warm peach%%
```

Multiple spans work independently on the same line.
Spans cannot nest or cross lines; the first opening delimiter owns its
contents until its matching closing delimiter.
Single delimiters inside a double-delimited span stay literal.
Code contents are literal, so carets, hash marks, and percent signs inside
code are displayed normally.
Empty pairs and unmatched delimiters remain literal.
A leading unpaired `%` retains Vroom's slide-note title syntax.
The generated slide files contain ANSI styling, which Vim renders while
hiding the escape codes.
Generated Vim slides disable line wrapping so hidden ANSI codes do not
cause early wraps.
The website uses the same highlighting.
Highlighted commands and URLs still run normally when you press Enter.
Backticks are presentation markup; use `$()` for shell substitution in
runnable examples.

On multi-part slides, the newly revealed bullet block is bold white.
This includes wrapped lines and sub-bullets, while inline colors stay visible.
Earlier blocks return to their usual colors as you advance.
On the final reveal, the last bullet and its wrapped lines are underlined.
These cues appear in both Vim and the website.

The first run installs all required tools under `.cache/` through Makes.
The talk does not rely on globally installed language runtimes or CLIs.

The related source checkouts must already exist under `repos/`:
`go-yaml`, `yamlstar`, and `vroom-pm`.
Run `make go-yaml-plugins` to build the demo CLI with the reference,
JSON-comments, and TOML parsers.
The external parser packages use pinned release versions.

Build the `go-yaml` command with the CSV/TSV parser from the talk directory:

```sh
make cli \
  PLUGIN-PACKAGE=github.com/yamlstar/yamlstar-plugin-parser-csv/goyaml@v0.1.0
```

## Function-Tag demo

The demo files live at the talk root: `main.go`, `input.yaml`, `vars.yaml`,
and `options.yaml`.
The example imports `nginx` deployment defaults from `vars.yaml`,
then overrides the namespace from `dev` to `prod` while retaining three
replicas.

```sh
make cli
make shell CMD='go-yaml -C options.yaml -y input.yaml'
make shell CMD='go run main.go'
```

Makes creates an ignored `go.mod` that uses the checkout in `repos/go-yaml`,
including its unreleased plugins.

## Slideshow website

Build and serve the browser version locally with:

```sh
make serve
```

The server rebuilds the website whenever `slides.vroom` changes and serves it
at <http://127.0.0.1:8000/>.
Use `HOST` and `PORT` to override the listening address.

On phones, tap once to advance or double-tap to go back one reveal.
Single taps wait briefly to distinguish them from double taps.
Mouse clicks, keyboard navigation, and the `[back]` button work as before.

Publish the generated website to the `gh-pages` branch with:

```sh
make publish
```

## Validate everything

```sh
make check
```

This compiles the Vroom deck, checks both Bash programs with ShellCheck,
tests the Vim watcher, lints and runs the YAMLScript example, converts the
YAMLSchema example, and exercises the YAMLStar and go-yaml interoperability
demos.

Run just the isolated Vroom compilation and Vim watcher checks with:

```sh
make watch-check
```

Each live demo also has a captured output under `demo/fallback/`.
The timing, speaking notes, cut list, and recovery plan are in
[`note/run-of-show.md`](note/run-of-show.md).
