let webcamStream = null;
let currentDeviceId = null;
let videoDevices = [];

async function getVideoDevices() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(d => d.kind === "videoinput");
}

async function startWebcam(videoEl) {
    try {
        const devices = await getVideoDevices();
        if (devices.length > 0 && !videoDevices.length) {
            videoDevices = devices;
            currentDeviceId = devices[0].deviceId;
        }
    } catch (e) { /* ignore */ }

    const constraints = { video: true };
    if (currentDeviceId) {
        constraints.video = { deviceId: { exact: currentDeviceId } };
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        webcamStream = stream;
        videoEl.srcObject = stream;
        await videoEl.play();
    } catch (err) {
        const el = document.getElementById("statusMsg");
        if (el) el.innerHTML = '<div class="alert alert-danger">Camera access denied.</div>';
    }
}

async function switchCamera(videoEl) {
    if (videoDevices.length < 2) {
        videoDevices = await getVideoDevices();
    }
    if (videoDevices.length < 2) return;

    const currentIdx = videoDevices.findIndex(d => d.deviceId === currentDeviceId);
    const nextIdx = (currentIdx + 1) % videoDevices.length;
    currentDeviceId = videoDevices[nextIdx].deviceId;

    stopWebcam();
    await startWebcam(videoEl);
}

function captureFrame(videoEl, canvasEl) {
    canvasEl.width = videoEl.videoWidth;
    canvasEl.height = videoEl.videoHeight;
    canvasEl.getContext("2d").drawImage(videoEl, 0, 0);
    return canvasEl.toDataURL("image/jpeg");
}

function stopWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(t => t.stop());
        webcamStream = null;
    }
}
