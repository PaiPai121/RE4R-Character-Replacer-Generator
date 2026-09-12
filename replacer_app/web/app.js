const $ = id => document.getElementById(id);
const i18n = window.ReplacerI18n;
const t = (key, values) => i18n.t(key, values);
const state = {targets:[], models:[], target:null, project:null, result:null, busy:false, view:'front', generation:0};
const fileUrl = path => `/api/file?path=${encodeURIComponent(path)}&t=${Date.now()}`;
async function request(url, body, timeout=30000) {
  let r;
  for(let attempt=0;;attempt++) {
    try {r=await fetch(url, {cache:'no-store',signal:AbortSignal.timeout(timeout),...(body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})});break;}
    catch(e) {if(body !== undefined || attempt>=2) throw new Error(t('serviceStopped'));await new Promise(resolve=>setTimeout(resolve,500*(attempt+1)));}
  }
  if (!(r.headers.get('Content-Type') || '').includes('application/json')) {
    throw new Error(t('staleBackend'));
  }
  const data = await r.json();
  if (!r.ok || data.ok === false) throw new Error(i18n.localizeError(data.error) || `HTTP ${r.status}`);
  return data;
}
function status(text, error=false) {$('statusText').textContent=text; $('statusText').parentElement.classList.toggle('error',error);}
function controls() {
  for (const id of ['targetButton','browseButton','sourcePath','scanGameButton','gamePath']) $(id).disabled=state.busy;
  $('previewButton').disabled=state.busy || !state.target || !$('sourcePath').value.trim();
  $('adjustButton').disabled=state.busy || !state.project;
  $('buildButton').disabled=state.busy || !state.project;
  $('progress').hidden=!state.busy;
  $('previewButton').textContent=state.project?t('refreshPreview'):t('retryPreview');
  $('previewButton').hidden=!state.project && !document.querySelector('.status.error');
}
function clearResult(){state.result=null;$('download').hidden=true;$('buildResult').hidden=true;$('outputPath').value='';}
function showResult(result){state.result=result;$('outputPath').value=result.packageZip;$('download').href=fileUrl(result.packageZip);$('download').hidden=false;$('buildResult').hidden=false;}
function invalidate() {
  localStorage.removeItem('replacer.project');
  state.generation++; state.project=null; clearResult();
  $('previewStage').replaceChildren(); $('viewControls').hidden=true;$('guideLegend').hidden=true;
  const p=document.createElement('p'); p.className='empty-preview';p.textContent=!state.target?t('noGameCharacter'):!$('sourcePath').value.trim()?t('noModel'):t('preparingPreview');$('previewStage').append(p);
  const name=$('sourcePath').value.trim().split(/[\\/]/).pop();
  $('sourceLabel').textContent=name || t('chooseFile'); $('selectedSourceText').textContent=name || '—';
  status(t('waitingPose')); controls();
}
function options(root, items, label, select, describe=item=>item.path || item.description || '') {
  root.replaceChildren();
  if (!items.length) {const p=document.createElement('p');p.textContent=t('noMatches');p.className='empty-list';root.append(p);}
  for (const item of items) {
    const b=document.createElement('button'); b.className='option'; b.textContent=label(item);
    if (item.available === false) b.disabled=true;
    const small=document.createElement('small'); small.textContent=describe(item); b.append(small);
    b.addEventListener('click',()=>select(item));root.append(b);
  }
}
function targetLabel(item){return t(item.id) || item.label;}
function targetDescription(item){
  if(item.available)return t('targetAvailable');
  if(item.issue==='modded-game-archive')return t('targetModdedArchive');
  if(item.issue==='missing-game-resource')return t('targetMissingResource');
  return t('targetUnavailable');
}
function targets() {
  const q=$('targetSearch').value.toLowerCase();
  options($('targetList'),state.targets.filter(item=>`${targetLabel(item)} ${item.label} ${(item.aliases||[]).join(' ')}`.toLowerCase().includes(q)),targetLabel,item=>{
    state.target=item; $('selectedTargetText').textContent=targetLabel(item); $('targetDialog').close();invalidate(); schedulePreview();
  },targetDescription);
}
function showPreview() {
  const files=state.result || state.project?.files; const path=files?.previewImages?.[state.view] || files?.previewImage;
  if (!path) return;
  const img=new Image();img.alt=t('previewAlt',{view:t(state.view==='hands'?'leftHand':state.view)});img.src=fileUrl(path);
  img.onerror=()=>status(t('previewUnavailable'),true);
  $('previewStage').replaceChildren(img);$('viewControls').hidden=false;
  $('guideLegend').hidden=!!state.result;$('viewLabel').textContent=state.result?t('generatedResult'):t('poseAlignment');
  document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===state.view);b.disabled=!files?.previewImages?.[b.dataset.view] && b.dataset.view!=='front';});
}
let debounce;
function schedulePreview() {clearTimeout(debounce);if(state.target && $('sourcePath').value.trim()) debounce=setTimeout(()=>preview().catch(failure),600);}
function failure(e){state.busy=false; const message=i18n.localizeError(e.message);status(message,true);$('jobBox').textContent=i18n.localizeError(e.stack)||message;$('diagnostics').open=true;controls();}
async function runJob(endpoint,payload,label,keepResult=false) {
  state.busy=true;status(label);controls();if(!keepResult)clearResult();
  const started=Date.now();let lastResponse=null;
  $('taskProgress').hidden=false;$('previewStage').setAttribute('aria-busy','true');
  $('taskPhase').textContent=label;
  const tick=()=>{
    const seconds=Math.floor((Date.now()-started)/1000);
    $('taskTime').textContent=t('elapsed',{minutes:Math.floor(seconds/60),seconds:seconds%60});
    const stale=Date.now()-(lastResponse || started);
    $('taskHeartbeat').textContent=stale>15000?t('backgroundSlow'):lastResponse?t('backgroundActive'):t('submitting');
  };
  tick();const timer=setInterval(tick,1000);
  try {
    const {jobId}=await request(endpoint,payload);
    for (;;) {
      if(Date.now()-started>3600000) throw new Error(t('taskTimeout'));
      const {job}=await request(`/api/jobs?id=${jobId}`);
      lastResponse=Date.now();tick();
      const activeLabel=job.stage==='build'?t('buildStage'):job.stage==='validate'?t('validateStage'):label;
      $('taskPhase').textContent=job.status==='complete'?t('loadingResult'):job.status==='queued'?t('queued'):activeLabel;
      $('jobBox').textContent=i18n.localizeError(job.error) || `${job.status}\n${i18n.localizeError((job.stdout||'').slice(-4000))}\n${i18n.localizeError((job.stderr||'').slice(-1000))}`;
      if (job.status==='failed') throw new Error(i18n.localizeError(job.error)||t('taskFailed'));
      if (job.status==='complete') return job.result;
      await new Promise(resolve=>setTimeout(resolve,1200));
    }
  } finally {clearInterval(timer);$('taskProgress').hidden=true;$('previewStage').setAttribute('aria-busy','false');state.busy=false;controls();}
}
async function preview() {
  if(state.busy || !state.target || !$('sourcePath').value.trim()) return;
  clearTimeout(debounce);
  const generation=state.generation;
  const result=state.project
    ? await runJob('/api/refresh-preview',{projectId:state.project.id},t('readingPose'))
    : await runJob('/api/create-pose-workspace',{sourceModel:$('sourcePath').value.trim(),targetId:state.target.id},t('generatingPreview'));
  if(generation!==state.generation) return;
  state.project=result.project;localStorage.setItem('replacer.project',state.project.id);clearResult();state.view='front';showPreview();status(t('posePending'));controls();
}
async function refresh() {
  const health=await request('/api/health');
  if(health.application!=='re4r-replacer' || !health.current) throw new Error(t('backendRestart'));
  const targetData=await request('/api/targets');const modelData=await request('/api/models');
  state.targets=targetData.targets;state.models=modelData.models.filter(m=>m.kind!=='prop');
  $('gamePath').value=targetData.gamePath || '';
  if(state.target && !state.targets.some(t=>t.id===state.target.id && t.available)){state.target=null;invalidate();}
  targets();knownModels();
  $('scanStatus').textContent=`${targetData.scanned?t('gameResources'):t('localReference')} · ${t('characterCount',{count:state.targets.length})}`;$('connectionStatus').textContent=t('localConnection');
  controls();
  return targetData;
}
$('targetButton').onclick=()=>{$('targetDialog').showModal();$('targetSearch').focus();};
$('languageButton').onclick=()=>i18n.setLanguage(i18n.language==='zh-CN'?'en':'zh-CN');
document.querySelectorAll('.close').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('targetSearch').oninput=targets;
$('sourcePath').oninput=()=>{invalidate();schedulePreview();};
$('browseButton').onclick=async()=>{
  if(state.busy)return;
  $('browseButton').disabled=true;$('sourceLabel').textContent=t('waitingSystemWindow');status(t('chooseModelFile'));
  try{
    const model=await request('/api/pick-model',{},610000);
    if(model.cancelled){status(t('selectionCancelled'));return;}
    chooseModel(model);
  }catch(e){
    if(e.message===t('serviceStopped')){status(e.message,true);return;}
    $('modelDialog').showModal();pickerTab(true);$('pickerStatus').textContent=t('pickerUnavailable',{error:e.message});
  }finally{controls();if(!$('sourcePath').value.trim())$('sourceLabel').textContent=t('selectModel');}
};
function chooseModel(model){$('sourcePath').value=model.path;const folder=model.directory||directory?.path;if(folder)localStorage.setItem('replacer.modelDirectory',folder);$('modelDialog').close();invalidate();schedulePreview();}
function knownModels(){const q=$('modelSearch').value.toLowerCase();options($('modelList'),state.models.filter(m=>m.name.toLowerCase().includes(q)),m=>m.name,chooseModel);}
$('modelSearch').oninput=knownModels;
let directory=null,directoryRequest=0;
function fileOptions(){const q=$('fileSearch').value.toLowerCase();options($('fileList'),(directory?.entries||[]).filter(e=>e.name.toLowerCase().includes(q)),e=>e.directory?e.name+' /':e.name,e=>e.directory?loadDirectory(e.path):chooseModel(e));}
async function loadDirectory(path='',fallback=true){
  const token=++directoryRequest;$('pickerStatus').textContent=t('readingFolder');$('fileList').replaceChildren();$('parentFolder').disabled=true;
  try{const result=await request('/api/model-directory?path='+encodeURIComponent(path));if(token!==directoryRequest)return;
    directory=result;localStorage.setItem('replacer.modelDirectory',result.path);$('folderPath').value=result.path;$('parentFolder').disabled=!result.parent;$('fileSearch').value='';fileOptions();$('pickerStatus').textContent='';
    $('driveList').replaceChildren();for(const drive of result.drives){const b=document.createElement('button');b.textContent=drive;b.onclick=()=>loadDirectory(drive);$('driveList').append(b);}
  }catch(e){if(token===directoryRequest){directory=null;if(path&&fallback){localStorage.removeItem('replacer.modelDirectory');return loadDirectory('',false);}$('pickerStatus').textContent=e.message;}}
}
function pickerTab(disk){$('knownModelsPanel').hidden=disk;$('diskModelsPanel').hidden=!disk;$('knownModelsTab').setAttribute('aria-selected',String(!disk));$('diskModelsTab').setAttribute('aria-selected',String(disk));if(disk&&!directory)loadDirectory(localStorage.getItem('replacer.modelDirectory')||'');}
$('knownModelsTab').onclick=()=>pickerTab(false);$('diskModelsTab').onclick=()=>pickerTab(true);
$('fileSearch').oninput=fileOptions;$('folderForm').onsubmit=e=>{e.preventDefault();loadDirectory($('folderPath').value.trim());};$('parentFolder').onclick=()=>{if(directory?.parent)loadDirectory(directory.parent);};
$('copyOutput').onclick=async()=>{try{await navigator.clipboard.writeText($('outputPath').value);$('copyOutput').textContent=t('copied');setTimeout(()=>$('copyOutput').textContent=t('copyPath'),1500);}catch(e){$('outputPath').focus();$('outputPath').select();status(t('selectedForCopy'));}};
async function scanGame() {
  if(state.busy) return;
  $('targetDialog').close();
  await runJob('/api/scan-game',{gamePath:$('gamePath').value.trim()},t('scanningCharacters'),true);
  await refresh(); status(t('scanComplete'));
}
$('refreshButton').onclick=()=>location.reload();
$('scanGameButton').onclick=()=>scanGame().catch(failure);
$('previewButton').onclick=()=>preview().catch(failure);
$('adjustButton').onclick=async()=>{
  if(state.busy || !state.project?.files?.poseBlend) return;
  state.busy=true;controls();status(t('openingBlender'));
  try{
    const opened=await request('/api/open-blender',{blend:state.project.files.poseBlend});
    status(t('blenderStarted'));
    $('jobBox').textContent=`Blender PID: ${opened.pid}\n${opened.blend}`;
    $('diagnostics').open=true;
  }catch(e){failure(e);}finally{state.busy=false;controls();}
};
$('buildButton').onclick=async()=>{try{const result=await runJob('/api/build-mod',{projectId:state.project.id},t('buildingMod'));if(!result.packageZip) throw new Error(t('buildMissingPackage'));showResult(result);state.view='front';showPreview();status(result.experimental?t('testPackageDone'):t('buildDone'));}catch(e){failure(e);}};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{state.view=b.dataset.view;showPreview();});
async function initialize() {
  const saved=localStorage.getItem('replacer.project');
  const inventory=await refresh();
  if(!inventory.scanned && inventory.gamePath) await scanGame();
  if(saved) {
    const {projects}=await request('/api/projects');
    const project=projects.find(p=>p.id===saved && p.files?.poseBlend);
    const target=state.targets.find(t=>t.id===project?.target && t.available);
    if(project && target) {
      state.target=target;state.project=project;
      $('selectedTargetText').textContent=targetLabel(target);$('sourcePath').value=project.sourceModel;
      const name=project.sourceModel.split(/[\\/]/).pop();$('sourceLabel').textContent=name;$('selectedSourceText').textContent=name;
      showPreview();status(t('restoredWorkspace'));controls();
      if(project.lastBuild?.packageZip){showResult(project.lastBuild);showPreview();$('viewLabel').textContent=t('lastBuild');status(t('restoredBuild'));}
    }
  }
}
initialize().catch(failure);
