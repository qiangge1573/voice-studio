const api = require('../../utils/api')

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const p = (n) => (n < 10 ? '0' + n : '' + n)
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
}

Page({
  data: {
    videoPath: '',
    videoName: '',
    sizeText: '',
    voices: [],
    voiceIndex: -1,
    voiceNames: [],
    script: '',
    mode: 'overlay',
    loading: true,
    submitting: false,
    videoUrl: '',
    tasks: []
  },

  onShow() {
    this.loadVoices()
    this.loadTasks()
  },

  loadVoices() {
    this.setData({ loading: true })
    api
      .request('/api/voices')
      .then((list) => {
        const voices = list || []
        let index = this.data.voiceIndex
        if (index < 0 && voices.length > 0) index = 0
        this.setData({
          voices,
          voiceIndex: index,
          voiceNames: voices.map((v) => v.name),
          loading: false
        })
      })
      .catch((err) => {
        this.setData({ loading: false })
        wx.showToast({ title: err.message || '加载失败', icon: 'none' })
      })
  },

  loadTasks() {
    api
      .request('/api/dubbing/tasks')
      .then((list) => {
        const tasks = (list || []).map((t) =>
          Object.assign({}, t, { created_at_text: formatDate(t.created_at) })
        )
        this.setData({ tasks })
      })
      .catch(() => {})
  },

  chooseVideo() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const f = res.tempFiles[0]
        const size = f.size || 0
        this.setData({
          videoPath: f.tempFilePath,
          videoName: f.name || '已选择视频',
          sizeText: size ? (size / 1024 / 1024).toFixed(1) + 'MB' : '',
          videoUrl: ''
        })
      }
    })
  },

  onScript(e) {
    this.setData({ script: e.detail.value })
  },

  onMode(e) {
    this.setData({ mode: e.detail.value })
  },

  onVoice(e) {
    this.setData({ voiceIndex: Number(e.detail.value) })
  },

  submit() {
    const { videoPath, voices, voiceIndex, script, mode, submitting } = this.data
    if (submitting) return
    const voice = voices[voiceIndex]
    if (!videoPath) return wx.showToast({ title: '请先选择视频', icon: 'none' })
    if (!voice) return wx.showToast({ title: '请先创建音色', icon: 'none' })
    const lines = script.split('\n').filter((l) => l.trim())
    if (!lines.length) return wx.showToast({ title: '请输入配音台本', icon: 'none' })

    this.setData({ submitting: true, videoUrl: '' })
    api
      .upload('/api/dubbing', videoPath, {
        voice_id: String(voice.id),
        script,
        mode
      })
      .then(({ task_id }) => this.poll(task_id, 0))
      .catch((err) => {
        this.setData({ submitting: false })
        wx.showToast({ title: err.message || '提交失败', icon: 'none' })
      })
  },

  poll(taskId, tries) {
    if (tries > 100) {
      this.setData({ submitting: false })
      return wx.showToast({ title: '配音超时，请重试', icon: 'none' })
    }
    setTimeout(() => {
      api
        .request('/api/dubbing/tasks/' + taskId)
        .then((task) => {
          if (task.status === 'done') {
            this.setData({
              submitting: false,
              videoUrl: api.authUrl(task.video_url)
            })
            wx.showToast({ title: '配音完成', icon: 'success' })
            this.loadTasks()
          } else if (task.status === 'failed') {
            this.setData({ submitting: false })
            wx.showToast({ title: task.error || '配音失败', icon: 'none' })
          } else {
            this.poll(taskId, tries + 1)
          }
        })
        .catch(() => this.poll(taskId, tries + 1))
    }, 2000)
  },

  previewTask(e) {
    const url = e.currentTarget.dataset.url
    if (url) this.setData({ videoUrl: api.authUrl(url) })
  },

  goCreateVoice() {
    wx.navigateTo({ url: '/pages/record/record' })
  }
})
