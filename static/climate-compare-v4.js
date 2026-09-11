/* All map and comparison values use the same country-climatology product. */
const q=s=>document.querySelector(s);
const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pathwayNames={ssp126:'Low · SSP1–2.6',ssp245:'Intermediate · SSP2–4.5',ssp370:'High · SSP3–7.0',ssp585:'Very high · SSP5–8.5'};
let DB,map,eventMap,markers,eventMarkers;
function fmt(v,d=1){return v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('en-GB',{maximumFractionDigits:d,minimumFractionDigits:d})}
function heat(c,s,p){const x=c.heat_scenarios?.[s]?.[p];return x&&Number.isFinite(x.median)?x:null}
function range(x){return x?`${fmt(x.median)} days · model range ${fmt(x.p10)}–${fmt(x.p90)}`:'No data'}
function colour(v){return v>180?'#ff745c':v>90?'#edc46c':v>30?'#43dfaa':'#61d8ed'}
function drawCountries(){
 if(!DB||!markers)return;
 const p=q('#heatPeriod').value,s=q('#heatPathway').value;
 markers.clearLayers();
 const rows=DB.countries.filter(c=>heat(c,s,p)).sort((a,b)=>heat(b,s,p).median-heat(a,s,p).median);
 rows.forEach(c=>{const x=heat(c,s,p);L.circleMarker([c.lat,c.lon],{radius:5+Math.min(365,x.median)/365*8,color:colour(x.median),fillOpacity:.72,weight:1}).bindPopup(`<b>${escapeHtml(c.name)}</b><br>${escapeHtml(p)} · ${escapeHtml(pathwayNames[s])}<br>${range(x)}<br>Daily maximum at least 35°C; country average.`).addTo(markers)});
 q('#ranking').innerHTML=rows.length?rows.map((c,i)=>`<div class="rank"><em>${i+1}</em><div><b>${escapeHtml(c.name)}</b><small>${escapeHtml(c.region)}</small></div><strong>${fmt(heat(c,s,p).median)}<small>${fmt(heat(c,s,p).p10)}–${fmt(heat(c,s,p).p90)} days</small></strong></div>`).join(''):'<p class="profile-help">This selection has no verified data. Missing values are not zero.</p>';
 q('#heatContext').textContent=`${p} · ${pathwayNames[s]} · ${rows.length} countries. Daily maximum ≥35°C. Middle model result; ranges show P10–P90 model spread, not guaranteed limits. Source data retrieved ${DB.heat_metadata?.retrieved_at||'date unavailable'}.${DB.regional_status?.status==='ok'?'':' Saved dataset — latest update unavailable.'} Map colours: blue ≤30, green >30–90, yellow >90–180, red >180 days/year.`;
 drawComparison();
}
function drawComparison(){
 if(!DB)return;
 const p=q('#comparePeriod').value,a=q('#compareA').value,b=q('#compareB').value;
 q('#compareCaption').textContent=`${p}: ${pathwayNames[a]} versus ${pathwayNames[b]}. Same period, threshold and country averaging. Differences are between ensemble medians, not paired-model uncertainty estimates.`;
 const rows=DB.countries.filter(c=>heat(c,a,p)&&heat(c,b,p)).sort((c,d)=>c.name.localeCompare(d.name));
 q('#scenarios').innerHTML=`<div class="heat-table-wrap"><table class="heat-table"><thead><tr><th scope="col">Country</th><th scope="col">${escapeHtml(pathwayNames[a])}<small>Days/year · P10–P90</small></th><th scope="col">${escapeHtml(pathwayNames[b])}<small>Days/year · P10–P90</small></th><th scope="col">Difference<br>B − A</th></tr></thead><tbody>${rows.map(c=>{const x=heat(c,a,p),y=heat(c,b,p),delta=y.median-x.median;return `<tr><th scope="row">${escapeHtml(c.name)}</th><td><b>${fmt(x.median)}</b><small>${fmt(x.p10)}–${fmt(x.p90)}</small></td><td><b>${fmt(y.median)}</b><small>${fmt(y.p10)}–${fmt(y.p90)}</small></td><td>${delta>0?'+':''}${fmt(delta)} days</td></tr>`}).join('')}</tbody></table></div>`;
 if(!rows.length)q('#scenarios').innerHTML='<p class="profile-help">Comparison unavailable. No values have been inferred.</p>';
}
function render(d){
 DB=d;
 q('#kTemp').textContent=`${d.latest.temperature.value>=0?'+':''}${fmt(d.latest.temperature.value,2)} °C`;
 q('#kCo2').textContent=fmt(d.latest.co2.value)+' ppm';q('#kIce').textContent=fmt(d.latest.sea_ice.value,2)+' million km²';q('#kOcean').textContent='#'+d.latest.ocean_heat.rank;q('#oceanValue').textContent=fmt(d.latest.ocean_heat.value)+' ×10²² J';
 if(typeof L!=='undefined'){
  map=L.map('map',{minZoom:2}).setView([18,10],2);
  const tiles='https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=YOUR_CARTO_BROWSER_KEY';
  L.tileLayer(tiles,{attribution:'&copy; OpenStreetMap &copy; CARTO'}).addTo(map);markers=L.layerGroup().addTo(map);drawCountries();
  eventMap=L.map('eventMap',{minZoom:2}).setView([18,10],2);L.tileLayer(tiles,{attribution:'&copy; OpenStreetMap &copy; CARTO'}).addTo(eventMap);eventMarkers=L.layerGroup().addTo(eventMap);
  const counts={};(d.events?.events||[]).forEach(e=>{counts[e.type]=(counts[e.type]||0)+1;L.circleMarker([e.lat,e.lon],{radius:3,color:e.type==='wildfire'?'#ff745c':'#61d8ed',fillOpacity:.6,weight:0}).bindPopup(`<b>${escapeHtml(e.name)}</b><br>${escapeHtml(e.type)}<br>Attribution: ${escapeHtml(e.attribution)}`).addTo(eventMarkers)});
  q('#eventStats').innerHTML=Object.entries(counts).map(([k,v])=>`<div><b>${v}</b><span>${escapeHtml(k)} signals</span></div>`).join('')||'<p>No hazard signals available in this snapshot.</p>';
 }else{q('#map').textContent='Map unavailable. The comparison table remains available.';drawComparison()}
 q('#sourceRows').innerHTML=d.sources.map(s=>`<div class="source"><b>${escapeHtml(s.name)}</b><span>${escapeHtml(s.measure)}</span><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">Source ↗</a></div>`).join('');
 q('#loading').classList.add('hide');window.dispatchEvent(new CustomEvent('climate-data-rendered',{detail:d}));
}
fetch('/climate/api/data',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(render).catch(()=>{q('#loading').classList.add('hide');q('#updated').textContent='Data temporarily unavailable. Please retry.'});
['heatPeriod','heatPathway'].forEach(id=>q('#'+id).addEventListener('change',drawCountries));
['comparePeriod','compareA','compareB'].forEach(id=>q('#'+id).addEventListener('change',drawComparison));
q('#views').onclick=e=>{const b=e.target.closest('[data-view]');if(!b)return;document.querySelectorAll('.navtabs button').forEach(t=>{t.classList.toggle('active',t===b);t.setAttribute('aria-pressed',String(t===b))});document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===b.dataset.view));setTimeout(()=>{map?.invalidateSize();eventMap?.invalidateSize()},20)};
document.querySelectorAll('[data-open-view]').forEach(b=>b.onclick=()=>{q(`#views [data-view="${b.dataset.openView}"]`)?.click();q('#'+b.dataset.openView)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'})});
q('#refresh').onclick=async()=>{const b=q('#refresh');b.disabled=true;b.textContent='Checking sources…';try{const r=await fetch('/climate/api/refresh',{method:'POST'});if(!r.ok)throw Error();location.reload()}catch{q('#updated').textContent='Refresh failed; previously loaded values remain visible.'}finally{b.disabled=false;b.textContent='↻ REFRESH'}};
