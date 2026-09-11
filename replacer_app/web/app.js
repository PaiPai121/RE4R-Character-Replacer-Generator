const $ = id => document.getElementById(id);
const state = {targets:[], models:[], target:null, project:null, result:null, busy:false, view:'front', generation:0};
const fileUrl = path => `/api/file?path=${encodeURIComponent(path)}&t=${Date.now()}`;
async function request(url, body, timeout=30000) {
  let r;
  for(let attempt=0;;attempt++) {
    try {r=await fetch(url, {cache:'no-store',signal:AbortSignal.timeout(timeout),...(body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})});break;}
    catch(e) {if(body !== undefined || attempt>=2) throw new Error('本地服务已停止。请重新运行 RE4RCharacterReplacer.exe；启动后可关闭窗口到系统托盘，但不要从托盘菜单退出');await new Promise(resolve=>setTimeout(resolve,500*(attempt+1)));}
  }
  if (!(r.headers.get('Content-Type') || '').includes('application/json')) {
    throw new Error('后台版本过旧或地址不正确。请在启动器中停止并重新启动服务，然后使用自动打开的页面。');
  }
  const data = await r.json();
  if (!r.ok || data.ok === false) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
function status(text, error=false) {$('statusText').textContent=text; $('statusText').parentElement.classList.toggle('error',error);}
function controls() {
  for (const id of ['targetButton','browseButton','sourcePath','scanGameButton','gamePath']) $(id).disabled=state.busy;
  $('previewButton').disabled=state.busy || !state.target || !$('sourcePath').value.trim();
  $('adjustButton').disabled=state.busy || !state.project;
  $('buildButton').disabled=state.busy || !state.project;
  $('progress').hidden=!state.busy;
  $('previewButton').textContent=state.project?'刷新预览':'重试预览';
  $('previewButton').hidden=!state.project && !document.querySelector('.status.error');
}
function clearResult(){state.result=null;$('download').hidden=true;$('buildResult').hidden=true;$('outputPath').value='';}
function showResult(result){state.result=result;$('outputPath').value=result.packageZip;$('download').href=fileUrl(result.packageZip);$('download').hidden=false;$('buildResult').hidden=false;}
function invalidate() {
  localStorage.removeItem('replacer.project');
  state.generation++; state.project=null; clearResult();
  $('previewStage').replaceChildren(); $('viewControls').hidden=true;$('guideLegend').hidden=true;
  const p=document.createElement('p'); p.className='empty-preview';p.textContent=!state.target?'未选择游戏角色':!$('sourcePath').value.trim()?'未选择模型':'准备生成预览';$('previewStage').append(p);
  const name=$('sourcePath').value.trim().split(/[\\/]/).pop();
  $('sourceLabel').textContent=name || '选择文件'; $('selectedSourceText').textContent=name || '—';
  status('等待姿势预览'); controls();
}
function options(root, items, label, select) {
  root.replaceChildren();
  if (!items.length) {const p=document.createElement('p');p.textContent='未找到匹配项';p.className='empty-list';root.append(p);}
  for (const item of items) {
    const b=document.createElement('button'); b.className='option'; b.textContent=label(item);
    if (item.available === false) b.disabled=true;
    const small=document.createElement('small'); small.textContent=item.path || item.description || ''; b.append(small);
    b.addEventListener('click',()=>select(item));root.append(b);
  }
}
function targets() {
  const q=$('targetSearch').value.toLowerCase();
  options($('targetList'),state.targets.filter(t=>`${t.label} ${(t.aliases||[]).join(' ')}`.toLowerCase().includes(q)),t=>t.label,t=>{
    state.target=t; $('selectedTargetText').textContent=t.label; $('targetDialog').close();invalidate(); schedulePreview();
  });
}
function showPreview() {
  const files=state.result || state.project?.files; const path=files?.previewImages?.[state.view] || files?.previewImage;
  if (!path) return;
  const img=new Image();img.alt=`${state.view} 姿势参考`;img.src=fileUrl(path);
  img.onerror=()=>status('预览文件不可用，请重新生成',true);
  $('previewStage').replaceChildren(img);$('viewControls').hidden=false;
  $('guideLegend').hidden=!!state.result;$('viewLabel').textContent=state.result?'生成结果':'姿势对齐';
  document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===state.view);b.disabled=!files?.previewImages?.[b.dataset.view] && b.dataset.view!=='front';});
}
let debounce;
function schedulePreview() {clearTimeout(debounce);if(state.target && $('sourcePath').value.trim()) debounce=setTimeout(()=>preview().catch(failure),600);}
function failure(e){state.busy=false; status(e.message,true);$('jobBox').textContent=e.stack||e.message;$('diagnostics').open=true;controls();}
async function runJob(endpoint,payload,label,keepResult=false) {
  state.busy=true;status(label);controls();if(!keepResult)clearResult();
  const started=Date.now();let lastResponse=null;
  $('taskProgress').hidden=false;$('previewStage').setAttribute('aria-busy','true');
  $('taskPhase').textContent=label;
  const tick=()=>{
    const seconds=Math.floor((Date.now()-started)/1000);
    $('taskTime').textContent=`已用时 ${Math.floor(seconds/60)} 分 ${seconds%60} 秒`;
    const stale=Date.now()-(lastResponse || started);
    $('taskHeartbeat').textContent=stale>15000?'后台响应较慢，正在确认连接':lastResponse?'后台已响应 · 处理中':'正在提交任务';
  };
  tick();const timer=setInterval(tick,1000);
  try {
    const {jobId}=await request(endpoint,payload);
    for (;;) {
      if(Date.now()-started>3600000) throw new Error('等待任务超时，模型工作区仍已保留');
      const {job}=await request(`/api/jobs?id=${jobId}`);
      lastResponse=Date.now();tick();
      $('taskPhase').textContent=job.status==='complete'?'正在载入结果':job.status==='queued'?'任务已排队':label;
      $('jobBox').textContent=job.error || `${job.status}\n${(job.stdout||'').slice(-4000)}\n${(job.stderr||'').slice(-1000)}`;
      if (job.status==='failed') throw new Error(job.error||'任务失败');
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
    ? await runJob('/api/refresh-preview',{projectId:state.project.id},'正在读取已保存的姿势')
    : await runJob('/api/create-pose-workspace',{sourceModel:$('sourcePath').value.trim(),targetId:state.target.id},'正在生成姿势预览');
  if(generation!==state.generation) return;
  state.project=result.project;localStorage.setItem('replacer.project',state.project.id);clearResult();state.view='front';showPreview();status('姿势待确认');controls();
}
async function refresh() {
  const health=await request('/api/health');
  if(health.application!=='re4r-replacer' || !health.current) throw new Error('软件文件已更新，但后台尚未重启。请在启动器中停止并重新启动服务。');
  const targetData=await request('/api/targets');const modelData=await request('/api/models');
  state.targets=targetData.targets;state.models=modelData.models.filter(m=>m.kind!=='prop');
  $('gamePath').value=targetData.gamePath || '';
  if(state.target && !state.targets.some(t=>t.id===state.target.id && t.available)){state.target=null;invalidate();}
  targets();knownModels();
  $('scanStatus').textContent=`${targetData.scanned?'游戏资源':'本地参考'} · ${state.targets.length} 个角色`;$('connectionStatus').textContent='本地连接';
  controls();
  return targetData;
}
$('targetButton').onclick=()=>{$('targetDialog').showModal();$('targetSearch').focus();};
document.querySelectorAll('.close').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('targetSearch').oninput=targets;
$('sourcePath').oninput=()=>{invalidate();schedulePreview();};
$('browseButton').onclick=async()=>{
  if(state.busy)return;
  $('browseButton').disabled=true;$('sourceLabel').textContent='等待系统窗口…';status('请选择模型文件');
  try{
    const model=await request('/api/pick-model',{},600000);
    if(model.cancelled){status('已取消选择');return;}
    chooseModel(model);
  }catch(e){
    if(e.message.includes('本地服务已停止')){status(e.message,true);return;}
    $('modelDialog').showModal();pickerTab(true);$('pickerStatus').textContent='系统文件窗口不可用，请使用备用目录浏览器：'+e.message;
  }finally{controls();if(!$('sourcePath').value.trim())$('sourceLabel').textContent='选择模型';}
};
function chooseModel(model){$('sourcePath').value=model.path;const folder=model.directory||directory?.path;if(folder)localStorage.setItem('replacer.modelDirectory',folder);$('modelDialog').close();invalidate();schedulePreview();}
function knownModels(){const q=$('modelSearch').value.toLowerCase();options($('modelList'),state.models.filter(m=>m.name.toLowerCase().includes(q)),m=>m.name,chooseModel);}
$('modelSearch').oninput=knownModels;
let directory=null,directoryRequest=0;
function fileOptions(){const q=$('fileSearch').value.toLowerCase();options($('fileList'),(directory?.entries||[]).filter(e=>e.name.toLowerCase().includes(q)),e=>e.directory?e.name+' /':e.name,e=>e.directory?loadDirectory(e.path):chooseModel(e));}
async function loadDirectory(path='',fallback=true){
  const token=++directoryRequest;$('pickerStatus').textContent='正在读取文件夹';$('fileList').replaceChildren();$('parentFolder').disabled=true;
  try{const result=await request('/api/model-directory?path='+encodeURIComponent(path));if(token!==directoryRequest)return;
    directory=result;localStorage.setItem('replacer.modelDirectory',result.path);$('folderPath').value=result.path;$('parentFolder').disabled=!result.parent;$('fileSearch').value='';fileOptions();$('pickerStatus').textContent='';
    $('driveList').replaceChildren();for(const drive of result.drives){const b=document.createElement('button');b.textContent=drive;b.onclick=()=>loadDirectory(drive);$('driveList').append(b);}
  }catch(e){if(token===directoryRequest){directory=null;if(path&&fallback){localStorage.removeItem('replacer.modelDirectory');return loadDirectory('',false);}$('pickerStatus').textContent=e.message;}}
}
function pickerTab(disk){$('knownModelsPanel').hidden=disk;$('diskModelsPanel').hidden=!disk;$('knownModelsTab').setAttribute('aria-selected',String(!disk));$('diskModelsTab').setAttribute('aria-selected',String(disk));if(disk&&!directory)loadDirectory(localStorage.getItem('replacer.modelDirectory')||'');}
$('knownModelsTab').onclick=()=>pickerTab(false);$('diskModelsTab').onclick=()=>pickerTab(true);
$('fileSearch').oninput=fileOptions;$('folderForm').onsubmit=e=>{e.preventDefault();loadDirectory($('folderPath').value.trim());};$('parentFolder').onclick=()=>{if(directory?.parent)loadDirectory(directory.parent);};
$('copyOutput').onclick=async()=>{try{await navigator.clipboard.writeText($('outputPath').value);$('copyOutput').textContent='已复制';setTimeout(()=>$('copyOutput').textContent='复制路径',1500);}catch(e){$('outputPath').focus();$('outputPath').select();status('路径已选中，可复制');}};
async function scanGame() {
  if(state.busy) return;
  $('targetDialog').close();
  await runJob('/api/scan-game',{gamePath:$('gamePath').value.trim()},'正在扫描游戏角色',true);
  await refresh(); status('角色扫描完成');
}
$('refreshButton').onclick=()=>location.reload();
$('scanGameButton').onclick=()=>scanGame().catch(failure);
$('previewButton').onclick=()=>preview().catch(failure);
$('adjustButton').onclick=async()=>{
  if(state.busy || !state.project?.files?.poseBlend) return;
  state.busy=true;controls();status('正在打开 Blender');
  try{
    const opened=await request('/api/open-blender',{blend:state.project.files.poseBlend});
    status('已启动 Blender · 等待姿势保存');
    $('jobBox').textContent=`Blender PID: ${opened.pid}\n${opened.blend}`;
    $('diagnostics').open=true;
  }catch(e){failure(e);}finally{state.busy=false;controls();}
};
$('buildButton').onclick=async()=>{try{const result=await runJob('/api/build-mod',{projectId:state.project.id},'正在生成并校验 Mod');if(!result.packageZip) throw new Error('构建没有返回本次任务的发布包');showResult(result);state.view='front';showPreview();status(result.experimental?'测试包已生成 · 待游戏验证':'生成完成 · 待游戏验证');}catch(e){failure(e);}};
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
      $('selectedTargetText').textContent=target.label;$('sourcePath').value=project.sourceModel;
      const name=project.sourceModel.split(/[\\/]/).pop();$('sourceLabel').textContent=name;$('selectedSourceText').textContent=name;
      showPreview();status('已恢复保存的工作区');controls();
      if(project.lastBuild?.packageZip){showResult(project.lastBuild);showPreview();$('viewLabel').textContent='上次生成结果';status('已恢复上次生成结果 · 待游戏验证');}
    }
  }
}
initialize().catch(failure);
