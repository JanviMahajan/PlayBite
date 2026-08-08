// memory-match.js - simple DOM-based memory match game using engine
export default class MemoryMatch {
  constructor(engine, opts={}){
    this.engine = engine;
    this.opts = opts;
    this.pairs = 6; // adaptive depending on screen
    this.cards = [];
    this.first = null;
    this.second = null;
    this.matched = 0;
    this.moves = 0;
  }

  async init(){
    const root = this.engine.root;
    root.innerHTML = '';
    this.container = document.createElement('div');
    this.container.className = 'memory-container';

    // determine pair count by width
    const w = Math.min(window.innerWidth, 900);
    this.pairs = w < 420 ? 6 : 8;

    // generate deck
    const total = this.pairs * 2;
    const values = [];
    for(let i=0;i<total/2;i++){ values.push(i); values.push(i); }
    // shuffle
    for(let i=values.length-1;i>0;i--){ const j = Math.floor(Math.random()*(i+1)); [values[i], values[j]]=[values[j], values[i]]; }

    const grid = document.createElement('div'); grid.className = 'memory-grid';
    values.forEach((v, idx)=>{
      const card = document.createElement('button');
      card.className = 'memory-card';
      card.dataset.value = v;
      card.setAttribute('aria-label', 'Card');
      card.innerHTML = `<div class='face front'></div><div class='face back'>${v}</div>`;
      card.addEventListener('click', ()=>this.onCardClick(card));
      grid.appendChild(card);
      this.cards.push(card);
    });

    const info = document.createElement('div'); info.className='memory-info text-center my-2';
    info.innerHTML = `<div>Moves: <span id='movesCount'>0</span></div>`;
    this.container.appendChild(grid);
    this.container.appendChild(info);
    root.appendChild(this.container);

    // accessibility: keyboard
    root.addEventListener('keydown', (e)=>{
      if(e.key === 'r') this.restart();
    });
  }

  onCardClick(card){
    if(card.classList.contains('flipped')) return;
    card.classList.add('flipped');

    if(!this.first){ this.first = card; return; }
    if(this.first === card) return;
    this.second = card;
    this.moves += 1;
    document.getElementById('movesCount').innerText = this.moves;

    if(this.first.dataset.value === this.second.dataset.value){
      // match
      this.first.disabled = true; this.second.disabled = true;
      this.matched += 1;
      this.engine.addScore(500);
      this.first = null; this.second = null;
      if(this.matched >= this.pairs){ this.win(); }
    } else {
      // mismatch
      this.engine.addScore(-50);
      setTimeout(()=>{ this.first.classList.remove('flipped'); this.second.classList.remove('flipped'); this.first=null; this.second=null; }, 700);
    }
  }

  async update(dt){ /* nothing heavy here */ }

  async destroy(){ /* cleanup */ }

  restart(){
    this.engine.score = 0; this.matched=0; this.moves=0; this.first=null; this.second=null; this.container.querySelector('#movesCount').innerText = '0';
    // re-init
    this.init();
  }

  win(){
    // award bonus for remaining time
    this.engine.addScore(Math.max(1000, Math.round(this.engine.timer * 50)));
    this.engine.end('completed');
  }
}
