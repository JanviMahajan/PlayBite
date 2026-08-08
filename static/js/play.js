// play.js - client-side helpers for PlayBite customer flow
(function(){
  window.Playbite = window.Playbite || {};

  window.Playbite.lang = (function(){
    function get(){ return localStorage.getItem('play_lang') || (navigator.language||'en').split('-')[0]; }
    function set(l){ localStorage.setItem('play_lang', l); if(l==='ar') document.documentElement.dir='rtl'; else document.documentElement.dir='ltr'; }
    return {get, set};
  })();

})();
