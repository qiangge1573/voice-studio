Component({
  properties: {
    voice: {
      type: Object,
      value: {}
    },
    playing: {
      type: Boolean,
      value: false
    }
  },

  methods: {
    onPlay() {
      this.triggerEvent('play', { id: this.data.voice.id })
    },
    onDelete() {
      this.triggerEvent('delete', { id: this.data.voice.id })
    },
    onUse() {
      this.triggerEvent('use', { id: this.data.voice.id })
    }
  }
})
