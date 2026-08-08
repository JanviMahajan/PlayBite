// fruit-slice.js - simple canvas fruit slice prototype
export default class FruitSlice {
  constructor(engine, opts={}){
    this.engine = engine; this.opts = opts;
    this.canvas = null; this.ctx = null; this.objects = []; this.lastSpawn = 0; this.spawnInterval = 800; this.combo = 1; this.gameOver=false;
  }

  async init(){
    const root = this.engine.root; root.innerHTML='';
    this.canvas = document.createElement('canvas'); this.canvas.width=800; this.canvas.height=600; this.canvas.style.width='100%';
    this.ctx = this.canvas.getContext('2d'); root.appendChild(this.canvas);

    this.canvas.addEventListener('pointerdown', (e)=> this._onPointer(e));
    this.canvas.addEventListener('pointermove', (e)=> this._onPointerMove(e));
    this.canvas.addEventListener('pointerup', (e)=> this._onPointerUp(e));

    this._pointerActive=false; this._lastTrail=[];
  }

  _onPointer(e){ this._pointerActive=true; this._lastTrail.push({x:e.offsetX, y:e.offsetY}); }
  _onPointerMove(e){ if(this._pointerActive){ this._lastTrail.push({x:e.offsetX,y:e.offsetY}); this._checkSlices(); } }
  _onPointerUp(e){ this._pointerActive=false; this._lastTrail.length=0; }

  _spawn(){
    const w=this.canvas.width; const h=this.canvas.height;
    const x = Math.random()*w*0.8 + w*0.1;
    const y = h + 50;
    const vx = (Math.random()-0.5)*6;
    const vy = - (6 + Math.random()*8);
    const isBomb = Math.random() < 0.08;
    this.objects.push({x,y,vx,vy,age:0,r:22,fruit: isBomb ? 'bomb' : 'fruit'});
  }

  _checkSlices(){
    if(this._lastTrail.length<2) return;
    const p1 = this._lastTrail[this._lastTrail.length-2]; const p2 = this._lastTrail[this._lastTrail.length-1];
    // line segment p1->p2, check intersection with circle objects
    for(let i=this.objects.length-1;i>=0;i--){ const obj=this.objects[i]; if(obj.sliced) continue; const cx=obj.x, cy=obj.y, r=obj.r; if(this._lineIntersectsCircle(p1,p2,{x:cx,y:cy},r)){ this._sliceObject(obj,i); } }
  }

  _lineIntersectsCircle(p1,p2,c,r){
    const vx = p2.x-p1.x, vy=p2.y-p1.y; const lx = p1.x-c.x, ly=p1.y-c.y; const a=vx*vx+vy*vy; const b=2*(vx*lx+vy*ly); const cterm=lx*lx+ly*ly - r*r; let disc = b*b - 4*a*cterm; return disc >= 0;
  }

  _sliceObject(obj,idx){
    obj.sliced=true;
    if(obj.fruit==='bomb'){ this.engine.addScore(-500); this.engine.end('bomb'); }
    else { this.engine.addScore(250 * this.combo); this.combo += 1; }
    // remove after small delay
    setTimeout(()=>{ this.objects.splice(idx,1); }, 120);
  }

  async update(dt){
    const now = performance.now();
    if(now - this.lastSpawn > this.spawnInterval){ this._spawn(); this.lastSpawn = now; }
    // physics
    for(let obj of this.objects){ obj.vy += 9.8*dt*0.5; obj.x += obj.vx; obj.y += obj.vy; obj.age += dt; }
    // cull
    this.objects = this.objects.filter(o=>o.y < this.canvas.height + 200);

    // draw
    const ctx=this.ctx; ctx.clearRect(0,0,this.canvas.width,this.canvas.height);
    for(let o of this.objects){ if(o.fruit==='bomb'){ ctx.fillStyle='black'; ctx.beginPath(); ctx.arc(o.x,o.y,o.r,0,Math.PI*2); ctx.fill(); } else { ctx.fillStyle='orange'; ctx.beginPath(); ctx.arc(o.x,o.y,o.r,0,Math.PI*2); ctx.fill(); } }

    // draw trail
    if(this._lastTrail.length>1){ ctx.strokeStyle='rgba(255,255,255,0.7)'; ctx.lineWidth=6; ctx.beginPath(); ctx.moveTo(this._lastTrail[0].x,this._lastTrail[0].y); for(let i=1;i<this._lastTrail.length;i++){ ctx.lineTo(this._lastTrail[i].x,this._lastTrail[i].y); } ctx.stroke(); }

    // end condition if too many bombs sliced? or time
  }

  async destroy(){ /* cleanup listeners */ }
}
