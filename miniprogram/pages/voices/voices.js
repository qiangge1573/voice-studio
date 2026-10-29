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
    loading: true,
    playingId: -1
  },

  onShow() {
    this.load()
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh())
  },

  load() {
    this.setData({ loading: true })
    return api
      .request('/api/voices')
      .then((list) => {
        const voices = (list || []).map((v) =>
          Object.assign({}, v, { created_at_text: formatDate(v.created_at) })
        )
        this.setData({ voices, loading: false })
      })
      .catch((err) => {
        this.setData({ loading: false })
        wx.showToast({ title: err.message || '加载失败', icon: 'none' })
      })
  },

  _audio: null,

  onPlay(e) {
    const id = e.detail.id
    if (this.data.playingId === id) {
      if (this._audio) this._audio.stop()
      this.setData({ playingId: -1 })
      return
    }
    if (this._audio) this._audio.destroy()
    const voice = this.data.voices.find((v) => v.id === id)
    if (!voice) return
    this._audio = wx.createInnerAudioContext()
    this._audio.src = api.authUrl(voice.sample_url)
    this._audio.onEnded(() => this.setData({ playingId: -1 }))
    this._audio.onError(() => {
      this.setData({ playingId: -1 })
      wx.showToast({ title: '音频播放失败', icon: 'none' })
    })
    this._audio.play()
    this.setData({ playingId: id })
  },

  onDelete(e) {
    const id = e.detail.id
    wx.showModal({
      title: '删除音色',
      content: '删除后该音色不可恢复，确定删除吗？',
      confirmColor: '#ef4444',
      success: (res) => {
        if (!res.confirm) return
        api
          .request('/api/voices/' + id, { method: 'DELETE' })
          .then(() => {
            if (this._audio) this._audio.destroy()
            wx.showToast({ title: '已删除', icon: 'success' })
            this.load()
          })
          .catch((err) => wx.showToast({ title: err.message, icon: 'none' }))
      }
    })
  },

  onUse(e) {
    const id = e.detail.id
    getApp().globalData.presetVoiceId = id
    wx.switchTab({ url: '/pages/synthesize/synthesize' })
  },

  goRecord() {
    wx.navigateTo({ url: '/pages/record/record' })
  }
})
