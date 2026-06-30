let capturedImage = null;

const video = document.getElementById("webcam");
const canvas = document.getElementById("captureCanvas");
const captureBtn = document.getElementById("captureBtn");
const preview = document.getElementById("photoPreview");
const form = document.getElementById("enrollForm");
const statusMsg = document.getElementById("statusMsg");

navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => { video.srcObject = stream; })
    .catch(() => { statusMsg.innerHTML = '<div class="alert alert-danger">Camera access denied.</div>'; });

captureBtn.addEventListener("click", () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    capturedImage = canvas.toDataURL("image/jpeg");
    preview.src = capturedImage;
    preview.style.display = "block";
});

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!capturedImage) {
        statusMsg.innerHTML = '<div class="alert alert-warning">Please capture a photo first.</div>';
        return;
    }
    const formData = new FormData(form);
    const payload = {
        full_name: formData.get("full_name"),
        role: formData.get("role"),
        department: formData.get("department"),
        contact: formData.get("contact"),
        photo: capturedImage,
    };
    statusMsg.innerHTML = '<div class="alert alert-info">Submitting...</div>';
    try {
        const res = await fetch("/enroll", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        statusMsg.innerHTML = data.success
            ? '<div class="alert alert-success">Enrolled successfully!</div>'
            : `<div class="alert alert-danger">${data.error || "Enrollment failed."}</div>`;
    } catch {
        statusMsg.innerHTML = '<div class="alert alert-danger">Network error.</div>';
    }
});
