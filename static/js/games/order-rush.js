const OPTIONS = [
  ['☕', 'Coffee'],
  ['🍔', 'Burger'],
  ['🍕', 'Pizza'],
  ['🍟', 'Fries'],
  ['🥤', 'Drink'],
  ['🧁', 'Cupcake'],
  ['🍩', 'Donut'],
  ['🥪', 'Sandwich'],
];

export default class OrderRush {
  constructor(engine, challenge) {
    this.e = engine;
    this.c = challenge;
    this.maxWrong = Number.isInteger(challenge.max_wrong) ? challenge.max_wrong : 2;
    this.selected = [];
    this.attempts = [];
    this.wrong = 0;
    this.ready = false;
    this.buttons = [];
    this.revealTimer = null;
  }

  init() {
    this.e.stage.innerHTML = `
      <div class="order-game">
        <div class="order-ticket">
          <span>Memorize this order!</span>
          <div class="order-preview">${this.c.order.join(' ')}</div>
        </div>
        <div class="order-slots">
          ${this.c.order.map(() => '<span>?</span>').join('')}
        </div>
        <div class="order-mistakes" role="status">Incorrect taps: <b>0 / ${this.maxWrong}</b></div>
        <div class="food-grid">
          ${OPTIONS.map(([food, name]) => `
            <button type="button" data-food="${food}" aria-label="${name}" aria-pressed="false">
              <b>${food}</b><small>${name}</small>
            </button>
          `).join('')}
        </div>
      </div>`;

    this.grid = this.e.stage.querySelector('.food-grid');
    this.grid.hidden = true;
    this.buttons = [...this.grid.querySelectorAll('button')];

    // Direct listeners make the emoji, label, touch, mouse, and keyboard paths
    // behave consistently instead of relying on delegated target detection.
    this.buttons.forEach((button) => {
      button.addEventListener('click', () => this.pick(button.dataset.food, button));
    });

    this.revealTimer = window.setTimeout(() => {
      if (this.e.ending) return;
      this.e.stage.querySelector('.order-ticket')?.classList.add('hidden');
      this.grid.hidden = false;
      this.ready = true;
      this.e.status('Now recreate it in the same order!');
    }, 3000);
  }

  pick(food, button) {
    if (!this.ready || this.e.ending || button.disabled) return;

    const wanted = this.c.order[this.selected.length];
    this.attempts.push(food);
    if (food !== wanted) {
      this.wrong += 1;
      this.e.stage.querySelector('.order-mistakes b').textContent = `${this.wrong} / ${this.maxWrong}`;
      button.classList.remove('shake');
      void button.offsetWidth;
      button.classList.add('shake');
      window.setTimeout(() => button.classList.remove('shake'), 350);
      this.e.sound('miss');
      if (this.wrong > this.maxWrong) {
        this.ready = false;
        this.e.status('Too many incorrect taps!','miss');
        this.e.finish('mistakes',{selection:this.selected,attempts:this.attempts});
        return;
      }
      this.e.status(`${this.maxWrong-this.wrong} incorrect tap${this.maxWrong-this.wrong===1?'':'s'} left ✨`, 'miss');
      return;
    }

    this.selected.push(food);
    button.disabled = true;
    button.setAttribute('aria-pressed', 'true');
    this.e.stage.querySelectorAll('.order-slots span')[this.selected.length - 1].textContent = food;
    this.e.sound('correct');

    if (this.selected.length === this.c.order.length) {
      this.ready = false;
      this.e.status(this.e.strings.orderServed, 'success');
      window.setTimeout(() => this.e.complete({ selection: this.selected, attempts: this.attempts }), 250);
    }
  }

  destroy() {
    if (this.revealTimer) window.clearTimeout(this.revealTimer);
    this.ready = false;
  }
}
