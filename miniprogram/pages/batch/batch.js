const api = require('../../utils/api')

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const p = (n) => (n < 10 ? '0' + n : '' + n)
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
}

Page({
  data: {
    voices: [],
    voiceIndex: -1,
    voiceNames: [],
    text: '',
    lineCount: 0,
    loading: true,
    submitting: false,
    result: null,
    tasks: [],
    playingIndex: -1
  },

  onLoad() {
    this.audio = wx.createInnerAudioContext()
  },

  onShow() {
    this.loadVoices()
    this.loadTasks()
  },

  onUnload() {
    if (this.audio) this.audio.destroy()
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
      .request('/api/batch/tasks')
      .then((list) => {
        const tasks = (list || []).map((t) =>
          Object.assign({}, t, { created_at_text: formatDate(t.created_at) })
        )
        this.setData({ tasks })
      })
      .catch(() => {})
  },

  onText(e) {
    const text = e.detail.value
    const lines = text.split('\n').filter((l) => l.trim())
    this.setData({ text, lineCount: lines.length })
  },

  onVoice(e) {
    this.setData({ voiceIndex: Number(e.detail.value) })
  },

  submit() {
    const { voices, voiceIndex, text, submitting } = this.data
    if (submitting) return
    const voice = voices[voiceIndex]
    if (!voice) return wx.showToast({ title: '请先创建音色', icon: 'none' })
    const lines = text.split('\n').filter((l) => l.trim())
    if (!lines.length) return wx.showToast({ title: '请输入要合成的文本（每行一条）', icon: 'none' })
    if (lines.length > 100) return wx.showToast({ title: '最多支持 100 行', icon: 'none' })

    this.setData({ submitting: true, result: null })
    api
      .request('/api/batch', {
        method: 'POST',
        data: {
          voice_id: voice.id,
          lines,
          language: voice.lang || 'zh'
        }
      })
      .then(({ task_id }) => this.poll(task_id, 0))
      .catch((err) => {
        this.setData({ submitting: false })
        wx.showToast({ title: err.message || '提交失败', icon: 'none' })
      })
  },

  poll(taskId, tries) {
    if (tries > 120) {
      this.setData({ submitting: false })
      return wx.showToast({ title: '合成超时，请重试', icon: 'none' })
    }
    setTimeout(() => {
      api
        .request('/api/batch/tasks/' + taskId)
        .then((task) => {
          this.setData({ result: task, submitting: false })
          const pending = task.items.filter((it) => it.status === 'pending' || it.status === 'failed')
          if (pending.length && task.status !== 'done') {
            this.poll(taskId, tries + 1)
            return
          }
          if (task.status === 'done') {
            wx.showToast({ title: '批量合成完成', icon: 'success' })
            this.loadTasks()
          }
        })
        .catch(() => this.poll(taskId, tries + 1))
    }, 1500)
  },

  onPlay(e) {
    const { index, url } = e.currentTarget.dataset
    if (this.data.playingIndex === index) {
      if (this.audio) this.audio.stop()
      this.setData({ playingIndex: -1 })
      return
    }
    if (this.audio) this.audio.destroy()
    this.audio = wx.createInnerAudioContext()
    this.audio.src = api.authUrl(url)
    this.audio.onEnded(() => this.setData({ playingIndex: -1 }))
    this.audio.onError(() => {
      this.setData({ playingIndex: -1 })
      wx.showToast({ title: '播放失败', icon: 'none' })
    })
    this.audio.play()
    this.setData({ playingIndex: index })
  },

  goCreateVoice() {
    wx.navigateTo({ url: '/pages/record/record' })
  }
})
