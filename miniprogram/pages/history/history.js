const api = require('../../utils/api')

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const p = (n) => (n < 10 ? '0' + n : '' + n)
  return (
    d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
    ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
  )
}

Page({
  data: {
    items: [],
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
      .request('/api/history')
      .then((list) => {
        const items = (list || []).map((t) =>
          Object.assign({}, t, { created_at_text: formatDate(t.created_at) })
        )
        this.setData({ items, loading: false })
      })
      .catch((err) => {
        this.setData({ loading: false })
        wx.showToast({ title: err.message || '加载失败', icon: 'none' })
      })
  },

  onPlay(e) {
    const id = e.currentTarget.dataset.id
    if (this.data.playingId === id) {
      if (this._audio) this._audio.stop()
      this.setData({ playingId: -1 })
      return
    }
    if (this._audio) this._audio.destroy()
    const item = this.data.items.find((t) => t.task_id === id)
    if (!item || !item.audio_url) return
    this._audio = wx.createInnerAudioContext()
    this._audio.src = api.authUrl(item.audio_url)
    this._audio.onEnded(() => this.setData({ playingId: -1 }))
    this._audio.onError(() => {
      this.setData({ playingId: -1 })
      wx.showToast({ title: '播放失败', icon: 'none' })
    })
    this._audio.play()
    this.setData({ playingId: id })
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '删除记录',
      content: '确定删除这条合成记录吗？',
      confirmColor: '#ef4444',
      success: (res) => {
        if (!res.confirm) return
        api
          .request('/api/history/' + id, { method: 'DELETE' })
          .then(() => {
            wx.showToast({ title: '已删除', icon: 'success' })
            this.load()
          })
          .catch((err) => wx.showToast({ title: err.message, icon: 'none' }))
      }
    })
  },

  goSynthesize() {
    wx.switchTab({ url: '/pages/synthesize/synthesize' })
  }
})
