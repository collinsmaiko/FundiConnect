// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');

    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', function() {
            navLinks.classList.toggle('active');
        });
    }

    // Close flash messages
    const closeBtns = document.querySelectorAll('.close-btn');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const alert = this.parentElement;
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100%)';
            setTimeout(() => alert.remove(), 300);
        });
    });

    // Auto-hide flash messages after 5 seconds
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100%)';
            setTimeout(() => alert.remove(), 300);
        });
    }, 5000);

    // Close mobile menu when clicking a link
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('active');
        });
    });

    // Add smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add lazy loading for images
    const images = document.querySelectorAll('img');
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    const originalSrc = img.getAttribute('data-src');
                    if (originalSrc) {
                        img.src = originalSrc;
                        img.removeAttribute('data-src');
                    }
                    img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        });
        images.forEach(img => imageObserver.observe(img));
    }
});

// Show notification with animation
window.showNotification = function(message, type = 'info') {
    const container = document.querySelector('.flash-messages') || createFlashContainer();
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;

    const icons = {
        success: 'check-circle',
        danger: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };

    alert.innerHTML = `
        <i class="fas fa-${icons[type] || 'info-circle'}"></i>
        <span>${escapeHtml(message)}</span>
        <span class="close-btn">&times;</span>
    `;

    container.appendChild(alert);

    const closeBtn = alert.querySelector('.close-btn');
    closeBtn.addEventListener('click', () => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateX(100%)';
        setTimeout(() => alert.remove(), 300);
    });

    setTimeout(() => {
        if (alert.parentNode) {
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100%)';
            setTimeout(() => alert.remove(), 300);
        }
    }, 5000);
};

function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages';
    document.body.appendChild(container);
    return container;
}

// Copy to clipboard with feedback
window.copyToClipboard = async function(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard!', 'success');
    } catch (err) {
        showNotification('Failed to copy', 'danger');
    }
};

// Phone formatting
window.formatPhone = function(input) {
    let value = input.value.replace(/\D/g, '');
    if (value.startsWith('0')) {
        value = '254' + value.substring(1);
    }
    if (value.length > 12) {
        value = value.substring(0, 12);
    }
    input.value = value;
};

// Image preview with enhanced functionality
window.previewImage = function(input, previewId) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const reader = new FileReader();

        // Check file size
        if (file.size > 5 * 1024 * 1024) {
            showNotification('Image too large. Max 5MB.', 'danger');
            input.value = '';
            return;
        }

        // Check file type
        if (!file.type.match('image.*')) {
            showNotification('Please select an image file.', 'danger');
            input.value = '';
            return;
        }

        reader.onload = function(e) {
            const preview = document.getElementById(previewId);
            if (preview) {
                preview.src = e.target.result;
                preview.style.display = 'block';
                preview.classList.add('loaded');
            }
        };
        reader.readAsDataURL(file);
    }
};

// Debounce function for search inputs
window.debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format currency
window.formatCurrency = function(amount) {
    return new Intl.NumberFormat('en-KE', {
        style: 'currency',
        currency: 'KES',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
};

// Format date relative (e.g., "2 days ago")
window.formatRelativeDate = function(date) {
    const now = new Date();
    const diffMs = now - new Date(date);
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return new Date(date).toLocaleDateString();
};

// Add loading state to buttons
window.setButtonLoading = function(button, isLoading, loadingText = 'Loading...') {
    if (isLoading) {
        button.dataset.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${loadingText}`;
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText;
    }
};

// Initialize scroll to top button
function initScrollToTop() {
    const btn = document.createElement('button');
    btn.innerHTML = '<i class="fas fa-arrow-up"></i>';
    btn.className = 'scroll-top-btn';
    document.body.appendChild(btn);

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            btn.style.display = 'flex';
        } else {
            btn.style.display = 'none';
        }
    });
}

// Initialize scroll to top on page load
initScrollToTop();
