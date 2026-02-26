document.addEventListener("DOMContentLoaded", function () {

    const container = document.getElementById("toastContainer");
    const errorMessage = container.getAttribute("data-error");

    if (errorMessage) {
        showToast(errorMessage, "error");
    }

});

/* ================= BIOMETRIC LOGIN ================= */

function biometricLogin() {

    const btn = document.querySelector(".biometric-btn");

    if (!btn) return;
    if (btn.classList.contains("scanning")) return;

    btn.classList.add("scanning");
    btn.disabled = true;

    btn.innerHTML = `
        <i class="fas fa-spinner fa-spin"></i> Scanning Face ID...
    `;

    showToast("Scanning biometric data...", "info");

    setTimeout(() => {

        btn.classList.remove("scanning");
        btn.disabled = false;

        btn.innerHTML = `
            <i class="fas fa-fingerprint"></i> Login with Face ID
        `;

        showToast("Authentication Successful ✅", "success");

        setTimeout(() => {
            window.location.href = "/dashboard";
        }, 900);

    }, 2000);
}

/* ================= TOAST SYSTEM ================= */

function showToast(message, type = "success") {

    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.classList.add("toast", `toast-${type}`);
    toast.innerText = message;

    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add("show");
    });

    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 400);
    }, 3000);
}