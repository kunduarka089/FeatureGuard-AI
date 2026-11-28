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
 const data=await res.json();document.getElementById('eventMessage').textContent=res.ok?'Event recorded. ID: '+data.event_id:'Error: '+data.error;loadData();scanAnomalies();
}
async function analyse(){
 const target=document.getElementById('analysis');target.textContent='Analysing recorded events…';
 const res=await fetch('/api/ai/analyse',{method:'POST'});const data=await res.json();
 target.textContent=data.analysis||data.message||data.error||JSON.stringify(data,null,2);
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
loadData();
scanAnomalies();
setInterval(scanAnomalies, 30000);


async function scanAnomalies(){
 const target=document.getElementById('anomalyResults');
 if(!target)return;
 try{
  const res=await fetch('/api/monitor/anomalies');
  const data=await res.json();
  if(!res.ok)throw new Error(data.error||'Monitor request failed.');
  if(data.alerts.length){
   target.innerHTML='<div class="alert-list">'+data.alerts.map(a=>
    '<article class="alert-item"><strong>'+escapeHtml(a.feature_name)+'</strong> <span class="status-pill">'+escapeHtml(a.severity.toUpperCase())+'</span><p>'+
    escapeHtml(a.message)+'</p><small>'+a.events+' events checked · '+Math.round(a.failure_rate*100)+'% failure rate</small></article>'
   ).join('')+'</div><p class="hint">'+escapeHtml(data.message)+'</p>';
  }else if(data.insufficient_data.length){
   target.innerHTML='<p>'+escapeHtml(data.message)+'</p><ul>'+data.insufficient_data.map(f=>
    '<li><strong>'+escapeHtml(f.feature_name)+'</strong>: '+f.events+' / '+data.thresholds.minimum_events+' minimum events</li>'
   ).join('')+'</ul>';
  }else{
   target.textContent=data.message;
  }
 }catch(err){target.textContent='Monitor unavailable: '+err.message}
}


let pendingApprovalId = null;

async function loadFlags(){
 const target=document.getElementById('flagList');
 target.textContent='Loading Flagsmith flags…';
 try{
  const res=await fetch('/api/flagsmith/flags');
  const data=await res.json();
  if(!res.ok || !data.configured) throw new Error(data.error||'Flagsmith is not configured.');
  if(!data.flags.length){target.textContent='No feature states were returned for this environment.';return}
  target.innerHTML='<table><thead><tr><th>Flag</th><th>State</th><th>Action</th></tr></thead><tbody>'+
   data.flags.map(f=>'<tr><td>'+escapeHtml(f.name)+'</td><td>'+(f.enabled?'ON':'OFF')+'</td><td>'+
   (f.enabled && f.name==='new_checkout'?'<button onclick="requestRollback(\'new_checkout\')">Prepare rollback</button>':'—')+
   '</td></tr>').join('')+'</tbody></table>';
 }catch(err){target.textContent='Flagsmith unavailable: '+err.message}
}

async function requestRollback(featureName){
 const status=document.getElementById('rollbackStatus');
 const area=document.getElementById('approvalArea');
 status.textContent='Preparing rollback…';area.innerHTML='';pendingApprovalId=null;
 try{
  const res=await fetch('/api/rollback/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature_name:featureName,reason:'Demo incident: checkout failures increased after the new checkout flag was enabled.'})});
  const data=await res.json();
  if(!res.ok) throw new Error(data.error||'Could not prepare rollback.');
  pendingApprovalId=data.approval_id;
  status.textContent='Review: '+data.feature_name+' will be switched OFF. Reason: '+data.reason+' Nothing has changed yet.';
  area.innerHTML='<button class="primary" onclick="approveRollback()">Approve and switch OFF</button> <button onclick="cancelRollback()">Cancel</button>';
 }catch(err){status.textContent='Rollback request failed: '+err.message}
}

async function approveRollback(){
 if(!pendingApprovalId)return;
 const status=document.getElementById('rollbackStatus');
 const area=document.getElementById('approvalArea');
 status.textContent='Applying approved rollback and verifying Flagsmith…';
 const id=pendingApprovalId;pendingApprovalId=null;area.innerHTML='';
 try{
  const res=await fetch('/api/rollback/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approval_id:id})});
  const data=await res.json();
  if(!res.ok) throw new Error(data.error||'Rollback failed.');
  status.textContent=data.message;loadFlags();
 }catch(err){status.textContent='Rollback failed: '+err.message}
}
function cancelRollback(){
 pendingApprovalId=null;
 document.getElementById('approvalArea').innerHTML='';
 document.getElementById('rollbackStatus').textContent='Rollback cancelled. No flag was changed.';
}
loadFlags();
