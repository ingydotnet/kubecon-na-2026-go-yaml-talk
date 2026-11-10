// Exercise the generated browser script with deterministic touch events.
// Run: node test/site-navigation.js slides/index.html
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(process.argv[2] || 'slides/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function browser({pointerEvents = true, hash = '#2.2'} = {}) {
  const handlers = {};
  const timers = new Map();
  let now = 0;
  let timerId = 0;
  const frames = ['1.1', '2.1', '2.2', '2.3', '3.1'].map(id => {
    const [slide, step] = id.split('.');
    return {
      dataset: {slide, step: String(Number(step) - 1)},
      hidden: true,
      handlers: {},
      addEventListener(type, handler) { this.handlers[type] = handler; },
    };
  });
  const previous = {
    handlers: {},
    addEventListener(type, handler) { this.handlers[type] = handler; },
  };
  const location = {hash};
  const context = {
    document: {
      querySelectorAll: () => frames,
      querySelector: selector => selector === '#previous' ? previous : {},
    },
    window: pointerEvents ? {PointerEvent: function () {}} : {},
    location,
    history: {replaceState: (_state, _title, value) => { location.hash = value; }},
    addEventListener: (type, handler) => { handlers[type] = handler; },
    setTimeout: (callback, delay) => {
      timers.set(++timerId, {callback, at: now + delay});
      return timerId;
    },
    clearTimeout: id => timers.delete(id),
  };
  vm.runInNewContext(script, context);
  const index = () => frames.findIndex(frame => !frame.hidden);
  const advance = milliseconds => {
    const end = now + milliseconds;
    for (;;) {
      const next = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
      if (!next || next[1].at > end) break;
      now = next[1].at;
      timers.delete(next[0]);
      next[1].callback();
    }
    now = end;
  };
  const event = overrides => ({
    pointerType: 'touch', button: 0, isPrimary: true,
    clientX: 100, clientY: 100, target: {closest: () => null},
    preventDefault() {}, stopPropagation() {}, ...overrides,
  });
  return {
    index, advance, timers,
    tap: overrides => frames[index()].handlers[
      pointerEvents ? 'pointerup' : 'click'
    ](event(overrides)),
    key: key => handlers.keydown(event({key})),
    back: () => previous.handlers.click(event()),
    cancel: () => handlers.pointercancel(),
    hash: value => { location.hash = value; handlers.hashchange(); },
  };
}

const tests = {
  'single tap advances after the double-tap interval'() {
    const b = browser(); b.tap();
    assert.equal(b.index(), 2);
    b.advance(299); assert.equal(b.index(), 2);
    b.advance(1); assert.equal(b.index(), 3);
  },
  'double tap goes back without advancing first'() {
    const b = browser(); b.tap(); b.advance(100); b.tap();
    assert.equal(b.index(), 1);
    b.advance(1000); assert.equal(b.index(), 1);
  },
  'double tap stays at the beginning and works at the end'() {
    for (const [hash, expected] of [['#1.1', 0], ['#3.1', 3]]) {
      const b = browser({hash}); b.tap(); b.tap(); b.advance(1000);
      assert.equal(b.index(), expected);
    }
  },
  'nearby touch positions count as a double tap'() {
    const b = browser(); b.tap(); b.tap({clientX: 115, clientY: 110});
    assert.equal(b.index(), 1);
  },
  'separate rapid taps advance twice'() {
    const b = browser(); b.tap(); b.tap({clientX: 300}); b.advance(300);
    assert.equal(b.index(), 4);
  },
  'keyboard and back button cancel a pending tap'() {
    for (const action of [b => b.key('ArrowLeft'), b => b.back()]) {
      const b = browser(); b.tap(); action(b); b.advance(1000);
      assert.equal(b.index(), 1);
    }
  },
  'hash changes cancel a pending tap'() {
    const b = browser(); b.tap(); b.hash('#3.1'); b.advance(1000);
    assert.equal(b.index(), 4);
  },
  'links cancel pending navigation and stay clickable'() {
    const b = browser(); b.tap(); b.tap({target: {closest: () => ({})}});
    b.advance(1000); assert.equal(b.index(), 2);
  },
  'secondary fingers and right clicks do not navigate'() {
    const b = browser(); b.tap({isPrimary: false}); b.tap({button: 2});
    b.advance(1000); assert.equal(b.index(), 2);
  },
  'scroll cancellation prevents delayed navigation'() {
    const b = browser(); b.tap(); b.cancel(); b.advance(1000);
    assert.equal(b.index(), 2);
  },
  'mouse clicks remain immediate'() {
    const b = browser(); b.tap({pointerType: 'mouse'});
    assert.equal(b.index(), 3); assert.equal(b.timers.size, 0);
  },
  'click fallback supports single and double taps'() {
    const b = browser({pointerEvents: false}); b.tap(); b.advance(300);
    assert.equal(b.index(), 3);
    b.tap(); b.advance(100); b.tap(); b.advance(1000);
    assert.equal(b.index(), 2);
  },
};
for (const [name, test] of Object.entries(tests)) {
  test();
  console.log('ok - ' + name);
}
