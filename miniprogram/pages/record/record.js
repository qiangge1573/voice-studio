const api = require('../../utils/api')

const LANGUAGES = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'fr', label: 'Français' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' }
]

const recorder = wx.getRecorderManager()

Page({
  data: {
    recording: false,
    seconds: 0,
    tempPath: '',
    previewing: false,
    name: '',
    langIndex: 0,
    lang: 'zh',
    consent: false,
    submitting: false,
    tip: ''
  },

  onLoad() {
    this._timer = null
    this.audio = wx.createInnerAudioContext()

    recorder.onStart(() => {
      this.setData({ recording: true, seconds: 0, tip: '' })
      this._startTimer()
    })

    recorder.onStop((res) => {
      this._stopTimer()
      this.setData({
        recording: false,
        seconds: 0,
        tempPath: res.tempFilePath,
        tip: '录音完成，可试听后重新录制'
      })
    })

    recorder.onError(() => {
      this._stopTimer()
      this.setData({ recording: false, tip: '录音失败，请检查麦克风权限' })
    })
  },

  onUnload() {
    this._stopTimer()
    if (this.audio) this.audio.destroy()
  },

  _startTimer() {
    this._timer = setInterval(() => {
      this.setData({ seconds: this.data.seconds + 1 })
    }, 1000)
  },

  _stopTimer() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  fmtSeconds(sec) {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return (m < 10 ? '0' + m : '' + m) + ':' + (s < 10 ? '0' + s : '' + s)
  },

  start() {
    if (this.data.recording) return
    this.setData({ tempPath: '', tip: '' })
    recorder.start({
      duration: 20000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 32000,
      format: 'mp3'
    })
  },

  onRecordTap() {
    if (this.data.recording) this.stop()
    else this.start()
  },

  stop() {
    if (this.data.recording) recorder.stop()
  },

  togglePreview() {
    if (!this.data.tempPath) return
    if (this.data.previewing) {
      this.audio.stop()
      this.setData({ previewing: false })
      return
    }
    this.audio.stop()
    this.audio.src = this.data.tempPath
    this.audio.onEnded(() => this.setData({ previewing: false }))
    this.audio.play()
    this.setData({ previewing: true })
  },

  onName(e) {
    this.setData({ name: e.detail.value })
  },

  onLang(e) {
    const index = Number(e.detail.value)
    this.setData({ langIndex: index, lang: LANGUAGES[index].value })
  },

  onConsent(e) {
    this.setData({ consent: e.detail.value.length > 0 })
  },

  submit() {
    const { name, tempPath, consent, lang, submitting } = this.data
    if (submitting) return
    if (!name.trim()) return wx.showToast({ title: '请填写音色名称', icon: 'none' })
    if (!tempPath) return wx.showToast({ title: '请先录制一段声音', icon: 'none' })
    if (!consent) return wx.showToast({ title: '请确认声音授权', icon: 'none' })

    this.setData({ submitting: true })
    api
      .upload('/api/voices', tempPath, {
        name: name.trim(),
        lang,
        consent: '1'
      })
      .then(() => {
        wx.showToast({ title: '音色创建成功', icon: 'success' })
        setTimeout(() => {
          wx.switchTab({ url: '/pages/voices/voices' })
        }, 800)
      })
      .catch((err) => {
        wx.showToast({ title: err.message || '创建失败', icon: 'none' })
        this.setData({ submitting: false })
      })
  }
})
