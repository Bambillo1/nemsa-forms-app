// Document status toasts
document.addEventListener('DOMContentLoaded', () => {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltipTriggerList.map(tooltipTriggerEl => {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Show flash messages as toasts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const toast = new bootstrap.Toast(alert, {
            autohide: true,
            delay: 5000
        });
        toast.show();
    });
});