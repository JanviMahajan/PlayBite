export default class GameEngine {
  constructor({root, slug, startUrl, submitUrl, ui, GameClass, strings={}}) {
    Object.assign(this, {root, slug, startUrl, submitUrl, ui, GameClass, strings});
    this.running = false; this.ending = false; this.muted = true; this.frame = null;
  }

  csrf() { return document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.split('=').slice(1).join('=') || ''; }
  async request(url, body = {}) {
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(this.csrf())}, body:JSON.stringify(body)});
    let data = {};
    try { data = await response.json(); } catch (_) { /* Preserve HTTP status for safe recovery. */ }
    if (!response.ok) throw Object.assign(new Error(data.error || 'Request failed'), {status:response.status});
    return data;
  }
  async begin() {
    const button = document.getElementById('start-game'); button.disabled = true;
    try {
      await this.countdown();
      const session = await this.request(this.startUrl);
      this.challenge = session.challenge; this.duration = session.duration;
      this.mount();
    } catch (error) {
      this.root.innerHTML = `<div class="pb-result"><div class="pb-game-hero">📡</div><h1>${this.strings.couldNotStart}</h1><p>${this.strings.connection}</p><button class="pb-primary-button" onclick="location.reload()">${this.strings.refresh}</button></div>`;
    }
  }
  async countdown() {
    this.root.innerHTML = '<div class="pb-countdown" aria-label="Game countdown"><strong></strong></div>';
    const node = this.root.querySelector('strong');
    const values = this.slug === 'tap-at-ten' ? ['1','2','3','GO! ☕'] : ['3','2','1','GO! 🎮'];
    for (const value of values) { node.textContent=value; node.classList.remove('pop'); void node.offsetWidth; node.classList.add('pop'); await new Promise(r=>setTimeout(r,value[0]==='G'?600:520)); }
  }
  mount() {
    const timer = this.slug === 'tap-at-ten' ? '' : `<div class="pb-play-head"><div><span class="pb-eyebrow">${this.strings.todayChallenge}</span><h1>${this.ui.title}</h1></div><small id="seconds-left">${this.duration}s</small></div><div class="pb-time-track" role="timer" aria-label="Time remaining"><span class="pb-time-start">●</span><div class="pb-time-fill"></div><span class="pb-runner">${this.ui.icon}</span><span class="pb-flag">🏁</span></div>`;
    this.root.innerHTML = `${timer}<div id="game-stage" class="pb-stage"></div><p id="game-status" class="pb-game-status" role="status"></p>`;
    this.stage = this.root.querySelector('#game-stage');
    this.game = new this.GameClass(this, this.challenge); this.game.init();
    this.started = performance.now(); this.running = true; this.frame = requestAnimationFrame(t=>this.tick(t));
  }
  tick(now) {
    if (!this.running) return;
    const elapsed=(now-this.started)/1000, remaining=Math.max(0,this.duration-elapsed), progress=Math.min(1,elapsed/this.duration);
    this.root.style.setProperty('--time-progress', `${progress*100}%`);
    this.root.classList.toggle('is-urgent', progress >= .8);
    const seconds = this.root.querySelector('#seconds-left');
    if (seconds) seconds.textContent=`${Math.ceil(remaining)}s`;
    this.game?.update?.(now, remaining);
    if (remaining <= 0) { this.finish('timeout', {}); return; }
    this.frame=requestAnimationFrame(t=>this.tick(t));
  }
  status(message, kind='') { const el=this.root.querySelector('#game-status'); if(el){el.textContent=message;el.dataset.kind=kind;} }
  sound(type) { if(this.muted) return; const ctx=this.audio||(this.audio=new AudioContext()); const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=type==='success'?660:340;g.gain.value=.025;o.connect(g).connect(ctx.destination);o.start();g.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.12);o.stop(ctx.currentTime+.13); }
  toggleMute(button) { this.muted=!this.muted; button.textContent=this.muted?'🔇':'🔊';button.setAttribute('aria-pressed',String(this.muted));button.setAttribute('aria-label',this.muted?'Unmute game sounds':'Mute game sounds'); }
  complete(evidence) { this.finish('completed', evidence); }
  async finish(outcome, evidence) {
    if (this.ending) return; this.ending=true;this.outcome=outcome;this.running=false;cancelAnimationFrame(this.frame);this.game?.destroy?.();
    try { const result=await this.request(this.submitUrl,{outcome,evidence}); this.showResult(result); }
    catch (error) {
      if (error.status === 409 || error.status >= 500) { window.location.reload(); return; }
      this.root.innerHTML='<div class="pb-result"><div class="pb-game-hero">📡</div><h1>Result saved?</h1><p>We lost the connection while checking. Refresh this page to safely see today’s final status.</p><button class="pb-primary-button" onclick="location.reload()">Refresh</button></div>';
    }
  }
  showResult(result) {
    if (!result.won) {
      if (this.slug === 'order-rush' && this.outcome === 'mistakes') {
        this.root.innerHTML='<div class="pb-result"><div class="pb-game-hero fail">🧾</div><h1>Oops! Too many incorrect taps!</h1><p>Today’s order challenge is over. Come back tomorrow and try again! ✨</p><a class="pb-primary-button" href="/">See You Tomorrow</a></div>'; return;
      }
      if (this.slug === 'burger-stack' && this.outcome === 'missed') {
        this.root.innerHTML='<div class="pb-result"><div class="pb-game-hero fail">🍔</div><h1>Oops! It missed the tray!</h1><p>That ingredient fell to the ground. Come back tomorrow for another try! ✨</p><a class="pb-primary-button" href="/">See You Tomorrow</a></div>'; return;
      }
      if (this.slug === 'pizza-slice' && this.outcome === 'missed') {
        this.root.innerHTML='<div class="pb-result"><div class="pb-game-hero fail">🍕</div><h1>Oops! Missed the green zone!</h1><p>That cut was outside the target. Come back tomorrow for another try! ✨</p><a class="pb-primary-button" href="/">See You Tomorrow</a></div>'; return;
      }
      this.root.innerHTML=`<div class="pb-result"><div class="pb-game-hero fail">🥹</div><h1>${this.strings.timeUp}</h1><p>${this.strings.soClose}</p><a class="pb-primary-button" href="/">${this.strings.tomorrow}</a></div>`; return;
    }
    this.sound('success'); this.confetti(); const coupon=result.coupon;
    if (!coupon) {
      const message=result.coupon_error==='no_table_reward'?this.strings.noTableReward:'No active reward is available for this table. Please ask the restaurant team to activate it.';
      this.root.innerHTML=`<div class="pb-result"><div class="pb-game-hero">🎉</div><h1>Game complete!</h1><p>${message}</p><a class="pb-primary-button" href="/">Done</a></div>`; return;
    }
    if (coupon?.view_url) { window.setTimeout(() => window.location.assign(coupon.view_url), 450); return; }
    this.root.innerHTML=`<div class="pb-result"><div class="pb-game-hero">🎉</div><h1>${this.strings.didIt}</h1><p>${this.strings.unlocked}</p>${coupon?`<div class="pb-coupon"><span>${coupon.reward}</span><code>${coupon.code}</code><small>${this.strings.validFrom} ${new Date(coupon.valid_from).toLocaleDateString(document.documentElement.lang)}</small></div>`:''}<a class="pb-primary-button" href="/">${this.strings.done}</a></div>`;
  }
  confetti(){for(let i=0;i<36;i++){const p=document.createElement('i');p.className='confetti-piece';p.style.left=Math.random()*100+'vw';p.style.background=['#f36b32','#f8b84e','#30b978'][i%3];p.style.animationDelay=Math.random()*.3+'s';document.body.append(p);setTimeout(()=>p.remove(),2400);}}
}
