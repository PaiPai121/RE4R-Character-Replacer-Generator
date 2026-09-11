(() => {
  const messages = {
    'zh-CN': {
      documentTitle:'RE4 · 人物替换', appHeading:'人物替换', switchLanguage:'Switch to English', refreshUi:'刷新界面',
      viewerAria:'模型预览', noModel:'未选择模型', taskRunning:'任务进行中', front:'正面', back:'背面', side:'侧面',
      leftHand:'左手', rightHand:'右手', sourceGuide:'源模型', targetLeft:'目标左侧', targetRight:'目标右侧', poseAlignment:'姿势对齐',
      settings:'替换设置', gameCharacter:'游戏角色', selectCharacter:'选择角色', replacementModel:'替换模型', selectModel:'选择模型',
      modelPathAria:'模型文件路径', modelPathPlaceholder:'或输入模型路径', waitingSelection:'等待选择', refreshPreview:'刷新预览', retryPreview:'重试预览',
      adjustBlender:'在 Blender 中调整', optional:'可选', generateMod:'生成 Mod', buildResultAria:'生成结果', savedLocally:'已保存到本机',
      downloadMod:'下载 Mod', fileLocation:'文件位置', copyPath:'复制路径', copied:'已复制', taskHistory:'任务记录', noTasks:'尚无任务',
      localResources:'本地资源', connecting:'连接中', chooseGameCharacter:'选择游戏角色', close:'关闭', searchCharacter:'搜索角色',
      gameDirectory:'游戏目录', scanGame:'扫描游戏', chooseModel:'选择模型', modelSource:'模型来源', knownModels:'已有模型', browseFiles:'浏览文件',
      searchModel:'搜索模型', parentFolder:'上一级文件夹', folderPath:'文件夹路径', openFolder:'打开文件夹', drives:'磁盘', searchFolder:'搜索当前文件夹',
      serviceStopped:'本地服务已停止。请重新运行 RE4RCharacterReplacer.exe；启动后可关闭窗口到系统托盘，但不要从托盘菜单退出',
      staleBackend:'后台版本过旧或地址不正确。请在启动器中停止并重新启动服务，然后使用自动打开的页面。',
      noGameCharacter:'未选择游戏角色', preparingPreview:'准备生成预览', chooseFile:'选择文件', waitingPose:'等待姿势预览', noMatches:'未找到匹配项',
      previewAlt:'{view} 姿势参考', previewUnavailable:'预览文件不可用，请重新生成', generatedResult:'生成结果', elapsed:'已用时 {minutes} 分 {seconds} 秒',
      backgroundSlow:'后台响应较慢，正在确认连接', backgroundActive:'后台已响应 · 处理中', submitting:'正在提交任务', loadingResult:'正在载入结果',
      queued:'任务已排队', taskTimeout:'等待任务超时，模型工作区仍已保留', taskFailed:'任务失败', readingPose:'正在读取已保存的姿势',
      generatingPreview:'正在生成姿势预览', posePending:'姿势待确认', backendRestart:'软件文件已更新，但后台尚未重启。请在启动器中停止并重新启动服务。',
      gameResources:'游戏资源', localReference:'本地参考', characterCount:'{count} 个角色', localConnection:'本地连接', waitingSystemWindow:'等待系统窗口…',
      chooseModelFile:'请选择模型文件', selectionCancelled:'已取消选择', pickerUnavailable:'系统文件窗口不可用，请使用备用目录浏览器：{error}',
      readingFolder:'正在读取文件夹', selectedForCopy:'路径已选中，可复制', scanningCharacters:'正在扫描游戏角色', scanComplete:'角色扫描完成',
      openingBlender:'正在打开 Blender', blenderStarted:'已启动 Blender · 等待姿势保存', buildingMod:'正在生成并校验 Mod', buildMissingPackage:'构建没有返回本次任务的发布包',
      testPackageDone:'测试包已生成 · 待游戏验证', buildDone:'生成完成 · 待游戏验证', restoredWorkspace:'已恢复保存的工作区',
      restoredBuild:'已恢复上次生成结果 · 待游戏验证', lastBuild:'上次生成结果', buildStage:'正在构建并转换模型', validateStage:'正在进行独立导出验证',
      targetAvailable:'可生成测试包 · 未经游戏内验收', targetUnavailable:'已扫描到资源 · 兼容配置尚不可用',
      leon:'里昂', ashley:'艾什莉', ada:'艾达', luis:'路易斯', wesker:'威斯克', merchant:'商人'
    },
    en: {
      documentTitle:'RE4 · Character Replacer', appHeading:'Character Replacer', switchLanguage:'切换到中文', refreshUi:'Refresh interface',
      viewerAria:'Model preview', noModel:'No model selected', taskRunning:'Task in progress', front:'Front', back:'Back', side:'Side',
      leftHand:'Left hand', rightHand:'Right hand', sourceGuide:'Source model', targetLeft:'Target left', targetRight:'Target right', poseAlignment:'Pose alignment',
      settings:'Replacement settings', gameCharacter:'Game character', selectCharacter:'Select character', replacementModel:'Replacement model', selectModel:'Select model',
      modelPathAria:'Model file path', modelPathPlaceholder:'Or enter a model path', waitingSelection:'Waiting for selection', refreshPreview:'Refresh preview', retryPreview:'Retry preview',
      adjustBlender:'Adjust in Blender', optional:'Optional', generateMod:'Generate Mod', buildResultAria:'Build result', savedLocally:'Saved on this computer',
      downloadMod:'Download Mod', fileLocation:'File location', copyPath:'Copy path', copied:'Copied', taskHistory:'Task history', noTasks:'No tasks yet',
      localResources:'Local resources', connecting:'Connecting', chooseGameCharacter:'Select game character', close:'Close', searchCharacter:'Search characters',
      gameDirectory:'Game directory', scanGame:'Scan game', chooseModel:'Select model', modelSource:'Model source', knownModels:'Known models', browseFiles:'Browse files',
      searchModel:'Search models', parentFolder:'Parent folder', folderPath:'Folder path', openFolder:'Open folder', drives:'Drives', searchFolder:'Search this folder',
      serviceStopped:'The local service has stopped. Run RE4RCharacterReplacer.exe again. You may close the launcher window to the system tray, but do not exit from the tray menu.',
      staleBackend:'The background service is outdated or this address is incorrect. Stop and restart the service in the launcher, then use the page it opens automatically.',
      noGameCharacter:'No game character selected', preparingPreview:'Ready to generate preview', chooseFile:'Select file', waitingPose:'Waiting for pose preview', noMatches:'No matching items',
      previewAlt:'{view} pose reference', previewUnavailable:'The preview file is unavailable. Generate it again.', generatedResult:'Generated result', elapsed:'Elapsed: {minutes}m {seconds}s',
      backgroundSlow:'Background response is slow; checking the connection', backgroundActive:'Background active · Processing', submitting:'Submitting task', loadingResult:'Loading result',
      queued:'Task queued', taskTimeout:'The task wait timed out. The model workspace has been preserved.', taskFailed:'Task failed', readingPose:'Reading the saved pose',
      generatingPreview:'Generating pose preview', posePending:'Pose awaiting confirmation', backendRestart:'The software files changed, but the background service was not restarted. Stop and restart it in the launcher.',
      gameResources:'Game resources', localReference:'Local reference', characterCount:'{count} characters', localConnection:'Local connection', waitingSystemWindow:'Waiting for system file window…',
      chooseModelFile:'Select a model file', selectionCancelled:'Selection cancelled', pickerUnavailable:'The system file window is unavailable. Use the fallback folder browser: {error}',
      readingFolder:'Reading folder', selectedForCopy:'The path is selected and ready to copy', scanningCharacters:'Scanning game characters', scanComplete:'Character scan complete',
      openingBlender:'Opening Blender', blenderStarted:'Blender started · Waiting for the pose to be saved', buildingMod:'Building and validating Mod', buildMissingPackage:'The build did not return a release package for this task.',
      testPackageDone:'Test package generated · In-game validation required', buildDone:'Build complete · In-game validation required', restoredWorkspace:'Restored saved workspace',
      restoredBuild:'Restored the previous build · In-game validation required', lastBuild:'Previous build result', buildStage:'Building and converting model', validateStage:'Running independent export validation',
      targetAvailable:'Can generate a test package · Not validated in game', targetUnavailable:'Resources found · Compatibility profile unavailable',
      leon:'Leon', ashley:'Ashley', ada:'Ada', luis:'Luis', wesker:'Wesker', merchant:'Merchant'
    }
  };

  const errorReplacements = [
    ['文件选择入口已更新，请刷新页面后点击“选择模型”', 'The file picker was updated. Refresh the page and click “Select model” again.'],
    ['后台需要重启，当前任务未启动。请在启动器中停止并重新启动服务。', 'The background service must be restarted. This task was not started. Stop and restart the service in the launcher.'],
    ['系统文件选择器只在完整 EXE 发布包中可用', 'The system file picker is available only in the complete EXE release package.'],
    ['请选择 PMX、PMD、FBX 或 BLEND 模型文件', 'Select a PMX, PMD, FBX, or BLEND model file.'],
    ['游戏目录缺少 re_chunk_000.pak', 'The game directory does not contain re_chunk_000.pak.'],
    ['姿势文件不存在', 'The pose file does not exist.'],
    ['Blender 正在保存，请保存完成后重试', 'Blender is still saving. Wait for it to finish and try again.'],
    ['构建校验结果不匹配，拒绝打包', 'Build validation did not match, so packaging was stopped.'],
    ['缺少安装清单', 'The installation manifest is missing.'],
    ['文件名或扩展名太长', 'The file name or extension is too long.'],
    ['该角色缺少完整资源映射，未生成 Mod', 'This character does not have a complete resource mapping, so no Mod was generated.'],
    ['导出未返回本次任务的验证请求', 'The export did not return a validation request for this task.'],
    ['请选择本机磁盘上的绝对文件夹路径', 'Select an absolute folder path on a local drive.'],
    ['这不是文件夹，请选择包含模型的文件夹', 'This is not a folder. Select the folder containing the model.'],
    ['文件夹内容过多，请直接输入更具体的子文件夹路径', 'This folder contains too many items. Enter a more specific subfolder path.'],
    ['系统文件选择器请求目录无效', 'The system file picker received an invalid folder.'],
    ['主程序未能打开系统文件窗口，请确认启动器仍在运行', 'The launcher could not open the system file window. Make sure the launcher is still running.'],
    ['系统文件窗口等待超时', 'The system file window timed out.'],
    ['系统文件选择器启动失败', 'The system file picker failed to start.'],
    ['游戏文件在扫描期间发生变化，请更新完成后重试', 'The game files changed during scanning. Wait for the update to finish and try again.'],
    ['PAK 索引工具返回的数据格式无效', 'The PAK index tool returned data in an invalid format.'],
    ['缺少 PAK 索引工具，请运行软件安装脚本', 'The PAK index tool is missing. Re-extract the complete application package.'],
    ['单个参考资源超出大小限制', 'A reference resource exceeds the size limit.'],
    ['构建缓存必须位于本机磁盘的绝对路径', 'The build cache must use an absolute path on a local drive.'],
    ['构建缓存路径过长，请设置更短的 REPLACER_BUILD_ROOT', 'The build cache path is too long. Set REPLACER_BUILD_ROOT to a shorter path.'],
    ['无法创建唯一的构建任务目录', 'Could not create a unique build task folder.'],
    ['游戏索引扫描完成', 'Game index scan complete.'],
    ['全部角色配置均与当前游戏版本匹配，无需重新提取', 'All character profiles already match this game version; no extraction is needed.'],
    ['已完成，跳过', 'complete; skipped'], ['正在准备角色配置', 'Preparing character profile'],
    ['正在提取参考资源', 'Extracting reference resources'], ['扫描游戏资源索引', 'Scanning game resource index'],
    ['已运行', 'elapsed'], ['秒', 'seconds'], ['任务目录', 'Task folder'],
    ['里昂', 'Leon'], ['艾什莉', 'Ashley'], ['艾达', 'Ada'], ['路易斯', 'Luis'], ['威斯克', 'Wesker'], ['商人', 'Merchant']
  ];
  const errorPrefixes = [
    ['无法打开文件夹：', 'Could not open folder: '], ['无法打开系统文件选择器：', 'Could not open the system file picker: '],
    ['无法打开 Blender：', 'Could not open Blender: '], ['PAK 索引读取失败：', 'Failed to read the PAK index: '],
    ['PAK 索引工具返回了无效数据：', 'The PAK index tool returned invalid data: '], ['游戏资源不存在：', 'Game resource not found: '],
    ['参考资源提取在 180 秒内没有完成：', 'Reference resource extraction did not finish within 180 seconds: '],
    ['参考资源提取失败：', 'Failed to extract reference resources: '], ['姿势预览失败：', 'Pose preview failed: '],
    ['自动构建未通过，未生成发布包：', 'The automatic build failed; no release package was generated: '], ['构建超时，现场保留：', 'The build timed out. Work files were preserved at: ']
  ];

  const normalize = value => value && value.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
  const queryLanguage = new URLSearchParams(location.search).get('lang');
  let language = normalize(queryLanguage || localStorage.getItem('replacer.language') || navigator.language || 'en');
  const t = (key, values={}) => {
    let value = messages[language][key] ?? messages.en[key] ?? key;
    for (const [name, replacement] of Object.entries(values)) value = value.replaceAll(`{${name}}`, String(replacement));
    return value;
  };
  const localizeError = message => {
    if (language === 'zh-CN' || !message) return message;
    let translated = String(message);
    for (const [source, target] of errorReplacements) translated = translated.replaceAll(source, target);
    for (const [source, target] of errorPrefixes) translated = translated.replaceAll(source, target);
    return translated;
  };
  const apply = () => {
    document.documentElement.lang = language;
    document.title = t('documentTitle');
    document.querySelectorAll('[data-i18n]').forEach(element => { element.textContent = t(element.dataset.i18n); });
    for (const attribute of ['placeholder','title','aria-label']) {
      document.querySelectorAll(`[data-i18n-${attribute}]`).forEach(element => element.setAttribute(attribute, t(element.dataset[`i18n${attribute.split('-').map(part=>part[0].toUpperCase()+part.slice(1)).join('')}`])));
    }
    const button = document.getElementById('languageButton');
    if (button) { button.textContent = language === 'zh-CN' ? 'EN' : '中文'; button.title = t('switchLanguage'); button.setAttribute('aria-label', t('switchLanguage')); }
  };
  const setLanguage = async value => {
    language = normalize(value);
    localStorage.setItem('replacer.language', language);
    try {
      await fetch('/api/language', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({language})});
    } catch (_) {
      // Browser persistence still works when the launcher service is unavailable.
    }
    const url = new URL(location.href); url.searchParams.set('lang', language); history.replaceState(null, '', url);
    location.reload();
  };
  window.ReplacerI18n = {t, apply, setLanguage, localizeError, get language(){ return language; }};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply); else apply();
})();
