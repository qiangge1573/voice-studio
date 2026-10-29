const app = getApp()

Page({
  data: {
    showPrivacy: false,
    user: null
  },

  onLoad() {
    this.initPrivacy()
  },

  onShow() {
    this.setData({ user: app.globalData.user })
  },

  // 首次进入展示《使用须知与隐私》弹窗
  initPrivacy() {
    if (wx.getStorageSync('privacy_agreed')) return
    this.setData({ showPrivacy: true })
  },

  agreePrivacy() {
    wx.setStorageSync('privacy_agreed', true)
    this.setData({ showPrivacy: false })
  },

  goRecord() {
    wx.navigateTo({ url: '/pages/record/record' })
  },

  goVoices() {
    wx.switchTab({ url: '/pages/voices/voices' })
  },

  goSynthesize() {
    wx.switchTab({ url: '/pages/synthesize/synthesize' })
  },

  goHistory() {
    wx.switchTab({ url: '/pages/history/history' })
  },

  goDubbing() {
    wx.navigateTo({ url: '/pages/dubbing/dubbing' })
  },

  goBatch() {
    wx.navigateTo({ url: '/pages/batch/batch' })
  }
})
