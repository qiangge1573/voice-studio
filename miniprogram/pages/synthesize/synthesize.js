const api = require('../../utils/api')

Page({
  data: {
    voices: [],
    voiceIndex: -1,
    voiceNames: [],
    text: '',
    left: 1000,
    loading: true,
    generating: false,
    audioUrl: '',
    playing: false
  },

  onLoad() {
    this.audio = wx.createInnerAudioContext()
  },

  onShow() {
    this.loadVoices()
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
        const preset = getApp().globalData.presetVoiceId
        getApp().globalData.presetVoiceId = null
        if (preset) {
          const hit = voices.findIndex((v) => v.id === preset)
          if (hit >= 0) index = hit
        }
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

  onText(e) {
    const text = e.detail.value
    this.setData({ text, left: 1000 - text.length })
  },

  onVoice(e) {
    this.setData({ voiceIndex: Number(e.detail.value) })
  },

  synthesize() {
    const { voices, voiceIndex, text, generating } = this.data
    if (generating) return
    const voice = voices[voiceIndex]
    if (!voice) return wx.showToast({ title: '请先创建音色', icon: 'none' })
    if (!text.trim()) return wx.showToast({ title: '请输入要合成的文本', icon: 'none' })

    this.setData({ generating: true, audioUrl: '', playing: false })
    api
      .request('/api/tts/synthesize', {
        method: 'POST',
        data: {
          voice_id: voice.id,
          text: text.trim(),
          language: voice.lang || 'zh'
        }
      })
      .then(({ task_id }) => this.poll(task_id, 0))
      .catch((err) => {
        this.setData({ generating: false })
        wx.showToast({ title: err.message || '合成失败', icon: 'none' })
      })
  },

  poll(taskId, tries) {
    if (tries > 80) {
      this.setData({ generating: false })
      return wx.showToast({ title: '合成超时，请重试', icon: 'none' })
    }
    setTimeout(() => {
      api
        .request('/api/tts/tasks/' + taskId)
        .then((task) => {
          if (task.status === 'done') {
            this.setData({ generating: false, audioUrl: task.audio_url })
            wx.showToast({ title: '合成完成', icon: 'success' })
          } else if (task.status === 'failed') {
            this.setData({ generating: false })
            wx.showToast({ title: task.error || '合成失败', icon: 'none' })
          } else {
            this.poll(taskId, tries + 1)
          }
        })
        .catch(() => this.poll(taskId, tries + 1))
    }, 1500)
  },

  togglePlay() {
    const { audioUrl, playing } = this.data
    if (!audioUrl) return
    if (playing) {
      this.audio.stop()
      this.setData({ playing: false })
      return
    }
    this.audio.stop()
    this.audio.src = api.authUrl(audioUrl)
    this.audio.onEnded(() => this.setData({ playing: false }))
    this.audio.onError(() => {
      this.setData({ playing: false })
      wx.showToast({ title: '播放失败', icon: 'none' })
    })
    this.audio.play()
    this.setData({ playing: true })
  },

  goCreateVoice() {
    wx.navigateTo({ url: '/pages/record/record' })
  }
})
