let webcamStream = null;

function startWebcam(videoEl) {
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            webcamStream = stream;
            videoEl.srcObject = stream;
        })
        .catch(() => {
            const el = document.getElementById("statusMsg");
            if (el) el.innerHTML = '<div class="alert alert-danger">Camera access denied.</div>';
        });
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
