const api = require('./utils/api')

App({
  globalData: {
    token: '',
    user: null,
    presetVoiceId: null
  },

  onLaunch() {
    this.login()
  },

  // 微信隐私保护指引授权（基础库 2.32.3+；需在公众平台配置《用户隐私保护指引》）
  login() {
    return api
      .login()
      .then(({ token, user }) => {
        this.globalData.token = token
        this.globalData.user = user
      })
      .catch((err) => {
        console.error('登录失败：', err)
      })
  },

  ensureLogin() {
    if (this.globalData.token) return Promise.resolve()
    return this.login()
  }
})
