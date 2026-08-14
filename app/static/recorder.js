const recordButton = document.getElementById("record");
const stopButton = document.getElementById("stop");
const statusLabel = document.getElementById("recording-status");
const fileInput = document.getElementById("audio-file");
const preview = document.getElementById("preview");
const previewWrapper = document.getElementById("preview-wrapper");
const timerLabel = document.getElementById("recording-timer");
const canvas = document.getElementById("visualizer-canvas");
const canvasPlaceholder = document.getElementById("visualizer-placeholder");
const canvasCtx = canvas ? canvas.getContext("2d") : null;

let audioContext;
let processor;
let analyser;
let source;
let stream;
let chunks = [];
let animationId;
let timerInterval;
let recordingStartTime;

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

function startTimer() {
  recordingStartTime = Date.now();
  timerLabel.textContent = "00:00";
  timerInterval = setInterval(() => {
    const elapsedSecs = (Date.now() - recordingStartTime) / 1000;
    timerLabel.textContent = formatTime(elapsedSecs);
  }, 250);
}

function stopTimer() {
  clearInterval(timerInterval);
}

function drawWaveform() {
  if (!analyser || !canvasCtx) return;
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function render() {
    animationId = requestAnimationFrame(render);
    analyser.getByteTimeDomainData(dataArray);

    canvasCtx.fillStyle = "#0f172a";
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = "#14b8a6";
    canvasCtx.beginPath();

    const sliceWidth = (canvas.width * 1.0) / bufferLength;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0;
      const y = (v * canvas.height) / 2;

      if (i === 0) {
        canvasCtx.moveTo(x, y);
      } else {
        canvasCtx.lineTo(x, y);
      }

      x += sliceWidth;
    }

    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
  }

  render();
}

function stopWaveform() {
  if (animationId) {
    cancelAnimationFrame(animationId);
  }
  if (canvasCtx) {
    canvasCtx.fillStyle = "#0f172a";
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

function flattenBuffers(buffers) {
  const length = buffers.reduce((sum, item) => sum + item.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  for (const buffer of buffers) {
    result.set(buffer, offset);
    offset += buffer.length;
  }
  return result;
}

function writeString(view, offset, value) {
  for (let i = 0; i < value.length; i += 1) {
    view.setUint8(offset + i, value.charCodeAt(i));
  }
}

function encodeWav(samples, sampleRate) {
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);
  
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // PCM format chunk size
  view.setUint16(20, 1, true); // Linear quantization (PCM)
  view.setUint16(22, 1, true); // Mono channel
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true); // 16-bit
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([view], { type: "audio/wav" });
}

// Adjust canvas resolution
function initCanvas() {
  if (canvas) {
    canvas.width = canvas.offsetWidth || 400;
    canvas.height = canvas.offsetHeight || 70;
  }
}
window.addEventListener("resize", initCanvas);
initCanvas();

recordButton.addEventListener("click", async () => {
  try {
    initCanvas();
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    source = audioContext.createMediaStreamSource(stream);
    
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    processor = audioContext.createScriptProcessor(4096, 1, 1);
    chunks = [];
    processor.onaudioprocess = (event) => {
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    
    source.connect(processor);
    processor.connect(audioContext.destination);

    recordButton.disabled = true;
    stopButton.disabled = false;
    statusLabel.textContent = "Recording in progress...";
    statusLabel.style.color = "var(--danger)";
    if (canvasPlaceholder) canvasPlaceholder.style.display = "none";
    
    startTimer();
    drawWaveform();
  } catch (err) {
    console.error("Microphone access denied or error:", err);
    statusLabel.textContent = "Mic permission denied";
    statusLabel.style.color = "var(--danger)";
  }
});

stopButton.addEventListener("click", async () => {
  stopTimer();
  stopWaveform();

  if (processor) processor.disconnect();
  if (source) source.disconnect();
  if (stream) stream.getTracks().forEach((track) => track.stop());

  const sampleRate = audioContext ? audioContext.sampleRate : 44100;
  const wav = encodeWav(flattenBuffers(chunks), sampleRate);
  if (audioContext) await audioContext.close();

  const file = new File([wav], `recording-${Date.now()}.wav`, { type: "audio/wav" });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;

  preview.src = URL.createObjectURL(file);
  if (previewWrapper) previewWrapper.style.display = "block";

  recordButton.disabled = false;
  stopButton.disabled = true;
  statusLabel.textContent = "Audio attached (WAV)";
  statusLabel.style.color = "var(--success)";
  if (canvasPlaceholder) {
    canvasPlaceholder.style.display = "flex";
    canvasPlaceholder.textContent = "Recording completed & ready";
  }
});

// If user selects a file directly from file input
fileInput.addEventListener("change", () => {
  if (fileInput.files && fileInput.files[0]) {
    const file = fileInput.files[0];
    preview.src = URL.createObjectURL(file);
    if (previewWrapper) previewWrapper.style.display = "block";
    statusLabel.textContent = `File selected: ${file.name}`;
    statusLabel.style.color = "var(--primary)";
  }
});
