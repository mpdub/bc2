const $ = id => document.getElementById(id);
let data = null;
let openId = null;
const fmt = new Intl.DateTimeFormat('en-NZ', {day:'numeric',month:'short',timeZone:'UTC'});
const shortDate = d => fmt.format(new Date(`${d}T12:00:00Z`));
const safe = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const formatName = f => ({MDM:'First class',ODM:'List A',T20:'T20',ODI:'ODI',Test:'Test',IT20:'T20'}[f] || f);
const initials = name => name.split(' ').map(x=>x[0]).slice(0,2).join('');
const allRows = p => [...p.batting, ...p.bowling];
const rows = (p, kind) => p[kind].filter(r => $('format').value === 'all' || r.format === $('format').value);
const recent = p => allRows(p).sort((a,b)=>b.date.localeCompare(a.date))[0];
function figure(r, kind) {
  if (!r) return '<strong class="dash">—</strong><small>No covered innings</small>';
  return kind === 'batting' ? `<strong>${r.runs}${r.out?'':'*'}</strong><small>${r.balls} balls · ${safe(formatName(r.format))}</small>` : `<strong>${r.wickets}/${r.runs}</strong><small>${Math.floor(r.balls / r.balls_per_over)}.${r.balls % r.balls_per_over} ov · ${safe(formatName(r.format))}</small>`;
}
function inningsRows(items, kind) {
  if (!items.length) return '<p class="empty">No covered innings in this format.</p>';
  return items.map(r => `<a class="innings-row" href="${safe(r.url)}" target="_blank" rel="noopener" title="${safe(r.team)} vs ${safe(r.opponent)} · ${safe(r.event || formatName(r.format))}"><span class="date">${safe(shortDate(r.date))}</span><span class="fixture">${safe(r.team)} v ${safe(r.opponent)} <span style="color:#839287">· ${safe(formatName(r.format))}</span></span><span class="figure">${kind === 'batting' ? `${r.runs}${r.out?'':'*'}` : `${r.wickets}/${r.runs}`}</span><span class="subfigure">${kind === 'batting' ? `${r.balls} balls` : `${Math.floor(r.balls/r.balls_per_over)}.${r.balls%r.balls_per_over} ov`}</span><span class="external">↗</span></a>`).join('');
}
function details(p) {
  const bat=rows(p,'batting'), bowl=rows(p,'bowling');
  return `<div class="details" id="details-${safe(p.id)}"><div class="detail-header"><strong>${safe(p.name)} / recent performances</strong><span>Most recent first · score opens match ↗</span></div><div class="two-tables"><section><div class="innings-head"><h3>Batting</h3><span>RUNS · BALLS</span></div>${inningsRows(bat,'batting')}</section><section><div class="innings-head"><h3>Bowling</h3><span>WICKETS/RUNS · OVERS</span></div>${inningsRows(bowl,'bowling')}</section></div></div>`;
}
function card(p) {
  const latest=recent(p), bat=rows(p,'batting')[0], bowl=rows(p,'bowling')[0];
  const expanded=p.id===openId;
  return `<article class="player"><button class="player-summary" type="button" data-id="${safe(p.id)}" aria-expanded="${expanded}" aria-label="${safe(p.name)}, show recent performances"><span class="identity"><span class="monogram">${safe(initials(p.name))}</span><span class="name-wrap"><span class="name">${safe(p.name)}</span><span class="tags">${p.contracted?'<span class="pill">CONTRACTED</span>':''}${p.international?'<span class="pill cap">NZ · 24 MO</span>':''}</span></span></span><span class="latest">${latest?`<strong>${safe(latest.team)} v ${safe(latest.opponent)}</strong><small>${safe(shortDate(latest.date))} · ${safe(latest.event || formatName(latest.format))}</small>`:'<strong>Awaiting covered match</strong><small>—</small>'}</span><span class="stat">${figure(bat,'batting')}</span><span class="stat bowl">${figure(bowl,'bowling')}</span><span class="arrow">›</span></button>${expanded?details(p):''}</article>`;
}
function render() {
  if (!data) return;
  const q=$('search').value.trim().toLowerCase(), cohort=$('cohort').value;
  let list=data.players.filter(p => (cohort==='all'||(cohort==='contracted'?p.contracted:p.international)) && (!q || [p.name,...allRows(p).flatMap(r=>[r.team,r.opponent,r.event])].join(' ').toLowerCase().includes(q)));
  if ($('format').value!=='all') list=list.filter(p=>rows(p,'batting').length||rows(p,'bowling').length);
  $('list').innerHTML=list.length?list.map(card).join(''):'<div class="loading">No players match these filters.</div>';
  $('resultCount').textContent=`SHOWING ${list.length} OF ${data.players.length} PLAYERS`;
}
$('editionYear').textContent=new Date().getFullYear();
$('backTop').addEventListener('click',e=>{e.preventDefault();window.scrollTo({top:0,behavior:'smooth'})});
$('list').addEventListener('click',e=>{const button=e.target.closest('button[data-id]');if(button){openId=openId===button.dataset.id?null:button.dataset.id;render();if(openId)document.getElementById(`details-${CSS.escape(openId)}`)?.scrollIntoView({block:'nearest'});}});
for(const id of ['search','cohort','format']) $(id).addEventListener(id==='search'?'input':'change',render);
fetch('data/players.json').then(r=>{if(!r.ok)throw Error('Data unavailable');return r.json()}).then(json=>{data=json;$('heroCount').textContent=json.players.length;$('freshness').textContent=`SOURCE THROUGH ${json.source_latest || '—'} · REFRESHED ${json.updated}`;$('windowLabel').textContent=`${json.match_count.toLocaleString()} COVERED MATCHES · SELECTION SINCE ${json.window_start}`;render()}).catch(err=>{$('freshness').textContent='DATA UPDATE PENDING';$('list').innerHTML='<div class="loading">Match data is not loaded yet. Run the GitHub Actions update workflow after publishing this page.</div>';console.error(err)});
