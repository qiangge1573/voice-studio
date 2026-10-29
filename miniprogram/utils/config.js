// 全局配置：后端地址与登录模式
//  - 微信开发者工具（未勾选"校验合法域名"）可用 http://127.0.0.1:8000
//  - 真机预览 / 发布必须换成已在小程序后台配置的 https 合法域名
const BASE_URL = 'http://127.0.0.1:8000'

// 开发模式：true 时跳过 wx.login，直接以 code=dev 登录（对应服务端 dev_mode）。
// 接入真实微信登录后改为 false
const USE_DEV_LOGIN = true

module.exports = { BASE_URL, USE_DEV_LOGIN }
