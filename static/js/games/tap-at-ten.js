export default class TapAtTen {
  constructor(engine, challenge) {
    this.e = engine;
    this.c = challenge;
    this.elapsed = 0;
    this.done = false;
  }

  init() {
    this.e.stage.classList.add('tap-ten-stage');
    this.e.stage.innerHTML = '<button type="button" class="tap-ten-button" aria-label="Stop the hidden ten-second timer">STOP</button>';
    this.button = this.e.stage.querySelector('.tap-ten-button');
    this.button.addEventListener('click', () => this.tap());
    this.button.focus({preventScroll: true});
  }

  update(_now, remaining) {
    if (this.done) return;
    this.elapsed = Math.max(0, this.e.duration - remaining);
  }

  tap() {
    if (this.done || this.e.ending) return;
    this.done = true;
    this.button.disabled = true;
    const tapMs = Math.round(this.elapsed * 1000);
    this.e.sound('tap');
    window.setTimeout(() => this.e.complete({tap_ms: tapMs}), 180);
  }

  destroy() {
    this.done = true;
  }
}
