(()=>{
 const date=s=>s?new Date(s).toLocaleString('en-GB',{timeZone:'UTC',dateStyle:'medium',timeStyle:'short'})+' UTC':'Not yet retrieved';
 function renderEvidence(d){
  const stale=Date.now()-Date.parse(d.generated_at)>48*3600000;
  const cached=Object.values(d.source_status||{}).some(s=>s.status!=='ok')||d.sea_level?.status!=='ok'||d.regional_status?.status!=='ok';
  const updated=document.querySelector('#updated');updated.textContent=`Source check: ${date(d.generated_at)} · ${stale?'Update overdue':cached?'Some data are saved or unavailable — see individual indicators':'Daily checks completed'}`;updated.classList.toggle('data-warning',stale||cached);
  function stamp(el,s){const n=document.createElement('span');n.className='retrieval'+(s?.status==='ok'?'':' data-warning');n.textContent=`Last successful check: ${date(s?.last_success)}.${s?.status==='ok'?'':' Saved data — latest update unavailable.'}`;el.parentElement.querySelector('.retrieval')?.remove();el.parentElement.append(n)}
  for(const [key,id] of Object.entries({temperature:'kTemp',co2:'kCo2',sea_ice:'kIce',ocean_heat:'kOcean'}))stamp(document.getElementById(id),d.source_status?.[key]);
  const glacier=document.querySelector('.kpis .kpi:nth-child(4)');const g=document.createElement('span');g.className='retrieval';g.textContent='Published assessment · manually reviewed, not a live measurement.';glacier.append(g);
  const sea=d.sea_level,rows=sea?.rows||[],k=document.querySelector('#kSea');
  if(!rows.length){k.textContent='Unavailable';document.querySelector('#seaStatus').textContent='Satellite data unavailable. No values have been inferred.';return}
  const last=rows.at(-1),year=Math.floor(last.year_decimal);k.textContent=(last.value_cm>=0?'+':'')+fmt(last.value_cm)+' cm';k.nextElementSibling.textContent=`NASA/JPL · ${year} · vs 1993 mean`;stamp(k,sea);
  const yearStart=Date.UTC(year,0,1),yearEnd=Date.UTC(year+1,0,1),lastDate=new Date(yearStart+(last.year_decimal-year)*(yearEnd-yearStart)).toLocaleDateString('en-GB',{timeZone:'UTC',dateStyle:'medium'});
  document.querySelector('#seaStatus').textContent=`Measurements: 1993–${lastDate}. Last successful check: ${date(sea.last_success)}. ${sea.status==='ok'?'Publication checked daily; measurements update when NASA/JPL releases a new version.':'Latest check failed; saved measurements shown.'}`;
  document.querySelector('#seaMethod').textContent=sea.method;document.querySelector('#seaSource').href=sea.record_url;
  const w=920,h=290,l=60,r=18,t=28,b=38,min=Math.min(0,...rows.map(x=>x.value_cm))-1,max=Math.max(...rows.map(x=>x.value_cm))+1;
  const x=v=>l+(v-1993)/(last.year_decimal-1993)*(w-l-r),y=v=>t+(max-v)/(max-min)*(h-t-b);
  const ticks=Array.from({length:5},(_,i)=>min+i*(max-min)/4);
  document.querySelector('#seaChart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Satellite-derived sea level change from the 1993 average in centimetres. Annual values are available below."><text x="${l}" y="18" fill="currentColor" font-size="15">cm above 1993 average · measurements only</text>${ticks.map(v=>`<line x1="${l}" x2="${w-r}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" opacity=".15"/><text x="${l-8}" y="${y(v)+5}" text-anchor="end" fill="currentColor" font-size="15">${fmt(v)}</text>`).join('')}<polyline points="${rows.map(v=>`${x(v.year_decimal)},${y(v.value_cm)}`).join(' ')}" fill="none" stroke="#61d8ed" stroke-width="2.5"/>${[1993,2000,2010,2020,year].filter((v,i,a)=>a.indexOf(v)===i).map(v=>`<text x="${x(v)}" y="${h-10}" text-anchor="${v===1993?'start':v===year?'end':'middle'}" fill="currentColor" font-size="15">${v}</text>`).join('')}</svg>`;
  const annual={};rows.forEach(v=>(annual[Math.floor(v.year_decimal)]??=[]).push(v));
  document.querySelector('#seaTable').innerHTML='<table class="heat-table"><thead><tr><th>Year</th><th>Average change (cm)</th><th>Coverage</th></tr></thead><tbody>'+Object.entries(annual).map(([year,a])=>`<tr><td>${year}</td><td>${fmt(a.reduce((s,v)=>s+v.value_cm,0)/a.length,2)}</td><td>${a.length} smoothed samples${a[0].year_decimal-Number(year)>.04||a.at(-1).year_decimal-Number(year)<.96?' · partial year':''}</td></tr>`).join('')+'</tbody></table>';
 }
 window.addEventListener('climate-data-rendered',e=>renderEvidence(e.detail));if(typeof DB!=='undefined'&&DB)renderEvidence(DB);
})();
