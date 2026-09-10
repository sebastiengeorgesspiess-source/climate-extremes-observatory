(()=>{
 function status(d){
  const age=(Date.now()-Date.parse(d.generated_at))/3600000;
  const cached=Object.values(d.source_status||{}).some(s=>s.status!=='ok');
  const updated=document.querySelector('#updated');
  updated.textContent=`Last retrieval: ${new Date(d.generated_at).toLocaleString('en-GB',{timeZone:'UTC'})} UTC · ${age>48?'Update overdue':cached?'Some sources unavailable; saved values shown':'Daily source checks'}`;
  updated.classList.toggle('data-warning',age>48||cached);
  const labels={temperature:['kTemp','NASA · annual change vs 1951–1980'],co2:['kCo2','NOAA · Mauna Loa annual mean'],sea_ice:['kIce','NSIDC · completed September mean'],ocean_heat:['kOcean','NOAA · annual ocean heat, upper 2,000 m']};
  const container=document.querySelector('#sourceRows');
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Measurement periods and last successful source checks';details.append(summary);
  Object.entries(labels).forEach(([key,[id,label]])=>{
   const rows=d.series[key],last=rows.at(-1),status=d.source_status?.[key];
   const el=document.getElementById(id);const note=el?.nextElementSibling;if(note)note.textContent=`${label} · ${last.year}${key==='ocean_heat'?` · rank within ${rows[0].year}–${last.year}`:''}`;
   const p=document.createElement('p');p.textContent=`${label}: ${rows[0].year}–${last.year}. Last successful retrieval: ${new Date(status?.last_success||d.generated_at).toLocaleString('en-GB',{timeZone:'UTC'})} UTC. ${status?.status==='cached'?'Latest attempt failed; previous values retained.':'Checked daily; new annual values depend on the publisher.'}`;
   if(status?.url){const a=document.createElement('a');a.href=status.url;a.textContent=' Download original data ↗';a.target='_blank';a.rel='noopener';p.append(a)}details.append(p);
  });container.prepend(details);
 }
 window.addEventListener('climate-data-rendered',e=>status(e.detail));
 if(typeof DB!=='undefined'&&DB)status(DB);
})();
