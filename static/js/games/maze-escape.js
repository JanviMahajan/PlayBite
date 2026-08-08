// maze-escape.js - simple grid maze with arrow key / swipe controls
export default class MazeEscape {
  constructor(engine, opts={}){
    this.engine = engine;
    this.opts = opts;
    this.gridSize = 9; // 9x9 maze
    this.player = {x:1,y:1};
    this.exit = {x:7,y:7};
    this.walls = new Set();
  }

  async init(){
    const root = this.engine.root; root.innerHTML='';
    this.canvas = document.createElement('canvas'); this.canvas.width = 720; this.canvas.height = 720; this.canvas.style.width='100%';
    this.ctx = this.canvas.getContext('2d');
    root.appendChild(this.canvas);

    this._generateMaze();
    this._draw();

    this._keyHandler = (e)=>{
      const dir = { ArrowUp:[0,-1], ArrowDown:[0,1], ArrowLeft:[-1,0], ArrowRight:[1,0] }[e.key];
      if(dir) { e.preventDefault(); this._move(dir[0], dir[1]); }
    };
    window.addEventListener('keydown', this._keyHandler);

    // touch swipe
    let startX=0,startY=0;
    this.canvas.addEventListener('touchstart',(e)=>{ const t=e.touches[0]; startX=t.clientX; startY=t.clientY; });
    this.canvas.addEventListener('touchend',(e)=>{ const t=e.changedTouches[0]; const dx=t.clientX-startX; const dy=t.clientY-startY; if(Math.abs(dx)>Math.abs(dy)){ if(dx>20) this._move(1,0); else if(dx<-20) this._move(-1,0); } else { if(dy>20) this._move(0,1); else if(dy<-20) this._move(0,-1); } });
  }

  _generateMaze(){
    // simple random walls (not perfect maze) for performance
    for(let y=0;y<this.gridSize;y++){
      for(let x=0;x<this.gridSize;x++){
        if(x===0||y===0||x===this.gridSize-1||y===this.gridSize-1) this.walls.add(`${x},${y}`);
        else if(Math.random()<0.22 && !(x===1&&y===1) && !(x===this.gridSize-2&&y===this.gridSize-2)) this.walls.add(`${x},${y}`);
      }
    }
    // ensure start & exit clear
    this.walls.delete('1,1'); this.walls.delete(`${this.gridSize-2},${this.gridSize-2}`);
    this.player = {x:1,y:1}; this.exit = {x:this.gridSize-2,y:this.gridSize-2};
  }

  _draw(){
    const ctx=this.ctx; const w=this.canvas.width; const h=this.canvas.height; ctx.clearRect(0,0,w,h);
    const cellW=w/this.gridSize; const cellH=h/this.gridSize;
    // draw cells
    for(let y=0;y<this.gridSize;y++){
      for(let x=0;x<this.gridSize;x++){
        if(this.walls.has(`${x},${y}`)){ ctx.fillStyle='#333'; ctx.fillRect(x*cellW,y*cellH,cellW,cellH); }
        else { ctx.fillStyle='#fff'; ctx.fillRect(x*cellW,y*cellH,cellW,cellH); }
      }
    }
    // draw exit
    ctx.fillStyle='#ffdd57'; ctx.fillRect(this.exit.x*cellW+cellW*0.1, this.exit.y*cellH+cellH*0.1, cellW*0.8, cellH*0.8);
    // draw player
    ctx.fillStyle='#ff7a00'; ctx.beginPath(); ctx.arc((this.player.x+0.5)*cellW, (this.player.y+0.5)*cellH, Math.min(cellW,cellH)*0.3,0,Math.PI*2); ctx.fill();
  }

  _move(dx,dy){
    const nx=this.player.x+dx, ny=this.player.y+dy;
    if(this.walls.has(`${nx},${ny}`)) return; // collision
    if(nx<0||ny<0||nx>=this.gridSize||ny>=this.gridSize) return;
    this.player.x=nx; this.player.y=ny;
    this._draw();
    this.engine.addScore(50);
    if(this.player.x===this.exit.x && this.player.y===this.exit.y){ this.win(); }
  }

  async update(dt){ /* nothing heavy */ }
  async destroy(){ window.removeEventListener('keydown', this._keyHandler); }

  win(){ this.engine.addScore(1000 + Math.round(this.engine.timer*100)); this.engine.end('completed'); }
}
