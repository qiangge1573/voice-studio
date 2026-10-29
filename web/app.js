/* Voice Studio 网页版 · 前端逻辑
 * 复用 Voice Studio 后端 API（FastAPI）：登录 / 音色 / 合成 / 配音 / 批量 / 历史
 * 音频与视频下载 URL 兼容 ?token= 查询参数
 */
(function () {
  'use strict';

  /* ================= 基础状态 ================= */
  var BASE_URL = localStorage.getItem('vs_base_url') || 'http://127.0.0.1:8000';
  var TOKEN = null;
  var POLL_INTERVAL = 1200;
  var MAX_SAMPLE_SEC = 20;

  var $ = function (sel) { return document.querySelector(sel); };

  /* ================= 工具函数 ================= */
  function authUrl(path) {
    var sep = path.indexOf('?') >= 0 ? '&' : '?';
    return BASE_URL + path + sep + 'token=' + encodeURIComponent(TOKEN || '');
  }

  function fmtTime(sec) {
    var m = Math.floor(sec / 60);
    var s = Math.floor(sec % 60);
    return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
  }

  function fmtClock(ts) {
    if (!ts) return '';
    var d = new Date(ts);
    if (isNaN(d.getTime())) return '';
    function p(n) { return (n < 10 ? '0' : '') + n; }
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  /* 确定性波形（按字符串哈希生成 SVG polyline），作为声音签名元素 */
  function hashStr(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) {
      h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    }
    return Math.abs(h);
  }

  function waveSvg(seed, w, h, amp) {
    var width = w || 96, height = h || 34, maxAmp = amp || 10;
    var n = 24, rnd = hashStr(seed), pts = [];
    for (var i = 0; i <= n; i++) {
      var x = (i / n) * width;
      var a = (Math.sin(rnd + i * 1.7) * 0.5 + 0.5) * maxAmp + 2;
      var y = height / 2;
      pts.push(x.toFixed(1) + ',' + (y - a).toFixed(1));
      pts.push(x.toFixed(1) + ',' + (y + a).toFixed(1));
    }
    return '<svg class="card-wave" viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none" aria-hidden="true">' +
      '<polyline points="' + pts.join(' ') + '" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  }

  function heroWave(el) {
    var html = [];
    for (var i = 0; i < 5; i++) {
      var r = 60 + i * 5;
      html.push('<svg viewBox="0 0 900 120" preserveAspectRatio="none" aria-hidden="true"><polyline points="' +
        wavePath(28 + i * 9, 90 - i * 8) + '" fill="none" stroke="' + (i % 2 ? '#f2a33c' : '#e9edf2') +
        '" stroke-width="1.4" opacity="' + (0.4 - i * 0.06) + '"/></svg>');
    }
    el.innerHTML = html.join('');
  }

  function wavePath(amp, freq) {
    var pts = [];
    for (var i = 0; i <= 60; i++) {
      var x = (i / 60) * 900;
      var y = 60 + Math.sin(i * freq / 10) * amp;
      pts.push(x.toFixed(1) + ',' + y.toFixed(1));
    }
    return pts.join(' ');
  }

  /* ================= API ================= */
  function request(path, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    headers['Content-Type'] = 'application/json';
    if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
    return fetch(BASE_URL + path, {
      method: opts.method || 'GET',
      headers: headers,
      body: opts.body
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var err = new Error((data && data.detail) || ('HTTP ' + res.status));
          err.status = res.status;
          throw err;
        }
        return data;
      });
    });
  }

  function upload(path, file, form) {
    var fd = new FormData();
    fd.append('file', file, file.name);
    Object.keys(form || {}).forEach(function (k) { fd.append(k, form[k]); });
    var headers = {};
    if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
    return fetch(BASE_URL + path, { method: 'POST', headers: headers, body: fd }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var err = new Error((data && data.detail) || ('HTTP ' + res.status));
          err.status = res.status;
          throw err;
        }
        return data;
      });
    });
  }

  function pollTask(url, timeoutMs) {
    var deadline = Date.now() + (timeoutMs || 180000);
    return new Promise(function (resolve, reject) {
      (function tick() {
        request(url).then(function (data) {
          if (data.status === 'done' || data.status === 'failed') return resolve(data);
          if (Date.now() > deadline) return reject(new Error('任务超时，请稍后查看任务列表'));
          setTimeout(tick, POLL_INTERVAL);
        }).catch(function (e) {
          if (Date.now() > deadline) return reject(e);
          setTimeout(tick, POLL_INTERVAL + 800);
        });
      })();
    });
  }

  /* ================= 播放器（全局单例） ================= */
  var player = null;
  var playingBtn = null;

  function stopPlay() {
    if (player) { player.pause(); player.src = ''; }
    if (playingBtn) {
      playingBtn.classList.remove('playing');
      playingBtn.textContent = playingBtn.getAttribute('data-label') || '播放';
      playingBtn = null;
    }
  }

  function playUrl(url, btn, label) {
    stopPlay();
    var audio = player || (player = new Audio());
    audio.src = url;
    audio.setAttribute('controls', '');
    audio.onended = function () {
      if (playingBtn) { playingBtn.classList.remove('playing'); playingBtn.textContent = playingBtn.getAttribute('data-label') || '播放'; playingBtn = null; }
    };
    audio.play().catch(function () { /* 用户交互后一般可播放 */ });
    if (btn) {
      btn.classList.add('playing');
      btn.textContent = '停止';
      btn.setAttribute('data-label', label || '播放');
      playingBtn = btn;
    }
  }

  function wirePlay(btn, url, label) {
    btn.addEventListener('click', function () {
      if (btn.classList.contains('playing')) { stopPlay(); return; }
      playUrl(url, btn, label);
    });
  }

  /* ================= 哈希路由 ================= */
  var NAV = [
    { id: 'home', label: '首页' },
    { id: 'record', label: '克隆音色' },
    { id: 'voices', label: '音色库' },
    { id: 'synth', label: '文本合成' },
    { id: 'dub', label: '视频配音' },
    { id: 'batch', label: '批量合成' },
    { id: 'history', label: '历史' }
  ];

  function renderTabs() {
    var wrap = $('#tabs');
    wrap.innerHTML = '';
    NAV.forEach(function (item) {
      var b = document.createElement('button');
      b.className = 'tab';
      b.textContent = item.label;
      b.dataset.nav = item.id;
      wrap.appendChild(b);
    });
  }

  function showView(id) {
    NAV.forEach(function (item) {
      var v = $('#view-' + item.id);
      if (v) v.hidden = item.id !== id;
    });
    document.querySelectorAll('.tab').forEach(function (t) {
      t.classList.toggle('active', t.dataset.nav === id);
    });
    if (id === 'voices') loadVoices();
    if (id === 'synth') fillVoiceSelect('synth-voice');
    if (id === 'dub') { fillVoiceSelect('dub-voice'); loadDubTasks(); }
    if (id === 'batch') fillVoiceSelect('batch-voice');
    if (id === 'history') loadHistory();
    window.scrollTo(0, 0);
  }

  function initNav() {
    renderTabs();
    $('#tabs').addEventListener('click', function (e) {
      var t = e.target.closest('.tab');
      if (t) location.hash = t.dataset.nav;
    });
    document.querySelectorAll('[data-nav]').forEach(function (el) {
      el.addEventListener('click', function () { location.hash = el.dataset.nav; });
    });
    window.addEventListener('hashchange', route);
  }

  function route() {
    var id = (location.hash || '#home').replace('#', '');
    if (!NAV.some(function (n) { return n.id === id; })) id = 'home';
    showView(id);
  }

  /* ================= 连接与登录 ================= */
  function setConn(state, text) {
    var chip = $('#conn-chip');
    chip.className = 'chip ' + state;
    chip.textContent = text;
  }

  function connect(silent) {
    return request('/api/health').then(function (h) {
      setConn(h.engine === 'mock' ? 'warn' : 'ok', '已连接 · 引擎 ' + h.engine);
      $('#hero-engine').textContent = '引擎：' + h.engine + (h.dev_mode ? ' · 开发模式' : '') + ' · 后端 ' + BASE_URL;
      if (h.engine === 'mock') {
        $('#hero-engine').textContent += ' · 未配置 VOLC_API_KEY，合成输出为演示音';
      }
      return h;
    }).then(function () {
      return request('/api/auth/login', { method: 'POST', body: JSON.stringify({ code: 'dev' }) });
    }).then(function (data) {
      TOKEN = data.token;
      setConn(data.engine === 'mock' ? 'warn' : 'ok', '已登录 · 引擎 ' + (data.engine || ''));
      return data;
    }).catch(function (e) {
      setConn('off', '后端不可达');
      $('#hero-engine').textContent = '无法连接后端 ' + BASE_URL + '：' + e.message + '。请点击右上角按钮设置后端地址。';
      if (!silent) {
        $('#modal-err').textContent = '连接失败：' + e.message;
        openModal();
      }
      throw e;
    });
  }

  function openModal() { $('#modal-mask').hidden = false; $('#base-url-input').value = BASE_URL; $('#modal-err').textContent = ''; }
  function closeModal() { $('#modal-mask').hidden = true; }

  /* ================= 录音 ================= */
  var recorder = null;
  var stream = null;
  var recChunks = [];
  var recTimer = null;
  var recStart = 0;
  var recAudio = null;
  var recWavBlob = null;

  function setErr(sel, msg) { $(sel).textContent = msg || ''; }

  function startRecord() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErr('#record-err', '当前浏览器不支持录音（需 HTTPS 或 localhost，且使用较新版本 Chrome / Edge / Firefox）。');
      return;
    }
    setErr('#record-err', '');
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s;
      var mime = (function () {
        var cands = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
        for (var i = 0; i < cands.length; i++) {
          if (MediaRecorder.isTypeSupported(cands[i])) return cands[i];
        }
        return '';
      })();
      recorder = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      recChunks = [];
      recorder.ondataavailable = function (e) { if (e.data && e.data.size > 0) recChunks.push(e.data); };
      recorder.onstop = function () {
        var blob = new Blob(recChunks, { type: recorder.mimeType || 'audio/webm' });
        stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
        stopMeter();
        convertToWav(blob).then(function (wav) {
          recWavBlob = wav;
          var sec = wav.size / 32000; /* 16k 16bit mono ≈ 32KB/s */
          $('#record-time').textContent = '已录制 ' + fmtTime(sec);
          $('#record-preview').hidden = false;
          $('#record-preview-audio').src = URL.createObjectURL(wav);
          $('#record-btn').classList.remove('recording');
          $('#record-btn-label').textContent = '重新录制';
        }).catch(function () {
          $('#record-btn').classList.remove('recording');
          $('#record-btn-label').textContent = '重新录制';
          setErr('#record-err', '录音转码失败，请重试。');
        });
      };
      recorder.start();
      recStart = Date.now();
      $('#record-btn').classList.add('recording');
      $('#record-btn-label').textContent = '停止录音';
      setErr('#record-err', '');
      startMeter();
      recTimer = setTimeout(function () {
        if (recorder && recorder.state === 'recording') stopRecord();
      }, MAX_SAMPLE_SEC * 1000);
    }).catch(function (e) {
      setErr('#record-err', '无法访问麦克风：' + (e.name || e.message) + '。请检查系统授权。');
    });
  }

  function stopRecord() {
    clearTimeout(recTimer);
    if (recorder && recorder.state === 'recording') recorder.stop();
  }

  /* 录音转 16kHz 单声道 16bit WAV（兼容后端与云引擎参考音频要求） */
  function convertToWav(blob) {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    return blob.arrayBuffer().then(function (ab) {
      return ctx.decodeAudioData(ab);
    }).then(function (buf) {
      var src = buf.getChannelData(0);
      var targetRate = 16000;
      var outLen = Math.round(src.length * targetRate / buf.sampleRate);
      var out = new Float32Array(outLen);
      var step = buf.sampleRate / targetRate;
      for (var i = 0; i < outLen; i++) out[i] = src[Math.min(src.length - 1, Math.floor(i * step))];
      var wav = new ArrayBuffer(44 + outLen * 2);
      var view = new DataView(wav);
      function writeStr(off, s) { for (var j = 0; j < s.length; j++) view.setUint8(off + j, s.charCodeAt(j)); }
      writeStr(0, 'RIFF');
      view.setUint32(4, 36 + outLen * 2, true);
      writeStr(8, 'WAVE');
      writeStr(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, targetRate, true);
      view.setUint32(28, targetRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeStr(36, 'data');
      view.setUint32(40, outLen * 2, true);
      for (var k = 0; k < outLen; k++) {
        var v = Math.max(-1, Math.min(1, out[k]));
        view.setInt16(44 + k * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
      }
      return new Blob([wav], { type: 'audio/wav' });
    }).finally(function () { ctx.close(); });
  }

  /* 电平表（假电平，录音时跳动） */
  var meterTimer = null;
  function startMeter() {
    var box = $('#record-meter');
    box.innerHTML = '';
    for (var i = 0; i < 24; i++) {
      var b = document.createElement('div');
      b.className = 'bar';
      box.appendChild(b);
    }
    var bars = box.querySelectorAll('.bar');
    meterTimer = setInterval(function () {
      bars.forEach(function (b, idx) {
        var h = 6 + Math.round((Math.sin(Date.now() / 120 + idx * 1.3) * 0.5 + 0.5) * 26);
        b.style.height = h + 'px';
      });
    }, 90);
  }
  function stopMeter() {
    if (meterTimer) clearInterval(meterTimer);
    meterTimer = null;
    $('#record-meter').innerHTML = '';
  }

  /* ================= 音色库 ================= */
  var voiceCache = [];

  function loadVoices() {
    if (!TOKEN) return;
    request('/api/voices').then(function (list) {
      voiceCache = list;
      renderVoices(list);
      ['synth-voice', 'dub-voice', 'batch-voice'].forEach(function (sel) { fillVoiceSelect(sel); });
    }).catch(function (e) {
      $('#voice-empty').hidden = false;
      $('#voice-empty').querySelector('p').textContent = '音色加载失败：' + e.message;
    });
  }

  function fillVoiceSelect(id) {
    var sel = $('#' + id);
    var prev = sel.value;
    sel.innerHTML = '';
    if (!voiceCache.length) {
      sel.innerHTML = '<option value="">（请先创建音色）</option>';
      return;
    }
    voiceCache.forEach(function (v) {
      var o = document.createElement('option');
      o.value = v.id;
      o.textContent = v.name + ' · ' + v.lang + ' · ' + fmtTime(v.sample_duration || 0);
      sel.appendChild(o);
    });
    if (prev && voiceCache.some(function (v) { return String(v.id) === prev; })) sel.value = prev;
  }

  function renderVoices(list) {
    var box = $('#voice-list');
    box.innerHTML = '';
    $('#voice-empty').hidden = list.length > 0;
    list.forEach(function (v) {
      var card = document.createElement('div');
      card.className = 'voice-card';
      card.innerHTML = waveSvg('voice-' + v.id + '-' + v.name, 96, 34, 10) +
        '<div class="card-main">' +
        '<div class="card-name">' + escapeHtml(v.name) + '</div>' +
        '<div class="card-meta">' + v.lang + ' · ' + fmtTime(v.sample_duration || 0) + ' · 样本创建于 ' + fmtClock(v.created_at * 1000) + '</div>' +
        '</div>' +
        '<div class="card-actions">' +
        '<button class="mini-btn" data-play="' + v.id + '" type="button">试听</button>' +
        '<button class="mini-btn primary" data-synth="' + v.id + '" type="button">去合成</button>' +
        '<button class="mini-btn danger" data-del="' + v.id + '" type="button">删除</button>' +
        '</div>';
      box.appendChild(card);
    });
  }

  function createVoice() {
    var name = $('#voice-name').value.trim();
    var lang = $('#voice-lang').value;
    var consent = $('#voice-consent').checked;
    if (!recWavBlob) { setErr('#create-voice-err', '请先录制一段声音样本。'); return; }
    if (!name) { setErr('#create-voice-err', '请填写音色名称（1–20 字）。'); return; }
    if (!consent) { setErr('#create-voice-err', '请勾选声音授权确认。'); return; }
    setErr('#create-voice-err', '');
    var btn = $('#create-voice-btn');
    btn.disabled = true;
    btn.textContent = '创建中…';
    upload('/api/voices', recWavBlob, { name: name, lang: lang, consent: '1' })
      .then(function (v) {
        btn.disabled = false;
        btn.textContent = '创建音色';
        $('#voice-consent').checked = false;
        $('#voice-name').value = '';
        $('#record-preview').hidden = true;
        recWavBlob = null;
        loadVoices();
        location.hash = 'voices';
      })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = '创建音色';
        setErr('#create-voice-err', '创建失败：' + e.message);
      });
  }

  function deleteVoice(id) {
    request('/api/voices/' + id, { method: 'DELETE' }).then(function () {
      loadVoices();
    }).catch(function (e) { alert('删除失败：' + e.message); });
  }

  /* ================= 文本合成 ================= */
  function createSynth() {
    var voiceId = $('#synth-voice').value;
    var text = $('#synth-text').value.trim();
    var voice = voiceCache.find(function (v) { return String(v.id) === String(voiceId); });
    if (!voiceId) { setErr('#synth-err', '请先选择音色。'); return; }
    if (!text) { setErr('#synth-err', '请输入要合成的文本。'); return; }
    setErr('#synth-err', '');
    var btn = $('#synth-btn');
    btn.disabled = true;
    btn.textContent = '合成中…';
    request('/api/tts/synthesize', {
      method: 'POST',
      body: JSON.stringify({ voice_id: voiceId, text: text, language: (voice && voice.lang) || 'zh' })
    }).then(function (data) {
      return pollTask('/api/tts/tasks/' + data.task_id);
    }).then(function (task) {
      btn.disabled = false;
      btn.textContent = '开始合成';
      if (task.status === 'failed') { setErr('#synth-err', '合成失败：' + (task.error || '未知错误')); return; }
      setErr('#synth-err', '');
      $('#synth-result').hidden = false;
      var audio = $('#synth-audio');
      audio.src = authUrl(task.audio_url);
      audio.load();
    }).catch(function (e) {
      btn.disabled = false;
      btn.textContent = '开始合成';
      setErr('#synth-err', '合成失败：' + e.message);
    });
  }

  /* ================= 视频配音 ================= */
  function loadDubTasks() {
    if (!TOKEN) return;
    request('/api/dubbing/tasks').then(function (list) {
      var box = $('#dub-tasks');
      box.innerHTML = '';
      if (!list || !list.length) { box.innerHTML = '<p class="hint">暂无配音任务</p>'; return; }
      list.slice(0, 5).forEach(function (t) {
        var row = document.createElement('div');
        row.className = 'task-card';
        var statusCls = t.status === 'done' ? 'done' : (t.status === 'failed' ? 'failed' : 'pending');
        var statusText = t.status === 'done' ? '完成' : (t.status === 'failed' ? '失败' : t.status);
        row.innerHTML = '<div class="card-main"><div class="card-name">配音任务 · ' + fmtClock(t.created_at * 1000) + '</div>' +
          '<div class="card-meta">' + t.mode + ' · 音色 ' + escapeHtml(t.voice_name || '') + '</div></div>' +
          '<span class="task-status ' + statusCls + '">' + statusText + '</span>';
        if (t.status === 'done') {
          var pbtn = document.createElement('button');
          pbtn.className = 'mini-btn primary';
          pbtn.textContent = '播放';
          row.querySelector('.card-main').appendChild(pbtn);
          wirePlay(pbtn, authUrl(t.video_url), '播放');
        }
        box.appendChild(row);
      });
    }).catch(function () { /* 静默 */ });
  }

  function createDub() {
    var file = $('#dub-video').files[0];
    var voiceId = $('#dub-voice').value;
    var script = $('#dub-script').value.trim();
    var mode = document.querySelector('input[name="dub-mode"]:checked').value;
    if (!file) { setErr('#dub-err', '请选择视频文件。'); return; }
    if (!voiceId) { setErr('#dub-err', '请选择音色。'); return; }
    if (!script) { setErr('#dub-err', '请填写配音台本。'); return; }
    setErr('#dub-err', '');
    var btn = $('#dub-btn');
    btn.disabled = true;
    btn.textContent = '配音处理中…';
    upload('/api/dubbing', file, { voice_id: voiceId, script: script, mode: mode })
      .then(function (data) {
        return pollTask('/api/dubbing/tasks/' + data.task_id);
      })
      .then(function (task) {
        btn.disabled = false;
        btn.textContent = '开始配音';
        if (task.status === 'failed') { setErr('#dub-err', '配音失败：' + (task.error || '未知错误')); return; }
        setErr('#dub-err', '');
        $('#dub-result').hidden = false;
        var v = $('#dub-output');
        v.src = authUrl(task.video_url);
        v.load();
        loadDubTasks();
      })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = '开始配音';
        setErr('#dub-err', '配音失败：' + e.message);
      });
  }

  /* ================= 批量合成 ================= */
  var lastBatchTaskId = null;

  function createBatch() {
    var voiceId = $('#batch-voice').value;
    var raw = $('#batch-text').value;
    var lines = raw.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
    if (!voiceId) { setErr('#batch-err', '请先选择音色。'); return; }
    if (!lines.length) { setErr('#batch-err', '请输入至少一行文本。'); return; }
    setErr('#batch-err', '');
    var btn = $('#batch-btn');
    btn.disabled = true;
    btn.textContent = '批量合成中…';
    request('/api/batch', {
      method: 'POST',
      body: JSON.stringify({ voice_id: voiceId, lines: lines, language: 'zh' })
    }).then(function (data) {
      lastBatchTaskId = data.task_id;
      sessionStorage.setItem('vs_last_batch', data.task_id);
      return pollTask('/api/batch/tasks/' + data.task_id, 600000);
    }).then(function (task) {
      btn.disabled = false;
      btn.textContent = '批量合成';
      if (task.status === 'failed') { setErr('#batch-err', '批量任务失败：' + (task.error || '')); return; }
      setErr('#batch-err', '');
      renderBatchItems(task);
    }).catch(function (e) {
      btn.disabled = false;
      btn.textContent = '批量合成';
      setErr('#batch-err', '批量合成失败：' + e.message);
    });
  }

  function renderBatchItems(task) {
    $('#batch-result').hidden = false;
    var box = $('#batch-items');
    box.innerHTML = '';
    (task.items || []).forEach(function (item, i) {
      var row = document.createElement('div');
      row.className = 'item-line';
      var statusCls = item.status === 'done' ? 'done' : (item.status === 'failed' ? 'failed' : 'pending');
      var statusText = item.status === 'done' ? '完成' : (item.status === 'failed' ? '失败' : item.status);
      row.innerHTML = '<span class="item-status ' + statusCls + '">' + statusText + '</span>' +
        '<span class="item-text">' + (i + 1) + '. ' + escapeHtml(item.text) + '</span>';
      if (item.status === 'failed') {
        row.innerHTML += '<span class="item-err">' + escapeHtml(item.error || '') + '</span>';
      } else if (item.status === 'done') {
        var pbtn = document.createElement('button');
        pbtn.className = 'mini-btn primary';
        pbtn.textContent = '播放';
        row.appendChild(pbtn);
        wirePlay(pbtn, authUrl(item.audio_url), '播放');
      }
      box.appendChild(row);
    });
  }

  /* ================= 历史 ================= */
  function loadHistory() {
    if (!TOKEN) return;
    request('/api/history').then(function (list) {
      var box = $('#history-list');
      box.innerHTML = '';
      $('#history-empty').hidden = (list || []).length > 0;
      (list || []).forEach(function (h) {
        var row = document.createElement('div');
        row.className = 'his-card';
        row.innerHTML = '<div class="card-main"><div class="card-name">文本合成 · ' + escapeHtml(h.voice_name || '') + '</div>' +
          '<div class="card-meta">' + escapeHtml(h.text || '') + ' · ' + (h.status === 'done' ? '已完成' : h.status) + ' · ' + fmtClock(h.created_at * 1000) + '</div></div>' +
          '<div class="card-actions"></div>';
        var acts = row.querySelector('.card-actions');
        if (h.audio_url && h.status === 'done') {
          var pb = document.createElement('button');
          pb.className = 'mini-btn primary';
          pb.textContent = '播放';
          acts.appendChild(pb);
          wirePlay(pb, authUrl(h.audio_url), '播放');
          var dl = document.createElement('button');
          dl.className = 'mini-btn';
          dl.textContent = '下载';
          dl.addEventListener('click', function () {
            var a = document.createElement('a');
            a.href = authUrl(h.audio_url);
            a.download = '';
            document.body.appendChild(a);
            a.click();
            a.remove();
          });
          acts.appendChild(dl);
        }
        var del = document.createElement('button');
        del.className = 'mini-btn danger';
        del.textContent = '删除';
        del.addEventListener('click', function () {
          request('/api/history/' + h.task_id, { method: 'DELETE' }).then(loadHistory).catch(function (e) { alert('删除失败：' + e.message); });
        });
        acts.appendChild(del);
        box.appendChild(row);
      });
    }).catch(function () { /* 未登录或后端不可达时静默 */ });
  }

  /* ================= 事件绑定 ================= */
  function bindEvents() {
    $('#conn-chip').addEventListener('click', openModal);
    $('#settings-btn').addEventListener('click', openModal);
    $('#modal-close').addEventListener('click', closeModal);
    $('#modal-mask').addEventListener('click', function (e) { if (e.target === this) closeModal(); });
    $('#modal-save').addEventListener('click', function () {
      var v = $('#base-url-input').value.trim().replace(/\/+$/, '');
      if (!v) { $('#modal-err').textContent = '请输入后端地址。'; return; }
      BASE_URL = v;
      localStorage.setItem('vs_base_url', v);
      TOKEN = null;
      closeModal();
      setConn('off', '连接中…');
      connect();
    });

    $('#record-btn').addEventListener('click', function () {
      if (recorder && recorder.state === 'recording') { stopRecord(); return; }
      startRecord();
    });
    $('#re-record-btn').addEventListener('click', function () {
      $('#record-preview').hidden = true;
      recWavBlob = null;
      $('#record-time').textContent = '00:00';
      $('#record-btn-label').textContent = '开始录音';
    });
    $('#create-voice-btn').addEventListener('click', createVoice);

    $('#voice-list').addEventListener('click', function (e) {
      var t = e.target;
      if (t.dataset.play) {
        var v = voiceCache.find(function (x) { return String(x.id) === t.dataset.play; });
        if (v) playUrl(authUrl('/api/voices/' + v.id + '/sample'), t, '试听');
      } else if (t.dataset.synth) {
        location.hash = 'synth';
        setTimeout(function () {
          var sel = $('#synth-voice');
          sel.value = t.dataset.synth;
        }, 80);
      } else if (t.dataset.del) {
        deleteVoice(t.dataset.del);
      }
    });

    $('#synth-text').addEventListener('input', function () { $('#synth-counter').textContent = this.value.length + ' / 1000'; });
    $('#synth-btn').addEventListener('click', createSynth);
    $('#synth-play-btn').addEventListener('click', function () {
      var audio = $('#synth-audio');
      if (!audio.src) return;
      playUrl(audio.src, $('#synth-play-btn'), '播放');
    });

    $('#dub-video').addEventListener('change', function () {
      var f = this.files[0];
      if (!f) { $('#dub-source-box').hidden = true; return; }
      if (f.size > 100 * 1024 * 1024) { setErr('#dub-err', '视频超过 100MB 上限。'); $('#dub-source-box').hidden = true; return; }
      $('#dub-source').src = URL.createObjectURL(f);
      $('#dub-source-box').hidden = false;
    });
    $('#dub-btn').addEventListener('click', createDub);

    $('#batch-text').addEventListener('input', function () {
      var lines = this.value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean);
      $('#batch-counter').textContent = lines.length + ' 行';
    });
    $('#batch-btn').addEventListener('click', createBatch);
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ================= 启动 ================= */
  function init() {
    heroWave($('#hero-wave'));
    bindEvents();
    initNav();
    route();
    connect(true).then(function () {
      loadVoices();
    }).catch(function () { /* 连接失败已有提示 */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
