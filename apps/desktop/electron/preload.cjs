const { contextBridge, ipcRenderer, webUtils } = require('electron')

contextBridge.exposeInMainWorld('clioDesktop', {
  getConnection: profile => ipcRenderer.invoke('clio:connection', profile),
  touchBackend: profile => ipcRenderer.invoke('clio:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('clio:gateway:ws-url', profile),
  installGatewayService: () => ipcRenderer.invoke('clio:gateway:install'),
  getBootProgress: () => ipcRenderer.invoke('clio:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('clio:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('clio:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('clio:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('clio:connection-config:test', payload),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('clio:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('clio:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('clio:connection-config:oauth-logout', remoteUrl),
  profile: {
    get: () => ipcRenderer.invoke('clio:profile:get'),
    set: name => ipcRenderer.invoke('clio:profile:set', name)
  },
  api: request => ipcRenderer.invoke('clio:api', request),
  notify: payload => ipcRenderer.invoke('clio:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('clio:requestMicrophoneAccess'),
  readFileDataUrl: filePath => ipcRenderer.invoke('clio:readFileDataUrl', filePath),
  readFileText: filePath => ipcRenderer.invoke('clio:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('clio:selectPaths', options),
  writeClipboard: text => ipcRenderer.invoke('clio:writeClipboard', text),
  saveImageFromUrl: url => ipcRenderer.invoke('clio:saveImageFromUrl', url),
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('clio:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('clio:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('clio:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('clio:watchPreviewFile', url),
  stopPreviewFileWatch: id => ipcRenderer.invoke('clio:stopPreviewFileWatch', id),
  setTitleBarTheme: payload => ipcRenderer.send('clio:titlebar-theme', payload),
  setPreviewShortcutActive: active => ipcRenderer.send('clio:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('clio:openExternal', url),
  fetchLinkTitle: url => ipcRenderer.invoke('clio:fetchLinkTitle', url),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('clio:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('clio:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('clio:setting:defaultProjectDir:pick')
  },
  revealLogs: () => ipcRenderer.invoke('clio:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('clio:logs:recent'),
  readDir: dirPath => ipcRenderer.invoke('clio:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('clio:fs:gitRoot', startPath),
  terminal: {
    dispose: id => ipcRenderer.invoke('clio:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('clio:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('clio:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('clio:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `clio:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)
      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `clio:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)
      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('clio:close-preview-requested', listener)
    return () => ipcRenderer.removeListener('clio:close-preview-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('clio:open-updates', listener)
    return () => ipcRenderer.removeListener('clio:open-updates', listener)
  },
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('clio:window-state-changed', listener)
    return () => ipcRenderer.removeListener('clio:window-state-changed', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('clio:preview-file-changed', listener)
    return () => ipcRenderer.removeListener('clio:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('clio:backend-exit', listener)
    return () => ipcRenderer.removeListener('clio:backend-exit', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('clio:power-resume', listener)
    return () => ipcRenderer.removeListener('clio:power-resume', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('clio:boot-progress', listener)
    return () => ipcRenderer.removeListener('clio:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.cjs (apps/desktop/electron/bootstrap-runner.cjs).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('clio:bootstrap:get'),
  resetBootstrap: () => ipcRenderer.invoke('clio:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('clio:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('clio:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('clio:bootstrap:event', listener)
    return () => ipcRenderer.removeListener('clio:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('clio:version'),
  updates: {
    check: () => ipcRenderer.invoke('clio:updates:check'),
    apply: opts => ipcRenderer.invoke('clio:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('clio:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('clio:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('clio:updates:progress', listener)
      return () => ipcRenderer.removeListener('clio:updates:progress', listener)
    }
  }
})
