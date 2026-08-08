// GameEngine: shared lifecycle, timer, score, pause, mute, FPS-friendly loop
export default class GameEngine {
  constructor({root, duration=30, onEnd}){
    this.root = root;
    this.duration = duration;
    this.onEnd = onEnd;
    this.game = null;
    this.timer = duration;
    this.interval = null;
    this.score = 0;
    this.paused = false;
    this.muted = false;
    this.tickRate = 1000/60;
    this._lastTick = performance.now();
    this._frame = null;

    this._onTick = this._onTick.bind(this);
  }

  async load(gameInstance){
    this.game = gameInstance;
    if(this.game && typeof this.game.init === 'function'){
      await this.game.init();
    }
    // show initial state
    this._renderScore();
    this._renderTimer();
  }

  start(){
    this._startTime = performance.now();
    this._lastFrameTime = performance.now();
    this._frame = requestAnimationFrame(this._onTick);
  }

  _onTick(now){
    if(this.paused){ this._lastTick = now; this._frame = requestAnimationFrame(this._onTick); return; }
    const dt = (now - (this._lastTick || now)) / 1000;
    this._lastTick = now;

    // update timer
    this.timer -= dt;
    if(this.timer < 0) this.timer = 0;
    this._renderTimer();

    // delegate to game
    if(this.game && typeof this.game.update === 'function'){
      this.game.update(dt);
    }

    // update HUD
    this._renderScore();

    if(this.timer <= 0){
      this.end('timeout');
      return;
    }

    this._frame = requestAnimationFrame(this._onTick);
  }

  addScore(n){ this.score += n; this._renderScore(); }
  setScore(n){ this.score = n; this._renderScore(); }

  _renderScore(){
    const el = document.getElementById('game-score');
    if(el) el.innerText = this.score;
  }
  _renderTimer(){
    const el = document.getElementById('game-timer');
    if(!el) return;
    const s = Math.ceil(this.timer);
    const mm = String(Math.floor(s/60)).padStart(2,'0');
    const ss = String(s%60).padStart(2,'0');
    el.innerText = `${mm}:${ss}`;
  }

  togglePause(){
    this.paused = !this.paused;
    if(this.paused){ cancelAnimationFrame(this._frame); }
    else { this._lastTick = performance.now(); this._frame = requestAnimationFrame(this._onTick); }
  }
  toggleMute(){ this.muted = !this.muted; }

  async end(status='completed'){
    // stop loop
    cancelAnimationFrame(this._frame);
    this.timer = 0;
    if(this.game && typeof this.game.destroy === 'function'){
      try{ await this.game.destroy(); }catch(e){console.warn(e);} 
    }
    // call onEnd callback with result payload
    if(typeof this.onEnd === 'function'){
      const elapsed = this.duration - this.timer;
      this.onEnd({score: this.score, time: Math.round(elapsed), status});
    }
  }
}
