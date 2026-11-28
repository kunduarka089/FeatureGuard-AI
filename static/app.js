async function loadData(){
 const [eventsRes, summaryRes]=await Promise.all([fetch('/api/events'),fetch('/api/summary')]);
 const events=await eventsRes.json(), summary=await summaryRes.json();
 document.getElementById('eventCount').textContent=events.length;
 document.getElementById('featureCount').textContent=summary.length;
 const successes=events.filter(e=>e.success).length;
 document.getElementById('successRate').textContent=events.length?Math.round(successes/events.length*100)+'%':'—';
 const target=document.getElementById('featureTable');
 if(!summary.length){target.className='empty';target.textContent='No events yet. Send a test event to begin.';return}
 target.className='';
 target.innerHTML='<table><thead><tr><th>Feature</th><th>Events</th><th>Successes</th><th>Average value</th></tr></thead><tbody>'+
 summary.map(s=>`<tr><td>${escapeHtml(s.feature_name)}</td><td>${s.events}</td><td>${s.successes||0}</td><td>${s.average_value??0}</td></tr>`).join('')+'</tbody></table>';
}
async function sendEvent(){
 const payload={event_name:document.getElementById('eventName').value,feature_name:document.getElementById('featureName').value,success:document.getElementById('eventSuccess').value==='true',value:1};
 const res=await fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const data=await res.json();document.getElementById('eventMessage').textContent=res.ok?'Event recorded. ID: '+data.event_id:'Error: '+data.error;loadData();
}
async function analyse(){
 const target=document.getElementById('analysis');target.textContent='Analysing recorded events…';
 const res=await fetch('/api/ai/analyse',{method:'POST'});const data=await res.json();
 target.textContent=data.analysis||data.message||data.error||JSON.stringify(data,null,2);
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
loadData();
