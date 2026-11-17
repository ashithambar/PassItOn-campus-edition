// PassItOn – QR Handover Scanner Integration (html5-qrcode)

document.addEventListener('DOMContentLoaded', function () {
    const readerElement = document.getElementById('qr-reader');
    const tokenInput = document.getElementById('token');
    const verifyForm = document.getElementById('handover-verify-form');
    const statusMsg = document.getElementById('qr-status-message');

    if (!readerElement || !tokenInput) return;

    let html5QrCode = null;

    function onScanSuccess(decodedText, decodedResult) {
        console.log("QR Code detected:", decodedText);
        
        // Stop scanning
        if (html5QrCode) {
            html5QrCode.stop().then(() => {
                console.log("Scanner stopped.");
            }).catch(err => console.error(err));
        }

        // Auto-fill input
        tokenInput.value = decodedText;
        if (statusMsg) {
            statusMsg.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill"></i> QR Code detected! Submitting verification...</span>`;
        }

        // Automatically submit the verification form
        if (verifyForm) {
            setTimeout(() => {
                verifyForm.submit();
            }, 600);
        }
    }

    function onScanFailure(error) {
        // Continuous scan failure - normal when searching for QR
    }

    // Initialize scanner if Html5Qrcode is available
    if (typeof Html5Qrcode !== 'undefined') {
        html5QrCode = new Html5Qrcode("qr-reader");
        const config = { fps: 10, qrbox: { width: 250, height: 250 } };

        // Start back camera by default
        Html5Qrcode.getCameras().then(cameras => {
            if (cameras && cameras.length) {
                const cameraId = cameras[cameras.length - 1].id; // Prefer rear/back camera on mobile
                html5QrCode.start(
                    cameraId,
                    config,
                    onScanSuccess,
                    onScanFailure
                ).catch(err => {
                    console.warn("Camera start failed, showing manual input fallback:", err);
                    if (statusMsg) {
                        statusMsg.innerHTML = `<span class="text-muted"><i class="bi bi-camera-video-off"></i> Camera access unavailable. Please use the manual code entry below.</span>`;
                    }
                });
            } else {
                if (statusMsg) {
                    statusMsg.innerHTML = `<span class="text-muted"><i class="bi bi-camera-video-off"></i> No camera detected. Please enter code manually below.</span>`;
                }
            }
        }).catch(err => {
            console.warn("Camera permission / device error:", err);
            if (statusMsg) {
                statusMsg.innerHTML = `<span class="text-muted"><i class="bi bi-info-circle"></i> Camera not permitted. Enter code manually below.</span>`;
            }
        });
    }
});
