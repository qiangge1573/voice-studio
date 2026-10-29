const { BASE_URL, USE_DEV_LOGIN } = require('./config')

function getToken() {
  const app = getApp()
  return (app && app.globalData && app.globalData.token) || ''
}

// 通用请求（自动携带登录令牌）
function request(path, { method = 'GET', data, header = {} } = {}) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    wx.request({
      url: BASE_URL + path,
      method,
      data,
      header: Object.assign(
        { 'Content-Type': 'application/json' },
        token ? { Authorization: 'Bearer ' + token } : {},
        header
      ),
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const msg =
            (res.data && (res.data.detail || res.data.message)) ||
            '请求失败(' + res.statusCode + ')'
          reject(new Error(msg))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      }
    })
  })
}

// 上传文件（语音样本）
function upload(path, filePath, formData = {}) {
  return new Promise((resolve, reject) => {
    const token = getToken()
    wx.uploadFile({
      url: BASE_URL + path,
      filePath,
      name: 'file',
      formData,
      header: token ? { Authorization: 'Bearer ' + token } : {},
      success(res) {
        let data = {}
        try {
          data = JSON.parse(res.data)
        } catch (e) {
          /* 忽略解析失败 */
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(data)
        } else {
          reject(new Error((data && data.detail) || '上传失败(' + res.statusCode + ')'))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      }
    })
  })
}

// 登录：开发模式直接 code=dev，正式模式走 wx.login
function login() {
  const getCode = USE_DEV_LOGIN
    ? Promise.resolve({ code: 'dev' })
    : new Promise((resolve, reject) => {
        wx.login({ success: resolve, fail: reject })
      })
  return getCode
    .then(({ code }) =>
      request('/api/auth/login', { method: 'POST', data: { code } })
    )
    .then((res) => ({ token: res.token, user: res.user }))
}

// 音频播放 URL：InnerAudioContext 不支持自定义 Header，令牌以查询参数传递
function authUrl(path) {
  const token = getToken()
  return BASE_URL + path + (token ? '?token=' + encodeURIComponent(token) : '')
}

module.exports = { request, upload, login, authUrl, BASE_URL, USE_DEV_LOGIN }
