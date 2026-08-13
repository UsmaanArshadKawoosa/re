const recordButton = document.getElementById("record");
const stopButton = document.getElementById("stop");
const statusLabel = document.getElementById("recording-status");
const fileInput = document.getElementById("audio-file");
const preview = document.getElementById("preview");

let audioContext;
let processor;
let source;
let stream;
let chunks = [];

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
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
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

recordButton.addEventListener("click", async () => {
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioContext = new AudioContext();
  source = audioContext.createMediaStreamSource(stream);
  processor = audioContext.createScriptProcessor(4096, 1, 1);
  chunks = [];
  processor.onaudioprocess = (event) => {
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };
  source.connect(processor);
  processor.connect(audioContext.destination);
  recordButton.disabled = true;
  stopButton.disabled = false;
  statusLabel.textContent = "Recording";
});

stopButton.addEventListener("click", async () => {
  processor.disconnect();
  source.disconnect();
  stream.getTracks().forEach((track) => track.stop());
  const wav = encodeWav(flattenBuffers(chunks), audioContext.sampleRate);
  await audioContext.close();
  const file = new File([wav], `recording-${Date.now()}.wav`, { type: "audio/wav" });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  preview.src = URL.createObjectURL(file);
  recordButton.disabled = false;
  stopButton.disabled = true;
  statusLabel.textContent = "Recording attached";
});
