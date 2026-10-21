(function(){
  const $=id=>document.getElementById(id);
  const list=$("players");
  const state={who:"all",games:"all",q:"",open:new Set()};
  let data=null;
  let thisYear=new Date().getFullYear();

  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const day=new Intl.DateTimeFormat("en-NZ",{day:"numeric",month:"short",timeZone:"UTC"});
  const dayYear=new Intl.DateTimeFormat("en-NZ",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"});
  const date=iso=>{const d=new Date(`${iso}T12:00:00Z`);return (d.getUTCFullYear()===thisYear?day:dayYear).format(d)};

  const formatName=r=>({Test:"Test",ODI:"ODI",T20:r.team==="New Zealand"?"T20I":"T20",IT20:"T20",MDM:"First-class",ODM:"List A"}[r.format]||r.format);
  const inGames=r=>state.games==="all"||(state.games==="nz"?r.team==="New Zealand":state.games==="T20"?r.format==="T20"||r.format==="IT20":r.format===state.games);
  const rows=(p,kind)=>p[kind].filter(inGames);
  const contract=p=>p.contract==="central"?"Central contract":p.contract==="casual"?"Casual contract":p.contracted?"Contracted":"";
  const overs=r=>`${Math.floor(r.balls/r.balls_per_over)}${r.balls%r.balls_per_over?`.${r.balls%r.balls_per_over}`:""}`;

  const bat=r=>({text:`${r.runs}${r.out?"":"*"}`,tier:r.runs>=100?"huge":r.runs>=50?"big":""});
  const bowl=r=>({text:`${r.wickets}/${r.runs}`,tier:r.wickets>=5?"huge":r.wickets>=3?"big":""});

  function formLine(items,kind){
    if(!items.length)return `<span class="form-line"><span class="none">${state.games!=="all"?"None in these games":kind==="batting"?"Hasn't batted":"Hasn't bowled"}</span></span>`;
    const read=kind==="batting"?bat:bowl;
    return `<span class="form-line">${items.map(r=>{const f=read(r);return `<span${f.tier?` class="${f.tier}"`:""}>${esc(f.text)}</span>`}).join("")}</span>`;
  }

  function meta(p){
    const all=[...rows(p,"batting"),...rows(p,"bowling")].sort((a,b)=>b.date.localeCompare(a.date));
    const last=all[0];
    const bits=[contract(p)];
    if(last)bits.push(`Last played ${date(last.date)} ${last.team==="New Zealand"?`for New Zealand v ${last.opponent}`:`for ${last.team}`}`);
    else if(!p.batting.length&&!p.bowling.length)bits.push("No games in the data yet");
    return bits.filter(Boolean).map(esc).join(" · ");
  }

  function innings(items,kind){
    if(!items.length)return `<p class="empty">${kind==="batting"?"No innings":"No bowling"}${state.games==="all"?" in the last two years":" in these games"}.</p>`;
    return `<ol class="innings">${items.map(r=>{
      const f=kind==="batting"?bat(r):bowl(r);
      const sub=kind==="batting"?`${r.balls} ball${r.balls===1?"":"s"}`:`${overs(r)} over${r.balls===r.balls_per_over?"":"s"}`;
      const where=`${r.team} v ${r.opponent}`;
      const what=[r.event,formatName(r)].filter((x,i,a)=>x&&a.indexOf(x)===i).join(", ");
      return `<li><a href="${esc(r.url)}" target="_blank" rel="noopener"><span class="date">${esc(date(r.date))}</span><span class="where">${esc(where)}<small>${esc(what)}</small></span><span class="figure${f.tier==="huge"?" huge":""}">${esc(f.text)}<small>${esc(sub)}</small></span></a></li>`;
    }).join("")}</ol>`;
  }

  function player(p){
    const open=state.open.has(p.id);
    const id=`p-${p.id.replace(/[^\w-]/g,"")}`;
    const b=rows(p,"batting"),w=rows(p,"bowling");
    return `<li class="player">
      <button class="player-row" type="button" data-id="${esc(p.id)}" aria-expanded="${open}" aria-controls="${id}">
        <span class="who"><span class="name">${esc(p.name)}</span><span class="meta">${meta(p)}</span></span>
        <span class="bat"><span class="form-label">Batting</span>${formLine(b,"batting")}</span>
        <span class="bowl"><span class="form-label">Bowling</span>${formLine(w,"bowling")}</span>
        <span class="toggle" aria-hidden="true"></span>
      </button>
      <div class="details" id="${id}"${open?"":" hidden"}>
        ${open?`<div><h3>Batting</h3>${innings(b,"batting")}</div><div><h3>Bowling</h3>${innings(w,"bowling")}</div>`:""}
      </div>
    </li>`;
  }

  function render(){
    if(!data)return;
    const q=state.q.trim().toLowerCase();
    const shown=data.players.filter(p=>{
      if(state.who==="contracted"&&!p.contracted)return false;
      if(state.who==="international"&&!p.international)return false;
      if(state.games!=="all"&&!rows(p,"batting").length&&!rows(p,"bowling").length)return false;
      if(!q)return true;
      return [p.name,...p.batting,...p.bowling].map(x=>typeof x==="string"?x:`${x.team} ${x.opponent} ${x.event}`).join(" ").toLowerCase().includes(q);
    });
    const total=data.players.length;
    $("count").textContent=shown.length===total?`${total} players`:`${shown.length} of ${total} players`;
    list.innerHTML=shown.length?shown.map(player).join(""):`<li class="nothing">Nobody matches that.</li>`;
  }

  function freshness(json){
    const updated=new Date(`${json.updated}T12:00:00Z`);
    const days=Math.floor((Date.now()-updated)/864e5);
    const newest=json.source_latest?` The newest game in here is from ${date(json.source_latest)}.`:"";
    return days>3?`Last updated ${date(json.updated)}, which is a while ago, so the daily update might be stuck.${newest}`:`Updated ${date(json.updated)}.${newest}`;
  }

  document.querySelectorAll("[data-who],[data-games]").forEach(button=>{
    button.addEventListener("click",()=>{
      const key=button.dataset.who?"who":"games";
      state[key]=button.dataset[key];
      document.querySelectorAll(`[data-${key}]`).forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
      render();
    });
  });
  $("search").addEventListener("input",e=>{state.q=e.target.value;render()});
  list.addEventListener("click",e=>{
    const row=e.target.closest(".player-row");
    if(!row)return;
    const id=row.dataset.id;
    state.open.has(id)?state.open.delete(id):state.open.add(id);
    render();
    list.querySelector(`[data-id="${CSS.escape(id)}"]`)?.focus({preventScroll:true});
  });

  fetch("data/players.json",{cache:"no-cache"})
    .then(r=>{if(!r.ok)throw new Error(r.status);return r.json()})
    .then(json=>{
      data=json;
      thisYear=Number(json.updated.slice(0,4));
      // Older snapshots only knew about central contracts.
      data.players.forEach(p=>{if(p.contract===undefined)p.contract=p.contracted?"central":null});
      $("freshness").textContent=freshness(json);
      render();
    })
    .catch(err=>{
      $("freshness").textContent="Couldn't load the scores. Try refreshing in a minute.";
      console.error(err);
    });

  // The pig
  const footer=document.querySelector(".site-footer");
  const pig=document.querySelector(".pig-button");
  if(footer){
    const footerObserver=new IntersectionObserver(entries=>{
      if(entries.some(entry=>entry.isIntersecting)){
        footer.classList.add("is-visible");
        footerObserver.disconnect();
      }
    },{threshold:.25});
    footerObserver.observe(footer);
  }
  if(pig){
    const reducedMotion=window.matchMedia("(prefers-reduced-motion: reduce)");
    const note=document.querySelector(".pig-note");
    let busy=false;
    let resetTimer;
    const settle=()=>{pig.classList.remove("is-hopping");busy=false};
    const showNote=()=>{footer.classList.add("is-visible");note.textContent="oink."};
    const hideNote=()=>{if(!pig.matches(":hover")&&document.activeElement!==pig)note.textContent=""};
    pig.addEventListener("pointerenter",showNote);
    pig.addEventListener("pointerleave",hideNote);
    pig.addEventListener("focus",showNote);
    pig.addEventListener("blur",hideNote);
    pig.addEventListener("click",()=>{
      if(busy)return;
      clearTimeout(resetTimer);
      note.textContent="oink.";
      if(!reducedMotion.matches){busy=true;pig.classList.add("is-hopping")}
      resetTimer=setTimeout(()=>{settle();hideNote()},1200);
    });
    pig.addEventListener("animationend",event=>{if(event.animationName==="pig-hop")settle()});
    reducedMotion.addEventListener("change",()=>{if(reducedMotion.matches)settle()});
  }
})();
