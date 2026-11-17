// PassItOn – Campus Edition: Main Global JavaScript

document.addEventListener('DOMContentLoaded', function () {
    // 1. Auto-dismiss flash messages after 6 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 6000);
    });

    // 2. Wishlist AJAX Toggle
    const wishlistBtns = document.querySelectorAll('.wishlist-toggle-btn');
    wishlistBtns.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            
            const listingId = this.dataset.listingId;
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            
            fetch(`/listings/${listingId}/toggle-wishlist`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || '',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const icon = btn.querySelector('i');
                    if (data.saved) {
                        btn.classList.add('active');
                        if (icon) {
                            icon.classList.remove('bi-heart');
                            icon.classList.add('bi-heart-fill');
                            icon.style.color = '#e11d48';
                        }
                    } else {
                        btn.classList.remove('active');
                        if (icon) {
                            icon.classList.remove('bi-heart-fill');
                            icon.classList.add('bi-heart');
                            icon.style.color = '';
                        }
                    }
                }
            })
            .catch(err => console.error("Error toggling wishlist:", err));
        });
    });

    // 3. Multi-image file input preview
    const imageInput = document.getElementById('images');
    const previewContainer = document.getElementById('image-preview-container');
    
    if (imageInput && previewContainer) {
        imageInput.addEventListener('change', function () {
            previewContainer.innerHTML = '';
            if (this.files) {
                Array.from(this.files).forEach((file, index) => {
                    if (file.type.startsWith('image/')) {
                        const reader = new FileReader();
                        reader.onload = function (e) {
                            const col = document.createElement('div');
                            col.className = 'col-4 col-md-3 position-relative';
                            col.innerHTML = `
                                <div class="border rounded p-1 text-center bg-light">
                                    <img src="${e.target.result}" class="img-fluid rounded" style="height: 90px; width: 100%; object-fit: cover;">
                                    <small class="d-block text-truncate text-muted mt-1" style="font-size: 0.7rem;">${file.name}</small>
                                    ${index === 0 ? '<span class="badge bg-primary position-absolute top-0 start-0 m-2" style="font-size: 0.65rem;">Primary</span>' : ''}
                                </div>
                            `;
                            previewContainer.appendChild(col);
                        };
                        reader.readAsDataURL(file);
                    }
                });
            }
        });
    }
});
